# Install Game Visual Forge Skills in Codex

This M0 repository ships three manual Codex Skills:

- `generate-2d-sprite`
- `generate-2d-map`
- `video-to-2d-sprite`

Manual install only:

- Supported workflow A: repository-local use. Keep this repository root intact and use its existing `skills/` and `src/` layout directly if your Codex workspace supports repository-local Skills.
- Supported workflow B: copy the full repository layout into a new root that preserves the shared runtime. At minimum, copy all three directories under `skills/`, the repository `src/` tree, and the required package files such as `pyproject.toml`, `README.md`, and any referenced docs/examples you want to keep with the copied root.
- Copying only an individual Skill directory is not executable by itself unless you also provide a matching `src/` tree and package layout that the launcher can resolve.
- Restart the Codex task or session after the repository-local setup or full repository copy so Skill discovery reloads.

M0 safety limits:

- This install flow does not install dependencies, providers, FFmpeg, rembg, or credentials.
- It does not write into your profile automatically.
- It does not create a Codex Plugin and does not require `.codex-plugin/`.
- `agents/openai.yaml` is Codex discovery metadata only. The executable behavior still comes from each `SKILL.md` plus the shared Python package in `src/`.

After installation, keep using repository-local commands for verification, for example:

```powershell
python -m unittest discover -s tests -v
python skills/generate-2d-sprite/scripts/run.py --help
```
