# Handoff — WD2 screensavers

## LATEST: further visual polish completed (2026-10-02 night)

User asked to continue Claude's changes, substantially improve DRONE and
DOTMATRIX, add visual polish to TOWER and remove NUDLE's occasional startup
pause. Preserve all eight existing modified files, including Claude's cursor
cleanup and idle-lock changes. Source backup before this pass:
`/tmp/wd2-evening-backup-20261002-220306`.

Three gpt-6.1-sol low agents finished disjoint DRONE, DOTMATRIX and TOWER files.
Root owns NUDLE, integration review and documentation. No desktop configuration
or installed plugin changes are being made in this pass.

NUDLE diagnosis confirmed: first constructor spent1.291s building deterministic
map artwork. Added a549KiB baked assets/nudle_map.npz, fingerprinted against
geometry/builder source, loaded with allow_pickle=False and shape/dtype checks.
Initial constructor sample is0.094s; bitmap/masks/mips match generation exactly.
Missing/stale resource falls back to procedural generation. Regenerate via
`/usr/bin/python3 tools/build_nudle_map.py` after changing map construction.
This asset contains no live/user data. Stale/missing/corrupt fallback checks pass.

Visual work now finished: DRONE stable window modules per facade (LOD no longer
splits a pane differently across pixels), restrained lighting, deeper background
city, rain/reflections only outside tunnel, city visible through exit, tunnel
curbs/rails and police UAV. DOTMATRIX bright modeled hands and bolder DEDSEC,
quiet background and fixed premature return snap. TOWER mechanical belts,
setback parapets and final pullback showing crown/antenna and sky skull.
Claude BOTNET pixel arcs/occlusion rewrite visually reviewed and retained.

All14 full timeline/glyph/farewell checks passed at90x26/175x45/240x60; final
DRONE/DOTMATRIX versions additionally passed full per-mode checks. All14 names
discovered without skips. Final serial timing completed with all agents idle: all14 at175x45 plus the
four requested modes at90x26/240x60 (22 samples). Permanent evidence:
`docs/performance-2026-10-02-night.csv`, report:
`docs/polish-2026-10-02-night.md`. At175x45 DOTMATRIX16.8ms, DRONE32.5ms,
NUDLE11.8ms and TOWER34.6ms. DRONE54.8ms/TOWER49.1ms at240x60 exceed24fps budget.
No guaranteed25ms/24fps claim; samples vary by scene and are not worst cases.
AGENTS/CLAUDE and architecture/validation/README updated, including44sDOTMATRIX
loop and NUDLE rebuild instructions. No outstanding source work or active agents.
User's session authorization for commit/push persists; use configured user identity
with no coauthor/assistant trailers. Resulting commit is available in Git log. No headless
check should be described as a new live desktop test.

## Previous: Claude visual pass in progress (2026-10-02 evening)

User asked for big *visual* improvements to TOWER, NUDLE and DOTMATRIX, plus the
weak points from Claude's evaluation (scores /10 from fresh 175x45 previews):
DRONE 6 (near buildings are unreadable orange blobs, 41 ms), DOTMATRIX 6 (static,
empty), TOWER 7 (flat block tower, sparse city), NUDLE 7 (fold confusing, empty
search bar, 34 ms), BOTNET 7 (arcs render as black smears on the globe).

Uncommitted, finished and tested by Claude (keep): `dedsec.py` restores the mouse
cursor first in `cleanup()` and wraps the frame loop so a dead pty (idle lock runs
`pkill -f org.omarchy.screensaver`) can't skip it; `integration/.../phobos.idle/Service.qml`
and the installed copy restore the cursor after `omarchy-system-wake`. Live test:
launch saver → cursor invisible true → pkill like the lock → invisible false.

Idle lock disabled at the user's request: `~/.config/omarchy/shell.json` now has
`"idle": {"screensaver": 150, "lock": false}` (backup `shell.json.bak.*`). The cloned
`phobos.idle/Service.qml` (installed + `integration/` copy) gained `lockEnabled`
(`idleConfig.lock !== false`); when false no lock timer is scheduled and the first idle
timeout is the screensaver's. `omarchy-shell idle status` reports `lockEnabled`.
Needed `omarchy restart shell` (hot reload kept the old instance answering IPC).
Verified: lockEnabled False, screensaver 150 s. Manual `omarchy system lock` still works.

