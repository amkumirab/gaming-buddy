# Game compatibility and performance report template

Record results for the candidate identified above. Empty rows and examples are not
test evidence. Use Pass, Fail, Not tested, or Not applicable with a reason. Complete
the environment fields before interpreting measurements.

## Environment

- Test date, Windows edition/version/build: Not recorded
- CPU, GPU, driver, RAM, display resolution and scaling: Not recorded
- Game title, game version, launcher: Not recorded
- Display mode (Windowed / Borderless / Exclusive Fullscreen): Not recorded
- HDR, monitor count, refresh rate, graphics preset, FPS cap, VSync: Not recorded
- Performance measurement tool and version: Not recorded
- Gaming Buddy profile, card count, visible pins and image sizes: Not recorded

## Repeatable procedure

1. Use a disposable game save and synthetic cards. Choose an offline or training area
   when possible. Do not change a game's protections or install hooks/injection tools
   to make an overlay test pass. Follow the game's supported overlay/tool policies.
2. Record the game build and all environment settings above. First run the same route
   or built-in benchmark with Gaming Buddy fully quit, including its tray process.
3. Warm up the game, then measure a fixed 60-second scene/route three times for each
   condition below. Alternate off/on order when practical. Keep the same graphics,
   FPS cap, scene, resolution, other running apps, and measurement tool in every run.
4. Repeat with Gaming Buddy idle, representative pins visible, and a separately recorded
   capture/OCR action. Capture is a transient workload; do not average its cost away
   into the idle measurement. Record action latency and visible stutters separately.
5. For memory, record GamingBuddy.exe private bytes and working set after 60 seconds idle
   and after repeated captures/searches. Record the sampling tool/interval. These are
   process measurements, not evidence of a GPU-memory or whole-system memory budget.
6. Test the interactions below. Repeat per display mode and monitor/scaling combination
   actually used; success in Borderless does not establish Exclusive Fullscreen support.

## Compatibility

| Scenario | Result | Evidence / reproduction steps |
| --- | --- | --- |
| Panel shortcut opens and closes; gameplay resumes normally | Not tested | |
| Region and full-monitor captures contain the correct game pixels | Not tested | |
| Overlay visible and readable in the recorded display mode | Not tested | |
| Click-through, focus mode, and card cycling | Not tested | |
| Quick Finder finds and opens a previously saved clue | Not tested | |
| Profile switches correctly and pins restore after returning to the game | Not tested | |
| Alt-Tab and resolution/monitor changes leave pins reachable | Not tested | |
| Capture/OCR cancellation and ordinary app exit | Not tested | |

## Performance results

Keep the raw per-run measurements or tool output. Compute summaries only from actual
data using the named tool's definitions. Never fill unknown values with zero. A frame
time at the 99th percentile and a tool's "1% low FPS" are not interchangeable metrics.

| Condition | Run | Avg FPS | P99 frame time (ms) | App private bytes (MiB) | App working set (MiB) | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| App fully quit | 1 / 2 / 3 separately | Not measured | Not measured | Not applicable | Not applicable | |
| App idle, no visible pins | 1 / 2 / 3 separately | Not measured | Not measured | Not measured | Not measured | |
| Representative pins visible | 1 / 2 / 3 separately | Not measured | Not measured | Not measured | Not measured | |
| Capture / OCR, action times recorded | 1 / 2 / 3 separately | Not measured | Not measured | Not measured | Not measured | |

- Cold launch until usable panel, three runs and timing method: Not measured
- Capture ready / saved latency and timing method: Not measured
- OCR completion latency, language pack and image dimensions: Not measured
- Repeated-action memory observations: Not measured
- Observable regressions, failed scenarios and limitations: Not assessed
- Conclusion for this game/configuration only: **Pending**

Share only sanitized logs and synthetic content. This local report is not uploaded
automatically and does not approve a public release or broad compatibility claim.
