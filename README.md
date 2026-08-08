# Game Visual Forge

English | [简体中文](README.zh-CN.md)

Game Visual Forge is a repository-local collection of three Codex Skills for
game-ready 2D visual assets: maps, sprites, and video-to-sprite animation.
Ask in natural language; the selected Skill turns the request into a validated
asset bundle or an engine-ready handoff.

## Skills

| Skill | Use it for | Typical output |
| --- | --- | --- |
| [`forge-2d-map`](skills/forge-2d-map/SKILL.md) | Playable 2D maps, Tilemaps, terrain, props, collision, and Unity handoff | Map bundle, preview, placement data, quality evidence |
| [`forge-2d-sprite`](skills/forge-2d-sprite/SKILL.md) | Characters, creatures, NPCs, props, effects, and animation sheets | Clean sprite sheets, frames, GIF previews, metadata |
| [`forge-video-to-sprite`](skills/forge-video-to-sprite/SKILL.md) | Turning a selected video or generated motion clip into dense sprite frames | Extracted frames, sprite strips, GIF previews, metadata |

## What it provides

- Natural-language intake with explicit choices for style, layout, runtime, and
  delivery format.
- Built-in image generation when a new visual asset is needed, plus support for
  user-provided source media.
- Deterministic local processing, validation reports, and reproducible output
  manifests.
- Playable map handoff with walkability, collision, objects, entrances, and
  Unity Tilemap support.
- Provider, cost, and submission confirmation gates for paid or external work.

## Showcase

### Playable map handoff

![Adaptive river crossing map in Unity](assets/readme/adaptive-river-crossing-map-unity-game-view.png)

The map example includes a Tilemap bundle, separate layers, bridge
connectivity, collision data, and Unity acceptance evidence.

### HD sprite cleanup

![HD background removal comparison](assets/readme/rembg-production-comparison-on-gray.jpg)

The local processor exports transparent assets and records the cleanup result.

## Install

Use the repository locally or follow the platform-specific guide:

- [Codex installation](install/codex/README.md)
- [Claude installation](install/claude/README.md)

The install guides are manual and repository-local. They do not install
providers, FFmpeg, credentials, or dependencies automatically.

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

## Unity integration

The Unity package lives at
[`integrations/unity/com.game-visual-forge.tilemap`](integrations/unity/com.game-visual-forge.tilemap).
It imports a validated Tilemap bundle into reusable textures, Tiles, Palette,
and Tilemap Prefab assets. The package includes EditMode and PlayMode tests.

## Repository layout

```text
skills/       Codex Skill instructions and launchers
src/          Shared contracts, routing, processing, and reports
integrations/ Unity Tilemap package and tests
assets/       Small checked-in examples and showcase artifacts
install/      Manual setup guides
```

## Development check

```powershell
python -m unittest discover -s tests -q
```

## License

[MIT](LICENSE)