Parallel Opus sub-agents (disjoint files, nothing else may be edited by them):
| agent | files | progress notes |
|---|---|---|
| TOWER | `mode_tower.py` (keep `from mode_logo import SKULL` working) | `/tmp/wd2-agent-notes/tower.md` |
| NUDLE — **DONE** (rebuilt: real SF outlines, 3 road tiers, 3D bridges + ~95 towers, 6 views, typed search, pins, routes with arrow, ETA/turn cards, tile-flip fold, pink DedSec hijack; verify --full passed; ~11-16 ms avg under load, camera flights up to ~33 ms, flip start frame 50-100 ms, first map build ~1.3 s per process; reviewed by Claude) | `mode_nudle.py` | `/tmp/wd2-agent-notes/nudle.md` |
| DOTMATRIX — **DONE** (44 s loop: 3D hands, touch ripple, pour into DEDSEC, orbit rings, dotted globe, re-form; verify --full passed; 17.6 ms at 175x45, 27 ms at 240x60; reviewed by Claude) | `mode_dotmatrix.py` (read-only `assets/dot_hands.json`) | `/tmp/wd2-agent-notes/dotmatrix.md` |
| DRONE+BOTNET | `mode_drone.py`, `mode_botnet.py` | `/tmp/wd2-agent-notes/drone-botnet.md` |

### Status snapshot when the user ran low on Claude tokens (2026-10-02 ~21:00)

Working tree (all uncommitted): `dedsec.py`, `handoff.md`, `integration/.../phobos.idle/Service.qml`
(Claude, finished), `mode_dotmatrix.py` + `mode_nudle.py` (agents DONE, reviewed),
`mode_tower.py`, `mode_botnet.py`, `mode_drone.py` (agents may still be running or be cut off).

- TOWER agent: full rewrite done and `verify --full` OK at milestone 2 (raycast chamfered
  setback tower, 7-layer city, hex prism shields with cracks/shards, drones, heli searchlight,
  clouds, finale blackout → sky skull → shockwave). Perf is the open issue: ~27 ms mean,
  31-35 ms peak (old was ~20). Original backup `/tmp/wd2-agent-notes/mode_tower.orig.py`.
  Must still review previews (`tools/preview.py --mode mode_tower --times 3 15 30 45 60`).
- BOTNET: DONE by agent (black smears fixed: text was drawn over globe pixels with bg=None;
  now ortho globe, pixel arcs with glow + occlusion, pixel packets, nodes with rings, night
  city lights, custom panels NODE LIST / WORLD MAP / TRAFFIC / REGIONS). verify --full OK,
  18 ms. Not yet reviewed visually by Claude.
- DRONE: WORK IN PROGRESS. Done: wider streets, higher cruise altitude looking down,
  numpy facade windows with LOD, side shading, street lamps + cars with trails; ~32 ms
  (was 43). TODO: tunnel as lit arches, siren perf, more perf, `verify --full`.
  Original backup: scratchpad `dronebot/mode_drone.orig.py` (may be gone) — git HEAD also has it.

Next steps for whoever continues (Codex):
1. If the agent processes are gone, run `/usr/bin/python3 tools/verify.py --full --mode mode_drone`
   (and tower, botnet). If DRONE fails and can't be fixed quickly, `git checkout -- mode_drone.py`.
2. Review previews of TOWER, BOTNET, DRONE; then serial timings for all 14 modes
   (`tools/snap.py` at 175x45 with nothing else running) and update docs/performance CSV.
3. Optional remaining: HACKERSPACE/HOLOGRAM perf (~32 ms), TOWER perf.
4. Report to the user in Spanish; commit/push only if asked (no assistant trailers).

If interrupted: read the notes files, `git diff --stat`, run
`/usr/bin/python3 tools/verify.py --full --mode <m>` per touched mode; if a mode is
broken and not quickly fixable, `git checkout -- <file>`. Remaining after agents:
HACKERSPACE/HOLOGRAM perf (~32 ms), serial timings, previews, Spanish report,
commit only if the user asks.

## Previous: continuation completed (2026-10-02)

Claude's interrupted visual work has been preserved and completed. All delegated
agents have finished; no source tasks remain running. The user authorized commit
and push with the configured user identity and no coauthor or assistant trailers.
AGENTS.md, CLAUDE.md and documentation were created before committing. See the
repository Git log for the resulting commit; canonical checkout remains
`/home/phobos/Projects/wd2-screensaver` (capital P).

