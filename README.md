# Game Visual Forge

English | [简体中文](README.zh-CN.md)

Game Visual Forge is a repository-local collection of four Codex Skills for
game-ready 2D visual assets and explicitly requested game audio: maps, sprites,
video-to-sprite animation, and reviewed sound effects.

## Skills

| Skill | Use it for | Typical output |
| --- | --- | --- |
| [`forge-2d-map`](skills/forge-2d-map/SKILL.md) | Playable 2D maps, Tilemaps, terrain, props, collision, and Unity handoff | Map bundle, preview, placement data, quality evidence |
| [`forge-2d-sprite`](skills/forge-2d-sprite/SKILL.md) | Characters, creatures, NPCs, props, effects, and animation sheets | Clean sprite sheets, frames, GIF previews, metadata |
| [`forge-video-to-sprite`](skills/forge-video-to-sprite/SKILL.md) | Turning a selected video or generated motion clip into dense sprite frames | Extracted frames, sprite strips, GIF previews, metadata |
| [`forge-text-audio`](skills/forge-text-audio/SKILL.md) | Explicitly requested SFX, UI sounds, action sounds, and ambience | Reviewed 44,100 Hz 16-bit PCM WAV and Unity AudioClip manifest |

## What it provides

- Natural-language intake with explicit choices for style, layout, runtime, and delivery format.
- Built-in image generation when a new visual asset is needed, plus support for user-provided source media.
- Deterministic local processing, validation reports, and reproducible output manifests.
- Playable map handoff with walkability, collision, objects, entrances, and Unity Tilemap support.
- Native map atlases are normalized to the declared grid, tile size, margins, and spacing before validation. This standardizes atlas geometry only; it does not repair artwork, seams, or map topology.
- Provider, cost, and submission confirmation gates for paid or external work.
- `forge-video-to-sprite` processes existing video locally with FFmpeg/FFprobe, timestamp sampling, rembg/Chroma cleanup, stable alignment, strips, sheets, GIF previews, and motion-quality evidence.
- Generated video routes support explicit MiniMax Hailuo or Jimeng selection with either their API or official CLI compatibility backend; tools and credentials are configured manually and never switched automatically.
- `forge-text-audio` uses the official local Stable Audio 3 `small-sfx` model through the isolated `stable-audio-3` runtime. It supports text-to-audio, redraw, inpaint, and continue modes, with WAV-only delivery and a final listening review.

## Showcase

![Adaptive river crossing map in Unity](assets/readme/adaptive-river-crossing-map-unity-game-view.png)

![HD background removal comparison](assets/readme/rembg-production-comparison-on-gray.jpg)

HD cleanup uses Pillow for image conversion, NumPy/SciPy for masks, rembg with
the `birefnet-general` model for semantic separation, known-magenta spill
reconstruction, and optional PyMatting refinement. If CUDA fails, the processor
tries CPU and reports a deterministic Chroma fallback when needed.

Install optional cleanup tools manually:

```powershell
python -m pip install -e ".[image]"
python -m pip install -e ".[background]"
python -m pip install "rembg[cpu]"
python -m pip install "rembg[gpu]"
python -m pip install -e ".[matting]"
python -c "from rembg import new_session; new_session('birefnet-general')"
```

Use `U2NET_HOME` for a shared model directory. CPU is the compatibility default;
GPU requires a verified CUDA environment. PyMatting is optional and slower.

### Stable Audio 3 examples

Generated with `forge-text-audio` and the official
`stabilityai/stable-audio-3-small-sfx` model.

#### Wooden UI click

Prompt:

```text
Dry wooden UI click, short transient, no music, no voice
```

[Listen to the wooden UI click](assets/readme/stable-audio-3-small-sfx-wooden-ui-click.wav)

![Stable Audio 3 wooden UI click waveform](assets/readme/stable-audio-3-small-sfx-wooden-ui-click-waveform.png)

![Stable Audio 3 wooden UI click spectrum](assets/readme/stable-audio-3-small-sfx-wooden-ui-click-spectrum.png)

#### Blacksmith hammer sound

Prompt:

```text
TrackType: SFX, a clean professional studio Foley recording of one natural strike of a small steel blacksmith hammer against a red-hot iron billet on a solid anvil, an isolated metallic impact with a fast attack and a short clean natural decay, recorded with a dry close microphone in a quiet room.
```

- [Listen to blacksmith hammer candidate 1](assets/readme/stable-audio-3-small-sfx-blacksmith-hammer-01.wav)
- [Listen to blacksmith hammer candidate 2](assets/readme/stable-audio-3-small-sfx-blacksmith-hammer-02.wav)
- [Listen to blacksmith hammer candidate 3](assets/readme/stable-audio-3-small-sfx-blacksmith-hammer-03.wav)

## Install

- [Codex installation](install/codex/README.md)
- [Claude installation](install/claude/README.md)
- [Stable Audio 3 setup](install/stable-audio-3/README.md)

The install guides are manual and repository-local. They do not install
providers, FFmpeg, credentials, model weights, or dependencies automatically.

To delegate the optional audio runtime setup to an Agent, copy this request:

> Install and configure the official stable-audio-3 runtime for forge-text-audio: ask me to choose the installation directory, keep the isolated Python environment, model weights, and all caches under that directory, require me to accept all licenses personally, never use a hosted API, run the repository's provider configure command without changing user environment variables or PATH, and finish by running and reporting the local offline preflight.

Detailed instructions are in [Stable Audio 3 setup](install/stable-audio-3/README.md). The ignored `game-visual-forge.local.json` stores only local paths; `provider configure` creates it. License acceptance remains a user action.

## Example requests

```text
Use forge-2d-map to create a top-down village with a north-south creek,
one walkable wooden bridge, building entrances, collision, and a Unity Tilemap.
```

```text
Use forge-2d-sprite to create a modern pixel-art player walk sheet with
transparent output and a preview GIF.
```

```text
Use forge-video-to-sprite with my existing MP4 and export a feet-aligned
24-frame sprite strip plus a preview GIF.
```

```text
Use forge-text-audio to create three dry iron-sword impacts against a steel
shield, no music or voice, review the candidates, and prepare a Unity AudioClip.
```

For local video processing, install FFmpeg and FFprobe yourself. MiniMax API
uses `MINIMAX_API_KEY`; Jimeng API uses `JIMENG_ACCESS_KEY` and
`JIMENG_SECRET_KEY`. The official `mmx` and `dreamina` CLIs are optional.

## Unity integration

The Tilemap package lives at
[`integrations/unity/com.game-visual-forge.tilemap`](integrations/unity/com.game-visual-forge.tilemap)
and imports validated Tilemap bundles into textures, Tiles, Palettes, and
Tilemap Prefabs. The independent audio package lives at
[`integrations/unity/com.game-visual-forge.audio`](integrations/unity/com.game-visual-forge.audio)
and imports reviewed WAV bundles as configured AudioClip assets without changing
scenes. Scene placement is performed through Unity MCP only after an explicit request.

## Repository layout

```text
skills/       Codex Skill instructions and launchers
src/          Shared contracts, routing, processing, and reports
integrations/ Unity Tilemap and audio packages plus tests
assets/       Small checked-in examples and showcase artifacts
install/      Manual setup guides
```

## Development check

Run the test suite from the repository root (the directory that contains `tests/`):

```powershell
Set-Location "game-visual-forge项目路径"
python -m unittest discover -s tests -q
```

## License

[MIT](LICENSE)
