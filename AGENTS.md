# Project instructions

## Working context

- Read `handoff.md` first, then `README.md` and relevant files under `docs/`.
  The newest handoff section supersedes historical observations below it.
- Canonical checkout: `/home/phobos/Projects/wd2-screensaver` (capital P).
  `~/.local/share/wd2-screensaver` is a symlink to this checkout on this machine.
- User-facing explanations and documentation are in Spanish. Code comments
  and agent handoffs may use English.
- Inspect `git status`/`git diff` before editing. Preserve unfinished work by
  other assistants; never reset a mode merely because its diff is large.
- Update the handoff as work completes: changes, actual tests, timings and
  remaining limitations. Do not leave completed tasks marked in progress.
- For delegated work, use the user's requested model. Current Codex preference
  is `gpt-6.1-sol` with low reasoning effort. Give each agent disjoint mode files;
  keep shared modules, docs and final integration with the main agent.

## Visual and data rules

- Recognizable silhouettes, material contrast and coherent movement take
  priority over more particles, bright edges or texture noise.
- Keep every mode's `farewell()`. Preserve WRENCH's established farewell.
- DOTMATRIX stays black with grayscale dots and must clearly form DEDSEC.
- No readable fake hacking source code. Artistic labels, diagrams and abstract
  data texture are allowed; do not add pretend scripts or code dumps.
- Screen cells contain printable, single-width characters only; no emoji,
  CJK, combining marks or external terminal controls. Sanitize external labels
  using `sysdata.display_text` or an equivalent existing safe API.
- Notifications are counted, never read. Audio is analyzed in memory, never
  recorded. Keep optional data sources and their privacy documentation.
- Do not add credentials, notification histories, recordings or runtime caches
  to the repository. Never read secrets to configure tests.

## Code and integration

- Each `mode_*.py` exports a unique `NAME` and `Mode(w,h)`, with
  `step(screen,now)` and `farewell(screen,now,progress)`.
- Preserve imports used by other modes. For example, TOWER consumes `SKULL`
  from `mode_logo.py` even though DEDSEC has its own newer skull renderer.
- After editing NUDLE map geometry/texture construction, regenerate its
  deterministic artwork with `tools/build_nudle_map.py` and include the NPZ.
  A stale/missing resource falls back correctly but restores the startup pause.
- Use `/usr/bin/python3` for tools: this machine's mise Python lacks NumPy.
  The interactive entry point handles that interpreter mismatch itself.
- No unnecessary desktop restart: a newly launched saver loads source changes.
  Don't close an existing user saver just to run a headless test.
- Before desktop/config changes, read the Omarchy skill and matching guide at
  `/home/phobos/.codex/skills/omarchy/`. Never edit `/usr/share/omarchy`.
- Installed launcher/plugin paths differ from their `integration/` copies.
  Keep copies synchronized when intentionally changing integration. Installer
  preview is the default; it backs up changed destinations with `--apply`.

## Verification

```bash
/usr/bin/python3 dedsec.py --list
/usr/bin/python3 tools/verify.py --full --mode mode_dotmatrix
/usr/bin/python3 tools/verify.py --full
/usr/bin/python3 tools/snap.py mode_dotmatrix 175 45 240
/usr/bin/python3 tools/preview.py --mode mode_dotmatrix --times 0 2.6 6 12 26 31 --output /tmp/dotmatrix.png
```

- Always check discovery of all 14 modes after cross-mode imports/exports change.
  No `skipping ...` messages should be silently accepted.
- Validate changed modes at 90x26, 175x45 and 240x60, including later phases and
  farewells. Run all modes after shared-renderer or integration changes.
- Inspect PNGs or live output; passing execution tests does not prove legibility.
  PNG previews are approximate and do not verify actual terminal font or focus.
- Benchmark serially, with no concurrent rendering/profiling workloads. Target
  roughly 25ms/frame at 175x45; 24fps has a 41.7ms frame budget. Preserve visual
  detail and report misses honestly. Instrumented profiles are not FPS timings.
- For pixel-preserving optimizations, compare old/new output on clipped and
  offscreen cases, not only typical centered geometry.

## Git

- Commit/push when the user requests them; session authorization persists.
- Use the configured user's Git identity. Do not add `Co-authored-by` trailers,
  assistant signatures or other assistant attribution.
- Stage intended source/docs changes; review staged diff and whitespace checks.
  Never stage temporary captures/logs, bytecode or personal configuration.
- The remote is private; don't change visibility or assume third-party art has
  a new license. See README provenance notes.