The Spanish per-mode report is `docs/polish-2026-10-02.md`; final serial timings
are recorded permanently in `docs/performance-2026-10-02.csv`. Read those and
AGENTS.md before the historical notes below, which are not pending tasks.

Completed changes:
- Preserved Claude's detailed DRONE, GOLDENGATE, HACKERSPACE, HOLOGRAM,
  DEDSEC, NUDLE, PROFILER, TEXTWALL, TRAFFIC and WRENCH scenes and farewells.
- TOWER import fixed: restored `mode_logo.SKULL` compatibility bitmap without
  replacing the new detailed DEDSEC skull renderer. Installed discovery lists
  all 14 unique modes without warnings; actual Saver rotation rendered all 14
  with transitions. Configured modes/exclude lists are empty.
- BOTNET shading, atmosphere, label fit, audio states, time-based packets and
  impact rings; DOTMATRIX staged DEDSEC arrivals and coherent point ribbons;
  SCOUTX hue-preserving filters and avatars; TOWER glass and background details.
- Pixel-preserving performance work: DRONE adjugate projection, cached axes,
  earlier distance culling, bounded halos/neon and fractional coordinate math;
  WRENCH clipped row fills; HOLOGRAM shading cache/voxel row blocks (original
  cone retained); NUDLE building culling/fill and label fixes; HACKERSPACE wall
  palette quantization. HOLOGRAM holds a readable front view before turning.
- Rejected DRONE window span and HOLOGRAM vector cone variants because whole
  frame measurements did not show a reliable improvement. Do not reintroduce
  them based only on isolated-function timings.
- tools/verify.py checks character width on every frame and uses seed 24 by
  default. All 14 modes passed full 80-second simulated timelines, every-frame
  glyph validation and nine farewell progress points at 90x26/175x45/240x60.
  Changed optimized modes passed again after their final edits.
- Pixel comparisons: WRENCH 1600 clipped polygons; DRONE 1000 projections and
  final coordinate change over 18 real camera views; HOLOGRAM 30 frames across
  three sizes including morph/turn. PNG phase reviews completed. These are
  headless tests, not a new live desktop/font/focus/data-source check.

Performance limitations are explicit in the report. At175x45 final DRONE39.5ms,
HACKERSPACE34.3ms, HOLOGRAM34.2ms, NUDLE29.4ms, GOLDENGATE28.7ms and TOWER25.8ms
miss the advisory25ms goal. All sampled175x45 timings are below41.7ms, with
little margin for DRONE. Some240x60 samples exceed the24fps budget. Timings
vary with phase and are not worst-case guarantees. Do not sacrifice scene
recognition just to claim a timing target.

No integration/system-data/config changes were needed. An already-running
saver retains its old discovery list: close and relaunch to load all14 modes.
The runtime path `~/.local/share/wd2-screensaver` is a symlink to this checkout.
No requirement to delete this handoff: user explicitly asked to maintain it.
Temporary backup/captures/logs are under `/tmp/wd2-claude-backup-20261002-124633`
and `/tmp/wd2-claude-review`; they are not permanent repository artifacts.

## Earlier: Claude polish pass interrupted (2026-10-02)

Claude reviewed every mode with `tools/preview.py` contact sheets (175x45, t=3/15/30 s)
and launched 7 parallel sub-agents, each allowed to edit ONLY its two files. They
may have been cut off by a usage limit mid-edit, so assume any of these files can
be half-finished. Nothing was committed by Claude; check `git status` / `git diff`.

