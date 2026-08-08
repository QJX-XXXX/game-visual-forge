# README Simplification Design

**Date:** 2026-08-09  
**Status:** Approved for implementation

## Goal

Make the English and Simplified Chinese project landing pages concise, tidy,
and useful to a first-time visitor. The README files describe what Game Visual
Forge is and how to start using it; detailed production procedures remain in
the Skill and installation documentation.

## Information architecture

`README.md` and `README.zh-CN.md` use the same compact structure:

1. Project name, language switch, and one-paragraph positioning.
2. A table for the three repository-owned Skills.
3. A short list of core capabilities and safeguards.
4. A small visual showcase using existing repository assets.
5. Manual installation links for Codex and Claude.
6. One natural-language invocation example per Skill.
7. A short Unity integration note and the MIT license link.

## Content removed from the landing pages

- milestone-by-milestone implementation history;
- complete planning, routing, ingestion, processing, and validation command
  sequences;
- internal request, report, and regression-fixture details;
- long case-study acceptance logs and per-run metrics;
- dependency implementation notes already owned by Skill or install docs.

The README files may link to detailed documentation, but they do not duplicate
the production workflow.

## Repository boundaries

- The only Skills presented are `forge-2d-map`, `forge-2d-sprite`, and
  `forge-video-to-sprite`.
- Existing assets are reused; this change generates no new visual media.
- Existing user changes outside the two README files and their repository
  contract test are preserved.
- English and Simplified Chinese pages remain reciprocal translations with
  working language links.

## Contract tests

Update the repository README tests to assert the compact public contract:

- reciprocal language links;
- all three Skill names;
- installation-guide links;
- the existing background-removal comparison asset;
- absence of internal workflow command sequences and milestone headings;
- a reasonable maximum README line count to prevent future expansion.

Run the full Python test suite and Markdown link/path checks before committing
the implementation.

## Approved revision: HD sprite cleanup detail

The compact landing-page structure remains unchanged, but the HD sprite cleanup
showcase must explain enough for a user to understand and install the feature.
Both README files add the same four-part summary:

1. **Tool chain and advantages.** Name Pillow, NumPy/SciPy, rembg with the
   default `birefnet-general` model, known-background reconstruction,
   deterministic chroma fallback, and optional PyMatting. Explain that semantic
   segmentation preserves soft foreground detail, known-background processing
   reduces magenta fringe, CUDA falls back to CPU, and a deterministic chroma
   result remains available when model execution fails.
2. **Installation choices.** Document the repository extras and the rembg
   hardware backend separately:
   - local image operations: `python -m pip install -e ".[image]"`;
   - CPU HD cleanup: install `.[background]`, then `rembg[cpu]`;
   - NVIDIA/CUDA HD cleanup: install `.[background]`, then `rembg[gpu]` after
     checking the current ONNX Runtime/CUDA compatibility;
   - optional PyMatting: install `.[matting]` after choosing a rembg backend.
3. **Model cache.** Show how to initialize `birefnet-general` with
   `new_session`, explain that rembg stores local models under `U2NET_HOME` or
   the default `~/.u2net`, and state that this project does not install or
   download dependencies silently.
4. **Selection guidance.** Recommend CPU for compatibility, GPU for repeated
   high-resolution batches on a verified CUDA environment, chroma for fast
   deterministic solid-key input, and PyMatting only when difficult soft edges
   justify extra processing cost.

The detailed section should add roughly 30–40 lines per language and keep each
README below the existing 180-line contract. Repository tests must retain the
installation commands, default model name, CPU/GPU fallback description, and
optional PyMatting guidance.
