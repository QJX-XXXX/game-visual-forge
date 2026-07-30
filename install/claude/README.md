# Install Game Visual Forge Skills in Claude

This M0 repository ships three manual Skills:

- `generate-2d-sprite`
- `generate-2d-map`
- `video-to-2d-sprite`

Manual install only:

- Copy each directory under `skills/` into the personal or repository-local Claude Skills location you use.
- Keep this repository available after the copy. The launcher scripts resolve the shared repository `src/` package at runtime.
- If your Claude setup supports repository-local Skills, you can keep the `skills/` directories in this repository instead of copying them elsewhere.
- Restart the Claude session or task after the copy so Skill discovery reloads.

Authority and compatibility notes:

- `SKILL.md` is the authoritative instruction file for Claude.
- `agents/openai.yaml` is ignored by Claude and is present only for Codex-side metadata compatibility in this repository.

M0 safety limits:

- This install flow does not install dependencies, providers, FFmpeg, rembg, or credentials.
- It does not write into your profile automatically.
- It does not require Codex-specific metadata for Claude to read the Skill instructions.

After installation, verify from the repository with commands such as:

```powershell
python -m unittest discover -s tests -v
python skills/video-to-2d-sprite/scripts/run.py --help
```