| files | diagnosis given to the agent |
|---|---|
| `mode_profiler.py` | 3D city behind the card is an unreadable mess of teal shards; make buildings/streets/pedestrians legible, clear reticles, link reticle→card, mini-map |
| `mode_botnet.py` | smoother globe shading (terminator, atmosphere ring), better nodes/arcs, empty panels (AUDIO TAP blank when silent), spectacular final attack, clear satellites |
| `mode_traffic.py` | nice but no visible chaos: recurring hack events (all green, near misses, skid marks, bollards, flipping car, hydrant, honking, police car, pedestrians), HACKED HUD with counters |
| `mode_drone.py` | tunnel is cluttered lines, buildings are flat pale slabs: shaded faces/windows/neon, clean tunnel arches, visible police drone, clear crash zoom |
| `mode_hackerspace.py` | dark/muddy, giant purple couch covers foreground: readable WD2 hideout (neon sign, monitors with live mini visuals, Wrench mask, 3D printer, robot, cat, server rack), better composition |
| `mode_tower.py` | blocky tower, sparse city: glass facade, Blume panels, antenna light, satisfying shield shatter, richer city, epic finale |
| `mode_wrench.py` | KEEP the farewell (user loves it). Flat grey mask, empty black background: real Wrench mask look (bevel, vents, rivets, hood, LED glow) + coherent backdrop (garage/workbench, sparks, holograms). Perf was ~27 ms |
| `mode_hologram.py` | proper hologram look (scanlines, flicker, light cone), lab stage, meaningful panels, smoother morph |
| `mode_logo.py` | bottom half empty: neon grid floor with reflections, skyline/palms vs sun, light trails; crisp recognizable skull (was pink noise); purposeful panels |
| `mode_dotmatrix.py` | MUST stay black/white dotted wallpaper style; add depth/life (parallax dots, breathing hands, dot flow between fingertips, sweep when DEDSEC forms, ripples), elegant not noisy |
| `mode_textwall.py` | user likes its detail; graffiti lettering is illegible → bold readable block letters (outline, fill, shadow, drips); more street life (cat, skater, pigeons, ctOS camera hacked red→green). Perf was ~28 ms |
| `mode_scoutx.py` | more/better pixel-art photos, smooth tilted feed scroll, like bursts, story rings, crisp fullscreen zoom with flash, filters |
| `mode_goldengate.py` | most beautiful mode, polish only: shimmering stretched water ripples (not blocky), cars with lights, ships/sailboats with wakes, gulls, fog under deck, skyline lit windows, DedSec bridge-light flicker |
| `mode_nudle.py` | clearer labels, smoother fold, 3D downtown buildings, route car icon, pin bounce + shadow, more dramatic DedSec hijack |

Rules given to agents (keep enforcing): ≤25 ms/frame at 175x45 (`tools/snap.py`),
no exceptions at 90x26 and 240x60, `tools/verify.py --full` passes, single-width
printable chars only, no readable fake hacking source code, keep `farewell()`,
recognizable coherent detail over noise, don't touch shared modules.

### To finish
1. For each file above: `git diff --stat`; if a mode is broken or half-edited and
   can't be fixed quickly, `git checkout -- <file>` to restore it.
2. Run `/usr/bin/python3 tools/verify.py --full` and `tools/snap.py` at 3 sizes for all modes.
3. Make new contact sheets with `tools/preview.py` and compare with the diagnosis.
4. Tell the user (Spanish) what improved per mode; commit only if the user asks.

---

# Earlier handoff (from Codex) — WD2 screensavers

The user is running low on their Codex 5-hour allowance and asked for a bounded
polish pass plus this handoff. Continue improving recognition and animation,
and communicate with the user in Spanish. Keep this file until the user asks
to remove it; they explicitly requested a new handoff.

## Canonical location and Git

- Repository: `/home/phobos/Projects/wd2-screensaver` (**capital P**).
- Runtime: `~/.local/share/wd2-screensaver` is a symlink to that repository.
- `~/projects` was an accidental lowercase location and has been removed.
- GitHub: `https://github.com/nbfrodri/wd2-screensaver`, verified **private**.
- Branch: `main`; inspect `git status` and `git log` before editing.
- The installed launcher is `~/.local/bin/wd2-launch-screensaver`.
- The repository copies the launcher/plugin under `integration/`; changing
  those copies does not update their installed equivalents automatically.
- Do not read credentials or upload runtime data. The repo ignores caches/logs.

## User intent and visual rules

The user likes TEXTWALL's detail and WRENCH's closing animation. They want all
scenes richly textured **and recognizable**, not a flood of bright noise.
TRAFFIC was especially weak before its rebuild. Every mode now has a farewell.
DOTMATRIX must preserve the black/white dotted wallpaper style, form DEDSEC,
and have more character than a generic bitmap font. More effects should have
a coherent purpose rather than filling the negative space indiscriminately.

- No readable fake hacking source code. Artistic labels and existing game-style
  displays are distinct from code dumps; don't add pretend scripts.
- Printable single-width characters only in screensaver cells. No emoji/CJK,
  combining marks or terminal control characters from external text.
- Notifications: **count only, never read their contents**.
- Audio analysis stays in memory; no recordings.
- Weather uses the Omarchy widget's location and `wttr.in`; document that
  external request and keep its toggle.
