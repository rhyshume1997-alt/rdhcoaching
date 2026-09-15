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
    assert "247 keys exist in total" in out


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
