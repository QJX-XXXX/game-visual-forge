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