- Do not modify `/usr/share/omarchy`; it is read-only reference material.
- Read the installed Omarchy skill before desktop/config changes:
  `/home/phobos/.codex/skills/omarchy/SKILL.md` and relevant topic guide.
- User authorized multiagents with **gpt-6.1-sol, low** if useful. The agents
  used in this pass have finished; there are no outstanding delegated edits.

## What this polish pass changed

1. `mode_dotmatrix.py`: custom 9x13 angular, slightly slanted stencil DEDSEC
   letters, open counters and deliberate cuts. Replaced the generic 5x7 word.
   A dotted contact arc fires between the fingers around 2.6 seconds (the
   previous spark condition never coincided with the hands phase). Detached,
   dim broken ellipse fragments frame the held word with slow rotation and a
   traveling tracer. They fade over 0.7 seconds at entry/exit, and participate
   in the closing collapse. Still strictly grayscale on black.
2. `mode_traffic.py`: reduced asphalt speckle and sidewalk tile contrast;
   fewer occupied windows with restrained warm/cool lighting. Cars, zebra
   crossings and building silhouettes now stand out better. Geometry remains.
3. `mode_drone.py` shared `BoxCity`: quieter edges, gently brighter filled
   faces, fewer windows in compact screens, facade strokes only when large
   enough. PROFILER also uses this renderer and was checked for regressions.
4. `mode_tower.py`: quieter ground avenues, facade braces and ambient windows;
   reduced compact-screen window density. Hacked floors retain pink identity.
5. `tools/preview.py`: portable headless PNG contact sheets, multiple phases,
   optional Pillow. Braille drawn manually as dots. Approximation of terminal
   raster, **not** proof of actual Ghostty font/rendering behavior.
6. README now records the capital-`Projects` location. `requirements-dev.txt`
   adds Pillow for the optional preview tool.

## Self-review: remaining issues and priority

Observations below are visual judgments from headless previews, primarily the
90x26 contact sheet at about 12 seconds and affected-mode 175x45 previews.
They are not a claim that every phase is visually correct on the real desktop.

| Mode | What reads well | Remaining improvement |
| --- | --- | --- |
| DOTMATRIX | Hands silhouette, DEDSEC counters, grayscale restraint | At mid-morph the points become a fairly uniform cloud; introduce structured streams or staggered letter assembly without losing hand continuity. Word hold still has a quiet narrative. Consider a custom emblem made from the same points, with a long readable hold, rather than more random particles. |
| TRAFFIC | Solid intersection, roofs, car colors, clear zebra strips | Motion still uses modulo positions and clamps cars near stop lines; queues can snap instead of braking. Pedestrians change crossing layout rather than traversing naturally. Introduce persistent vehicle/pedestrian positions and smooth acceleration/arrival with spacing. Keep static depth buffer and draw order sound. |
| DRONE | Building masses improved; horizon and depth evident | Night street is too dark; roof/edge strokes and rain still compete. Bright horizontal scan/horizon bands can obscure buildings. Establish visible road planes/curbs and restrained scan opacity. Check tunnels, corners and full route, not only one frame. |
| TOWER | Main blue tower now separate from city | Attack beams, firewall rings and scan bands still obscure the core; selectively reduce opacity/brightness when crossing the building. Camera framing can crop tower top/bottom; test all phases before changing it. |
| NUDLE | Pink identity and location pins | High-priority readability candidate: ground/facade texture and repeated pink markers resemble confetti at 90x26. Give each campus volume a distinct silhouette, quiet the ground, and prevent overlapping labels. |
| SCOUTX | Social framing | Large saturated pink sky dominates and the landmark silhouette is ambiguous in compact preview. Work on landmark proportions, material contrast and less saturated supporting surfaces. |
| PROFILER | Card/profile is immediately clear | City behind card was visually busy; shared BoxCity change helps. Preserve card contrast, avoid edge/window interference around its border. |
| BOTNET | Globe and connections recognizable | Labels overlap globe geometry, small relays ambiguous; reduce label density adaptively and give satellites a few strong recognizable features. |
| HOLOGRAM | Mask and projector clear | Side particles compete with outline; projection shimmer can erase facial features. Preserve eye/lens/cheek landmarks through interference. |
| GOLDENGATE | Bridge silhouette clear | Reflections are chunky bright rectangles in compact preview; tie glints to water perspective and tower reflection shapes rather than adding more flecks. |
| HACKERSPACE | Room volume and foreground furniture | Small props can be ambiguous; refine recognizable object proportions and occlusion before adding texture. Heavy renderer, don't add unbounded per-frame detail. |
| TEXTWALL | Graffiti and brick relief strong; user likes this | Preserve paint/brick contrast. Very large screens exceed target FPS. Avoid sacrificing this mode's detail just to add other effects. |
| WRENCH | Mask and LED eyes readable; closing animation liked | Dense skin may compete with lenses; keep contours and LED expressions clear. Large screens exceed target FPS. Preserve the existing farewell. |
| DEDSEC (`mode_logo`) | Large dimensional logo recognizable | Supporting icons/tickers can steal attention. Keep a long stable logo hold and restrained layers; don't introduce readable fake code. |

