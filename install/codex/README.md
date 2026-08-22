# Install Game Visual Forge Skills in Codex

Codex core installation is delegated to the shared
[Agent guide](../agent/README.md).

Use that guide to install only the four core Skills:

- `forge-2d-map`
- `forge-2d-sprite`
- `forge-video-to-sprite`
- `forge-text-audio`

Codex discovery notes:

- Prefer linked Skill directories under `$HOME/.agents/skills`.
- Keep the full repository available with shared `src/`, `pyproject.toml`,
  and the linked Skill directories; links are supported, isolated copies of one
  Skill are not.
- `agents/openai.yaml` is Codex discovery metadata only; executable behavior
  still comes from each `SKILL.md` plus the shared Python package in `src/`.

Authority boundary:

- This Codex entrypoint authorizes the shared Agent guide's core install only.
- Optional workflows are not part of the core install.
- When optional ComfyUI MiniMax H3, MiniMax Hailuo, Jimeng, CLI compatibility,
  or Stable Audio 3 setup is requested, follow the shared Agent guide's
  separate enable, inspect, plan, and confirm flow.
