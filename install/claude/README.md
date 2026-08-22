# Install Game Visual Forge Skills in Claude

Claude core installation is delegated to the shared
[Agent guide](../agent/README.md).

Use that guide to install only the four core Skills:

- `forge-2d-map`
- `forge-2d-sprite`
- `forge-video-to-sprite`
- `forge-text-audio`

Claude discovery notes:

- `SKILL.md` remains the authoritative instruction file for Claude.
- `agents/openai.yaml` remains in the repository for Codex compatibility and
  should stay alongside the Skill package.
- Prefer `$HOME/.agents/skills` when the current Claude environment supports
  it; otherwise use the current Claude-supported Skill discovery directory while
  preserving links back to the intact repository root with shared `src/`.

Authority boundary:

- This Claude entrypoint authorizes the shared Agent guide's core install only.
- Optional workflows are not part of the core install.
- When optional ComfyUI MiniMax H3, MiniMax Hailuo, Jimeng, CLI compatibility,
  or Stable Audio 3 setup is requested, follow the shared Agent guide's
  separate enable, inspect, plan, and confirm flow.
