# Claude project context

Read and follow [AGENTS.md](AGENTS.md), then the latest section of
[handoff.md](handoff.md). Both apply to this repository. Preserve existing
uncommitted changes and check mode dependencies before rewriting exports.

The user wants richly detailed but recognizable DedSec/Watch Dogs 2 scenes,
not bright noise. Keep WRENCH's farewell, DOTMATRIX's grayscale dotted style
and legible DEDSEC lettering, printable single-width cells, and the documented
data privacy rules. Reply to the user in Spanish.

Use `/usr/bin/python3`; the shell's mise interpreter may not have NumPy.
Canonical path is `/home/phobos/Projects/wd2-screensaver`. The installed runtime
path is a symlink, so source edits affect the next screensaver launch.

Read [architecture](docs/architecture.md), [installation](docs/installation.md)
and [validation](docs/validation.md). Current review and measurements are in
[the October 2 polish report](docs/polish-2026-10-02.md).

For parallel tasks, assign disjoint files and gather test evidence. Keep shared
modules and integration ownership explicit. Run full mode/size/close checks and
review multiple visual phases; serial timing comes after agents stop rendering.
If limits interrupt work, update `handoff.md` with precise ownership, partial
edits and commands already completed rather than leaving only a task plan.

Commits use the configured user's identity when authorized. No coauthor or
assistant attribution trailers. Keep the repo private.
