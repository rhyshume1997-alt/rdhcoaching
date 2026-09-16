"""tests/test_integration.py — the whole thing, end to end.

``tbot.pipeline`` -> ``tbot.backtest.engine`` -> ``tbot.backtest.metrics`` -> ``tbot.cli``.
Nothing here is mocked: the harness discovers the pipeline exactly the way it does in production
(``default_plan_provider``), the lookahead audit is left **on**, and the CLI is driven through
``cli.main`` with real argv.

The synthetic generator's ``1H`` bars are relabelled ``4H`` throughout: CF-38 makes ``1H`` a
scalp timeframe, and these tests are about the swing path.  (Q14 enabled ``module_scalp_enabled``
with ``scalp_tf_floor`` at ``30m``, so ``1H`` is no longer vetoed outright at G18.)
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from tbot import cli
from tbot.backtest.engine import BacktestEngine, EventKind, default_plan_provider
from tbot.backtest.metrics import compute_metrics
from tbot.config import Config
from tbot.data import synthetic
from tbot.models import Timeframe

WARMUP = 60          # the 100-bar fixture is shorter than the §12.1 default warm-up window
EQUITY = Decimal(10_000)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def cfg() -> Config:
    return Config.load()


@pytest.fixture(scope="module")
def series():
    return synthetic(seed=7, tf=Timeframe.H4, symbol="SYNTHUSDT").series


@pytest.fixture(scope="module")
def result(series, cfg):
    """One real backtest, run through the harness' own pipeline discovery."""
    return BacktestEngine(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP,
                          audit_outputs=True).run()


@pytest.fixture(scope="module")
def csv_path(tmp_path_factory, series):
    path = tmp_path_factory.mktemp("data") / "synthetic_4h.csv"
    series.frame.reset_index().to_csv(path, index=False)
    return path


# --------------------------------------------------------------------------- the harness


def test_the_harness_finds_the_pipeline(series, cfg):
    """``default_plan_provider`` must resolve ``tbot.pipeline.run`` with no help."""
    from tbot.backtest.engine import BarWindow

    output = default_plan_provider(BarWindow.at(series, len(series) - 1), cfg)
    assert output.detections or output.rejections or output.setups, (
        "the harness reached tbot.pipeline but got an empty world back"
    )


def test_backtest_completes_end_to_end(result):
    assert result.bars == 100
    assert result.warmup_bars == WARMUP
    assert len(result.equity_curve) == result.bars
    assert len(result.events) > 0
    assert result.rejections, "not one candidate was rejected in 40 analysed bars"
    assert any(e.kind is EventKind.PLAN for e in result.events), "no plan was ever armed"


def test_no_lookahead_survives_the_whole_run(series, cfg):
    """``audit_outputs=True`` re-walks every object the pipeline returns on every bar."""
    engine = BacktestEngine(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP,
                            audit_outputs=True)
    engine.run()          # a LookaheadError anywhere in the run fails this test


def test_backtest_is_deterministic(series, cfg):
    a = BacktestEngine(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP).run()
    b = BacktestEngine(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP).run()
    assert [t.id for t in a.trades] == [t.id for t in b.trades]
    assert [str(t.net_pnl_usd) for t in a.trades] == [str(t.net_pnl_usd) for t in b.trades]
    assert str(a.ending_equity) == str(b.ending_equity)


# --------------------------------------------------------------------------- metrics


def test_metrics_are_coherent(result):
    report = compute_metrics(result)
    assert report.symbol == "SYNTHUSDT"
    assert report.bars == result.bars
    assert report.starting_equity == EQUITY

    realised = sum((t.net_pnl_usd for t in result.trades), Decimal(0))
    unrealised = sum((t.unrealised_pnl_usd for t in result.open_at_end), Decimal(0))
    assert abs(report.ending_equity - (EQUITY + realised + unrealised)) < Decimal("0.01")
    assert report.net_pnl_usd == report.ending_equity - report.starting_equity

    rates = report.win_rates
    assert rates.trades == len(result.trades)
    assert 0 <= rates.wins <= rates.trades
    assert Decimal(0) <= rates.net_positive_pct <= Decimal(100)
    assert rates.wins + rates.losses + rates.breakevens == rates.trades
    assert report.drawdown.max_pct >= Decimal(0)
    assert report.drawdown.max_usd >= Decimal(0)
    assert report.liquidations == 0, "a liquidation is a §8.8 sizing bug, not a result (A12)"

    text = report.render()
    assert "BACKTEST REPORT" in text
    assert "SYNTHUSDT" in text


