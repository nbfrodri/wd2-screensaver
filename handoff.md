# Handoff for Claude — WD2 screensavers

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
