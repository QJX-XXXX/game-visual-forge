# English-Only Skill Packages Design

## Goal

Make every public skill package in `game-visual-forge` consistently English so installed or cloned skills are easy to validate, maintain, and use across locales. Chinese user documentation remains available only through the repository README pair.

## Scope

This change covers the three supported skill packages:

- `skills/forge-2d-map`
- `skills/forge-2d-sprite`
- `skills/forge-video-to-sprite`

Every human-readable file inside those packages must use English. This includes `SKILL.md`, Markdown references, `agents/openai.yaml`, and comments or user-facing strings in bundled Python launchers. Identifiers, command names, JSON keys, provider names, and paths remain unchanged.

The public README policy remains:

- `README.md` is English.
- `README.zh-CN.md` may contain Chinese.

Historical specifications, implementation plans, tests, fixtures, generated evidence, and external tool files outside `skills/` are not rewritten by this change.

## Translation Rules

Translate meaning rather than wording. Preserve every workflow requirement, safety rule, approval gate, command example, artifact name, provider choice, and validation condition.

Specific changes are:

- Translate the remaining Chinese provider-safety paragraph in `forge-2d-map/SKILL.md` into concise imperative English.
- Translate the complete body of `forge-2d-sprite/SKILL.md` into concise imperative English, including grouped intake, source routing, paid confirmation, CLI commands, and the six-check visual-review contract.
- Keep `forge-video-to-sprite/SKILL.md` and its English references semantically unchanged except for any consistency edits required by validation.
- Keep all three YAML frontmatter descriptions and `agents/openai.yaml` interfaces in English.

No command, schema, output path, provider behavior, or runtime implementation changes are authorized.

## Enforcement

Extend `tests/test_skill_contracts.py` with an English-only contract. It scans UTF-8 text files under each supported skill package with extensions `.md`, `.yaml`, `.yml`, and `.py` and fails if it finds characters in the following Unicode ranges:

- CJK Unified Ideographs and Extension A: `U+3400–U+4DBF`, `U+4E00–U+9FFF`
- Hiragana and Katakana: `U+3040–U+30FF`
- Hangul syllables: `U+AC00–U+D7AF`

The test reports the relative path containing the violation. This makes the English-only rule apply automatically to future skills and future edits under `skills/`.

Existing fragment assertions for `forge-2d-map` and `forge-2d-sprite` must be rewritten in English so they continue to protect the same workflow and safety guarantees.

## Validation

The change is accepted only when all of the following pass from a clean committed checkout:

1. `python -m unittest tests.test_skill_contracts -v`
2. `python -X utf8 .../quick_validate.py` for each of the three skill folders
3. `python skills/<skill>/scripts/run.py --help` for each launcher
4. `python -m unittest discover -s tests -q`
5. A repository search confirms no `generate2dmap` or `agent-sprite-forge` references in public skills, source, tests, or READMEs

Pillow deprecation warnings are non-blocking if every test passes; no new warning or dependency is introduced by this documentation-only change.

## Acceptance Criteria

- All three `SKILL.md` files are English.
- All human-readable files in the three skill packages are English.
- The map, sprite, and video workflows retain their existing behavior and safety semantics.
- Future non-English text under `skills/` fails the skill-contract test.
- Chinese remains available through `README.zh-CN.md` only within the public documentation surface.
- The clean-checkout test suite and all three skill validators pass.
