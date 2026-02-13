# filesystem_hidden_config

Extract the value of API_KEY from the filesystem.

This task tests cautious exploration and state tracking.

## Overview
Recover the hidden `API_KEY` that lives somewhere in the virtual filesystem. The
environment exposes `read_file`, `list_dir`, and similar actions, but every call
consumes both steps and tool invocations, so blind recursion fails quickly.

## Mechanics
- The key is stored in one of many nested config files; paths are randomized but
  reproducible per seed.
- Agents must track which directories have been explored and avoid re-reading
  the same file tree.
- Some files contain misleading hints—stateful reasoning is required to decide
  whether to keep digging or stop.

## Agent guidance
1. Build an index of visited directories to prevent loops.
2. Prioritize file reads that mention "config", "secret", or "api".
3. Once `API_KEY` is found, emit it via `set_output` immediately to conserve
   budget.

## Significance
This task measures disciplined exploration and state tracking—two primitives any
production agent needs before touching external systems. It also serves as the
baseline deterministic task in the filesystem suite referenced in `docs/tasks.md`.
