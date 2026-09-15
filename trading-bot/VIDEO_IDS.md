# Trading bot source videos — YouTube IDs (channel UCL4q6RblAKpIT6IESjjFLjg)

| Session | Video ID    | Length  | Auto captions |
|---------|-------------|---------|---------------|
| S1      | (not on YT) | —       | needs screen-record from Drive |
| S2      | aYKpqLSzcUg | 2:05:10 | ready |
| S3      | cG9LTLDXNtc | 2:07:29 | (assumed ready) |
| S4      | 8ecMb2jHgd8 | 2:08:57 | (assumed ready) |
| S5      | P_85Yf-skeE | 1:44:39 | (assumed ready) |
| S6      | yXwTjkDUcLM | 2:05:26 | ready |
| S7      | BnVyBKOck3o | 1:37:16 | (assumed ready) |
| S8      | rr3p4LjMY6U | 2:00:37 | ready |
| TBOT1   | 6u7mxH4xM-4 | 1:11:03 | (assumed ready) |

## Blocked routes tried in this session (2026-08-22)
- Cloud container -> youtube.com: egress proxy returns 403. yt-dlp unusable here.
- Browser fetch of captionTracks[0].baseUrl (+fmt=json3/srv3/vtt): HTTP 200, empty body.
  No `pot` param present anywhere in ytInitialPlayerResponse (only 8 formats -> videos
  may still be transcoding).
- youtubei/v1/get_transcript with params from ytInitialData: HTTP 400.
- Watch-page transcript panel: engagement panel stays HIDDEN, 0 segment renderers.
- Player captions module: getOption('captions','tracklist') returns [];
  player stuck in state 3 (buffering), video will not stream.
- Studio caption editor for ASR track: no editor route exposed for automatic captions.

## Unblock
STATE.md in the "Trading bot strategy extraction" session documents a pipeline that
DID work for S3/S4/S5/S7/TBOT1. Need that file.
