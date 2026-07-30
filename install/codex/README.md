# Install Game Visual Forge Skills in Codex

This M0 repository ships three manual Codex Skills:

- `generate-2d-sprite`
- `generate-2d-map`
- `video-to-2d-sprite`

Manual install only:

- Copy each directory under `skills/` into the Codex Skills location you choose for your machine or workspace.
- Keep this repository available after the copy. The launcher scripts resolve the shared repository `src/` package at runtime.
- If your current Codex workspace supports repository-local Skills, you can keep the `skills/` directories in this repository instead of copying them elsewhere.
- Restart the Codex task or session after the copy so Skill discovery reloads.

M0 safety limits:

- This install flow does not install dependencies, providers, FFmpeg, rembg, or credentials.
- It does not write into your profile automatically.
- It does not create a Codex Plugin and does not require `.codex-plugin/`.
- `agents/openai.yaml` is metadata for Codex discovery only; the Skill behavior remains defined by each `SKILL.md` plus the shared Python package in `src/`.

After installation, keep using repository-local commands for verification, for example:

```powershell
python -m unittest discover -s tests -v
python skills/generate-2d-sprite/scripts/run.py --help
```