Suggested next work: (1) NUDLE/SCOUTX silhouette pass, (2) smooth TRAFFIC motion,
(3) DOTMATRIX structured morph/emblem, (4) DRONE/TOWER occlusion/framing.
Do a few scenes well and validate each; don't blanket-add noise to all 14.

## Validation and useful commands

Use `/usr/bin/python3` for tools. The shell's `python3` is mise Python and lacks
NumPy. `dedsec.py` itself now re-execs system Python when NumPy is missing;
the headless tools expect their dependencies in the interpreter you choose.

```bash
cd /home/phobos/Projects/wd2-screensaver
/usr/bin/python3 dedsec.py --list
/usr/bin/python3 dedsec.py dotmatrix
/usr/bin/python3 tools/verify.py --full --mode mode_dotmatrix
/usr/bin/python3 tools/verify.py --full --mode mode_traffic
/usr/bin/python3 tools/snap.py mode_traffic 175 45 240
/usr/bin/python3 tools/preview.py --mode mode_dotmatrix --times 0 2.6 6 12 26 31 --output /tmp/dotmatrix.png
/usr/bin/python3 tools/preview.py --mode mode_nudle --times 0 12 30 --output /tmp/nudle.png
```

This pass: full 80-second timeline plus farewell tests passed for DOTMATRIX,
TRAFFIC, DRONE, TOWER and PROFILER at **90x26, 175x45 and 240x60**. DOTMATRIX
orbit fade/tracer follow-up passed boundary/farewell smoke checks. New preview
tool ran on six DOTMATRIX phases; reviewed hands, contact, morph, word, return.
Final `tools/snap.py mode_dotmatrix 175 45 240`: **9.1 ms/frame** including
mode drawing and ANSI rendering, measured after the orbit follow-up.
Before this pass all 14 modes passed the 42-size smoke suite and the prior
full timeline/farewell checks. No new live desktop test was performed this pass.

`tools/verify.py` doesn't start desktop actions or live data; it tests execution,
rendering and cell width, not subjective visual correctness. `tools/snap.py`
reports mode+render timing. Previous typical 175x45 costs: TEXTWALL ~27ms,
WRENCH ~32ms; at 240x60 ~56/57ms, above 24fps's 41.7ms budget. Never present
the agent's DOTMATRIX step+snapshot measurement as equivalent to snap timing.

Temporary previews may disappear: `/tmp/wd2-detail` contains this pass's sheets
and older comparisons, but reproduce them with the checked-in tool instead of
depending on those paths. PNG previews do not need to go into GitHub by default.

## Omarchy wiring and installer

See `docs/installation.md`, `docs/architecture.md`, `docs/validation.md`.
The cloned idle service is `~/.config/omarchy/plugins/phobos.idle`; stock
`omarchy.idle` is disabled. Current idle saver/lock defaults are 150/300 seconds.
Menu override: `~/.config/omarchy/extensions/omarchy-menu.jsonc`, entry
`system.screensaver`. Full launcher uses `/usr/bin/python3` and terminal class
`org.omarchy.screensaver`. The saver is not a security lock; Omarchy lock is
separate. `scripts/install.py` defaults to dry-run, merges relevant settings,
backs up existing targets, and only writes with `--apply`. It normalizes menu
JSONC and removes comments; be aware when applying.

The wallpaper reference is `~/.local/state/omarchy/current/background`
(currently `0-dot-hands.jpg`). Runtime uses only bundled offline centroids in
`assets/dot_hands.json`, not wallpaper access or regenerated images.

For a live check, first inspect existing saver windows and don't kill a user's
existing instance. Closing a managed test saver can close all saver-class
windows. Sandbox access to Hyprland sockets may require an allowed escalation.
Do not restart the shell or change config merely to preview source changes;
the next saver process loads the edited modules.
