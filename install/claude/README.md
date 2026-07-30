# Install Game Visual Forge Skills in Claude

This M0 repository ships three manual Skills:

- `generate-2d-sprite`
- `generate-2d-map`
- `video-to-2d-sprite`

Manual install only:

- Supported workflow A: repository-local use. Keep this repository root intact and use its existing `skills/` and `src/` layout directly if your Claude setup supports repository-local Skills.
- Supported workflow B: copy the full repository layout into a new root that preserves the shared runtime. At minimum, copy all three directories under `skills/`, the repository `src/` tree, and the required package files such as `pyproject.toml`, `README.md`, and any referenced docs/examples you want to keep with the copied root.
- Copying only an individual Skill directory is not executable by itself unless you also provide a matching `src/` tree and package layout that the launcher can resolve.
- Restart the Claude session or task after the repository-local setup or full repository copy so Skill discovery reloads.

Authority and compatibility notes:

- `SKILL.md` is the authoritative instruction file for Claude.
- `agents/openai.yaml` is ignored by Claude. It may remain in a copied full repository for Codex-side metadata compatibility, but Claude does not use it to execute the Skill.

M0 safety limits:

- This install flow does not install dependencies, providers, FFmpeg, rembg, or credentials.
- It does not write into your profile automatically.
- It does not require Codex-specific metadata for Claude to read the Skill instructions.

After installation, verify from the repository with commands such as:

```powershell
python -m unittest discover -s tests -v
python skills/video-to-2d-sprite/scripts/run.py --help
```