def test_metrics_render_the_rejection_attribution(result):
    report = compute_metrics(result)
    assert report.veto_census, "no rejection attribution was produced"
    assert sum(count for _, count in report.veto_census) == len(result.rejections)
    assert sum(count for _, count in report.veto_reasons) == len(result.rejections)
    for gate, count in report.veto_census:
        assert gate and count > 0
    assert all(reason for reason, _ in report.veto_reasons)


def test_every_rejection_names_a_gate_and_a_reason(result):
    for rejection in result.rejections:
        assert rejection.gate and rejection.reason
        assert rejection.symbol == "SYNTHUSDT"
        assert rejection.bar_index >= WARMUP


def test_rejections_reach_the_event_log(result):
    logged = [e for e in result.events if e.kind is EventKind.REJECTION]
    assert len(logged) == len(result.rejections)
    for event in logged:
        assert event.data["gate"] and event.data["reason"]


# --------------------------------------------------------------------------- the id chain


def test_source_ids_survive_into_the_trade_record(result):
    armed = [e for e in result.events if e.kind is EventKind.PLAN]
    assert armed, "no plan was armed, so there is no chain to check"
    for event in armed:
        assert event.source_ids, f"plan {event.plan_id} was armed with no rule chain"
    for trade in result.trades:
        assert trade.source_ids, f"closed trade {trade.ref} cannot name a rule"
        assert trade.plan_id and trade.setup_id
        assert trade.confluence_classes, "a trade with no confluence classes"


def test_detections_are_attributed_to_a_detector(result):
    for detection in result.detections:
        assert detection.detector
        assert detection.object_id.startswith("SYNTHUSDT:4H:")
        assert detection.bar_index >= WARMUP


# --------------------------------------------------------------------------- the CLI


def test_cli_config_runs(capsys):
    assert cli.main(["config"]) == 0
    out = capsys.readouterr().out
    assert "key" in out and "source" in out
    assert "254 keys exist in total" in out


