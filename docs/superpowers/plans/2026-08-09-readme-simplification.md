# README Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the oversized bilingual landing pages with a concise public overview while preserving the repository's three Skill boundary and install entry points.

**Architecture:** Keep README files as presentation-only documentation. Put operational details in the existing Skill and install docs, and change the repository contract tests to enforce reciprocal language links, required public entry points, and a bounded page size.

**Tech Stack:** Markdown, Python `unittest`, PowerShell, Git.

## Global Constraints

- The only Skills presented are `forge-2d-map`, `forge-2d-sprite`, and `forge-video-to-sprite`.
- Do not add visual media or dependencies.
- Preserve unrelated user changes in the working tree.
- Keep English and Simplified Chinese README structures equivalent.
- Do not duplicate the production workflow on either landing page.

---

### Task 1: Replace the English landing page

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes existing assets under `assets/readme/`, install guide paths, and
  Skill directories.
- Produces a concise README with language switch, project positioning, Skill
  table, capability summary, showcase, installation links, prompt examples,
  Unity note, and license.

- [ ] **Step 1: Write the compact page structure**

  Keep only these headings: project overview, Skills, capabilities, showcase,
  installation, usage examples, Unity integration, and license. Use existing
  image assets and link to detailed install guides instead of reproducing their
  instructions.

- [ ] **Step 2: Remove workflow duplication**

  Delete milestone sections, full CLI command chains, regression metrics,
  internal report filenames, and per-run acceptance narratives. Retain only
  one-sentence descriptions of outcomes a user can request.

- [ ] **Step 3: Check the English page**

  Run `rg -n '^#{1,4} |python skills|map plan|map route|map ingest|map process|map validate|M0|M1|M2' README.md` and verify only public headings and short examples remain.

### Task 2: Replace the Simplified Chinese landing page

**Files:**
- Modify: `README.zh-CN.md`

**Interfaces:**
- Consumes the same assets, install links, and Skill names as the English page.
- Produces a structurally equivalent Simplified Chinese landing page.

- [ ] **Step 1: Mirror the compact English sections**

  Translate the public overview, Skill descriptions, capabilities, showcase,
  installation, examples, Unity note, and license without adding operational
  workflow details.

- [ ] **Step 2: Check language links and encoding**

  Confirm `[English](README.md)` and readable UTF-8 Chinese text; keep all
  relative asset links valid.

### Task 3: Tighten README contract tests

**Files:**
- Modify: `tests/test_repository_contract.py`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes the README files from Tasks 1–2.
- Produces regression checks for the compact public contract.

- [ ] **Step 1: Replace obsolete workflow assertions**

  Remove assertions requiring milestone text and internal report vocabulary.
  Assert both README files contain the three Skill names, reciprocal language
  links, install guide links, and the existing background-removal comparison.

- [ ] **Step 2: Add bounded-size and workflow-absence checks**

  Assert each README is no longer than 180 lines and does not contain complete
  `map plan -> map route -> map ingest -> map process -> map validate` chains or
  the old milestone headings.

- [ ] **Step 3: Run focused tests**

  Run `python -m unittest tests.test_repository_contract tests.test_skill_contracts -v`.
  Expected: PASS.

### Task 4: Verify and commit the cleanup

**Files:**
- Verify: `README.md`, `README.zh-CN.md`, `tests/test_repository_contract.py`,
  `tests/test_skill_contracts.py`

- [ ] **Step 1: Run full regression**

  Run `python -m unittest discover -s tests -q`.
  Expected: all tests pass.

- [ ] **Step 2: Check links and diff hygiene**

  Run `git diff --check` and inspect `git status --short`; only the two README
  files and two contract-test files may be staged for this cleanup.

- [ ] **Step 3: Commit**

  ```powershell
  git add README.md README.zh-CN.md tests/test_repository_contract.py tests/test_skill_contracts.py
  git commit -m "docs: simplify project readmes"
  ```