def test_cli_config_json_is_machine_readable(capsys):
    assert cli.main(["config", "--json", "--grep", "pipeline"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(row["key"] == "pipeline_order" for row in payload)


def test_cli_scan_runs(csv_path, capsys):
    code = cli.main(["scan", "--csv", str(csv_path), "--tf", "4H",
                     "--symbol", "SYNTHUSDT", "--bars", "6"])
    assert code == 0
    out = capsys.readouterr().out
    assert "scan  SYNTHUSDT 4H" in out
    assert "trade ticket(s)" in out or "produced nothing" in out


def test_cli_backtest_runs(csv_path, tmp_path, capsys):
    run_file = tmp_path / "run.json"
    events = tmp_path / "events.txt"
    code = cli.main(["backtest", "--csv", str(csv_path), "--tf", "4H",
                     "--symbol", "SYNTHUSDT", "--warmup", str(WARMUP),
                     "--events", str(events), "--save-run", str(run_file)])
    assert code == 0
    out = capsys.readouterr().out
    assert "BACKTEST REPORT" in out
    assert run_file.exists() and events.exists()
    payload = json.loads(run_file.read_text())
    assert payload["meta"]["symbol"] == "SYNTHUSDT"
    assert "metrics" in payload and "events" in payload


def test_cli_explain_runs(csv_path, tmp_path, capsys):
    run_file = tmp_path / "run.json"
    assert cli.main(["backtest", "--csv", str(csv_path), "--tf", "4H",
                     "--symbol", "SYNTHUSDT", "--warmup", str(WARMUP),
                     "--save-run", str(run_file)]) == 0
    capsys.readouterr()
    payload = json.loads(run_file.read_text())
    # Any armed trade explains itself, closed or not — the chain is the point, not the P&L.
    refs = [e["trade_ref"] for e in payload["events"] if e.get("trade_ref")]
    if not refs:
        pytest.skip("this run armed no plan, so there is nothing to explain")
    ref = refs[0]
    assert cli.main(["explain", "--run", str(run_file), "--trade", ref]) == 0
    out = capsys.readouterr().out
    assert f"EXPLAIN  {ref}" in out
    assert "PLAN" in out and "ARM" in out
    assert "[CF-" in out, "the explained chain carries no rule ids"


def test_cli_explain_reports_an_unknown_trade(csv_path, tmp_path, capsys):
    run_file = tmp_path / "run.json"
    assert cli.main(["backtest", "--csv", str(csv_path), "--tf", "4H",
                     "--symbol", "SYNTHUSDT", "--warmup", str(WARMUP),
                     "--save-run", str(run_file)]) == 0
    capsys.readouterr()
    assert cli.main(["explain", "--run", str(run_file), "--trade", "T9999"]) == 1
    assert "no trade 'T9999'" in capsys.readouterr().out


def test_cli_ticket_renders_the_rule_chain(series, cfg):
    """A ticket that cannot name its rules is the failure INTERFACES.md §6.3 exists to prevent."""
    from tbot import pipeline

    for i in range(WARMUP, len(series)):
        record = pipeline.analyse_bar(series.head(i + 1), cfg)
        if not record.plans:
            continue
        setups = {s.id: s for s in record.setups}
        plan = record.plans[0]
        ticket = cli.render_ticket(plan, setup=setups.get(plan.setup_id))
        assert "SOURCE RULES:" in ticket
        assert "(none recorded)" not in ticket
        assert "ENTRIES" in ticket and "STOP" in ticket and "TAKE PROFITS" in ticket
        return
    pytest.skip("no plan was produced on this fixture")


# ------------------------------------------------- GAP 1: out-of-sample split (GAPS.md, 2026-09-15)
#
# Everything here is OUR engineering convention. He has never been recorded discussing
# out-of-sample testing, walk-forward or holdout at all, so the split ships as an opt-in CLI
# flag and the 2/3 default is marked [OUR CHOICE] at every place it is written down.


def test_split_default_fraction_is_two_thirds_and_cli_agrees():
    """`cli._SPLIT_USE_DEFAULT` resolves against the engine constant; pin them together.

    The CLI duplicates the number only so that building the argument parser does not have to
    import the backtest package. This test is what makes that duplication safe.
    """
    from tbot.backtest.engine import DEFAULT_IN_SAMPLE_FRACTION

    assert DEFAULT_IN_SAMPLE_FRACTION == pytest.approx(2.0 / 3.0)
    assert cli._SPLIT_USE_DEFAULT == 0.0, "the sentinel must be an illegal fraction"


def test_split_segments_are_chronological_disjoint_and_cover_the_series(series, cfg):
    from tbot.backtest.engine import split_backtest

    split = split_backtest(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP)
    # the fraction divides the ANALYSABLE bars, not the raw series (corrected 2026-09-15)
    analysable = len(series) - WARMUP
    assert split.split_index == WARMUP + round(analysable * (2.0 / 3.0))
    assert split.in_sample_bars + split.out_of_sample_bars == len(series)
    assert split.in_sample_analysable + split.out_of_sample_analysable == analysable
    assert split.realised_in_sample_share == pytest.approx(2.0 / 3.0, abs=0.02), (
        "the delivered share must match the requested one, which is the whole point")
    # in-sample is strictly earlier: it never sees a bar at or beyond the split index
    assert split.in_sample.bars == split.split_index
    # out-of-sample is handed the whole series but analyses only from the split on
    assert split.out_of_sample.bars == len(series)
    assert split.out_of_sample.warmup_bars == split.split_index


def test_split_in_sample_equals_a_plain_run_on_the_head(series, cfg):
    """The in-sample segment must be exactly a backtest of the first 2/3 — no more, no less."""
    from tbot.backtest.engine import run_backtest, split_backtest

    split = split_backtest(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP)
    plain = run_backtest(series.head(split.split_index), cfg,
                         starting_equity=EQUITY, warmup_bars=WARMUP)
    assert split.in_sample.bars == plain.bars
    assert [t.id for t in split.in_sample.trades] == [t.id for t in plain.trades]
    assert len(split.in_sample.rejections) == len(plain.rejections)


def test_split_out_of_sample_opens_nothing_before_the_split(series, cfg):
    """Warm-up history may be read; a trade may not be opened in it."""
    from tbot.backtest.engine import split_backtest

    split = split_backtest(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP)
    for trade in split.out_of_sample.trades:
        assert trade.opened_index >= split.split_index, (
            f"{trade.ref} opened at bar {trade.opened_index}, inside the in-sample region")


def test_split_rejects_an_impossible_fraction(series, cfg):
    from tbot.backtest.engine import SplitError, split_backtest

    for bad in (0.0, 1.0, -0.5, 1.5):
        with pytest.raises(SplitError):
            split_backtest(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP,
                           in_sample_fraction=bad)


def test_split_refuses_when_there_are_too_few_analysable_bars(series, cfg):
    """Failing loudly beats silently reporting a segment that never ran.

    The guard moved with the meaning of the fraction. It is no longer "the split index landed
    on the warm-up" -- that can no longer happen, because the index is measured FROM the
    warm-up. It is now "the series does not leave two analysable bars to divide".
    """
    from tbot.backtest.engine import SplitError, split_backtest

    with pytest.raises(SplitError, match="analysable"):
        split_backtest(series, cfg, starting_equity=EQUITY, warmup_bars=len(series) - 1,
                       in_sample_fraction=0.5)


def test_a_half_split_now_works_where_it_used_to_be_refused(series, cfg):
    """Evidence the fix is real: 0.5 on this fixture was refused before, and is even now."""
    from tbot.backtest.engine import split_backtest

    split = split_backtest(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP,
                           in_sample_fraction=0.5)
    assert split.in_sample_analysable == split.out_of_sample_analysable == 20


def test_split_result_has_no_combined_metric(series, cfg):
    """A merged headline is the exact failure the split exists to expose; it must not exist."""
    from tbot.backtest.engine import split_backtest

    split = split_backtest(series, cfg, starting_equity=EQUITY, warmup_bars=WARMUP)
    for banned in ("combined", "merged", "total", "overall", "headline"):
        assert not any(banned in name for name in dir(split)), (
            f"SplitResult exposes a '{banned}' member - the two segments must stay separate")


# -- the CLI flag ------------------------------------------------------------------------------


def _backtest_argv(csv_path, *extra):
    return ["backtest", "--csv", str(csv_path), "--tf", "4H", "--symbol", "SYNTHUSDT",
            "--warmup", str(WARMUP), *extra]


def test_backtest_without_split_is_byte_identical_to_the_single_run(csv_path, series, cfg,
                                                                    capsys):
    """ACCEPTANCE: adding --split must not move one byte of the default output."""
    from tbot.backtest.engine import run_backtest

    assert cli.main(_backtest_argv(csv_path)) == 0
    out = capsys.readouterr().out

    result = run_backtest(series, cfg, starting_equity=Decimal("10000"), warmup_bars=WARMUP)
    expected = compute_metrics(result).render() + "\n"
    if not result.trades:
        expected += cli._NO_PIPELINE + "\n"

    assert out == expected
    assert "IN-SAMPLE" not in out and "chronological split" not in out


def test_cli_split_prints_two_labelled_reports(csv_path, capsys):
    assert cli.main(_backtest_argv(csv_path, "--split")) == 0
    out = capsys.readouterr().out
    assert out.count("BACKTEST REPORT") == 2, "expected exactly one report per segment"
    assert "== IN-SAMPLE: bars 0-86" in out
    assert "== OUT-OF-SAMPLE: bars 87-99" in out
    assert "chronological split at bar 87 of 100" in out
    assert "of ANALYSABLE bars in-sample" in out, "the header must not imply raw bars"
    assert "27 analysable in-sample / 13 out-of-sample" in out
    assert "[OUR CHOICE" in out, "the 2/3 convention must be marked as ours"
    assert "NOT merged into a headline" in out


def test_cli_split_accepts_an_explicit_fraction(csv_path, capsys):
    assert cli.main(_backtest_argv(csv_path, "--split", "0.7")) == 0
    out = capsys.readouterr().out
    assert "chronological split at bar 88 of 100" in out          # 60 warm-up + 70% of 40
    assert "70.0% of ANALYSABLE bars in-sample" in out
    assert "28 analysable in-sample / 12 out-of-sample" in out


def test_cli_split_reports_a_usage_error_rather_than_crashing(csv_path, capsys):
    """A warm-up that leaves fewer than two analysable bars cannot be split."""
    argv = ["backtest", "--csv", str(csv_path), "--tf", "4H", "--symbol", "SYNTHUSDT",
            "--warmup", "99", "--split", "0.5"]
    assert cli.main(argv) == 2
    out = capsys.readouterr().out
    assert "cannot split this series" in out
    assert "BACKTEST REPORT" not in out


def test_cli_split_writes_one_artifact_pair_per_segment(csv_path, tmp_path, capsys):
    run_file = tmp_path / "run.json"
    events = tmp_path / "events.txt"
    assert cli.main(_backtest_argv(csv_path, "--split", "--events", str(events),
                                   "--save-run", str(run_file))) == 0
    capsys.readouterr()

    assert not run_file.exists(), "the unsuffixed name must not be written under --split"
    for tag in ("in_sample", "out_of_sample"):
        run_seg = tmp_path / f"run.{tag}.json"
        ev_seg = tmp_path / f"events.{tag}.txt"
        assert run_seg.exists() and ev_seg.exists(), f"missing artifacts for {tag}"
        payload = json.loads(run_seg.read_text())
        assert payload["meta"]["symbol"] == "SYNTHUSDT"
        assert "metrics" in payload and "events" in payload
    # the out-of-sample run records its warm-up as the split index: that is the audit trail
    oos = json.loads((tmp_path / "run.out_of_sample.json").read_text())
    assert oos["meta"]["warmup_bars"] == 87
