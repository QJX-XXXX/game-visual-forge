# English-Only Skill Packages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert every public skill package to English and enforce that policy for current and future skills.

**Architecture:** Preserve all runtime contracts and translate only human-readable skill content. Extend the existing skill-contract suite with a recursive Unicode guard, then document the authoring policy in the English and Chinese READMEs.

**Tech Stack:** Markdown, YAML, Python 3.12 standard library (`re`, `pathlib`, `unittest`), existing skill launchers, and `quick_validate.py`.

## Global Constraints

- Every human-readable file under `skills/` uses English, including `SKILL.md`, Markdown references, `agents/openai.yaml`, and bundled Python comments or user-facing strings.
- `README.md` is English; `README.zh-CN.md` may contain Chinese.
- Preserve every workflow requirement, safety rule, approval gate, command example, artifact name, provider choice, and validation condition.
- Do not change commands, schemas, output paths, provider behavior, or runtime implementations.
- Reject CJK Unified Ideographs, Hiragana, Katakana, and Hangul in `.md`, `.yaml`, `.yml`, and `.py` files under every current or future skill folder.
- Do not rewrite historical specifications, implementation plans, tests, fixtures, generated evidence, or external tool files outside the exact files listed by each task.
- Do not stage the uncommitted adaptive-river-crossing bridge evidence already present in the primary worktree.

---

### Task 1: Translate and protect the map skill

**Files:**
- Modify: `skills/forge-2d-map/SKILL.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: `ROOT`, `unittest.TestCase`, and the existing `SKILLS["forge-2d-map"]` contract.
- Produces: `SkillContractTests.assert_skill_tree_is_english(skill_name: str) -> None` and a map package with no CJK characters.

- [ ] **Step 1: Add a failing English-only helper and map test**

Add `import re` and this module-level constant:

```python
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
```

Add these methods to `SkillContractTests`:

```python
def assert_skill_tree_is_english(self, skill_name: str) -> None:
    skill_root = ROOT / "skills" / skill_name
    for path in sorted(item for item in skill_root.rglob("*") if item.is_file() and item.suffix.lower() in {".md", ".yaml", ".yml", ".py"}):
        content = path.read_text(encoding="utf-8")
        match = CJK_PATTERN.search(content)
        self.assertIsNone(match, f"{path.relative_to(ROOT)} contains non-English text: {match.group(0) if match else ''}")

def test_map_skill_package_is_english(self) -> None:
    self.assert_skill_tree_is_english("forge-2d-map")
```

Replace the map safety fragments in `SKILLS` with:

```python
"required_body_fragments": (
    "native Agent tools",
    "Jimeng",
    "Wanxiang",
    "Ask the user to choose the provider, model, and parameters every time",
    "explicit paid confirmation",
    "Never install tools automatically",
    "Never resubmit",
),
```

- [ ] **Step 2: Run the focused test and verify the remaining map paragraph fails**

Run: `python -m unittest tests.test_skill_contracts.SkillContractTests.test_map_skill_package_is_english -v`

Expected: FAIL naming `skills/forge-2d-map/SKILL.md` and the first Chinese character in the provider-safety paragraph.

- [ ] **Step 3: Translate the map provider-safety paragraph exactly**

Replace the final paragraph with:

```markdown
Keep provider safety explicit: use native Agent tools, Jimeng, or Wanxiang only when the current request selects that source. Obtain explicit paid confirmation before every paid attempt. Ask the user to choose the provider, model, and parameters every time. Never install tools automatically, and never resubmit a failed or `submission_unknown` task. Keep native generation within the confirmed intake and candidate review.
```

- [ ] **Step 4: Run the map and complete skill-contract tests**

Run:

```powershell
python -m unittest tests.test_skill_contracts.SkillContractTests.test_map_skill_package_is_english -v
python -m unittest tests.test_skill_contracts -v
```

Expected: both commands PASS; all existing map workflow fragments remain protected.

- [ ] **Step 5: Commit the map translation and first language guard**

```powershell
git add -- skills/forge-2d-map/SKILL.md tests/test_skill_contracts.py
git commit -m "docs: translate forge 2d map skill to english"
```

---

### Task 2: Translate the sprite skill and generalize future enforcement

**Files:**
- Modify: `skills/forge-2d-sprite/SKILL.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: Task 1 `CJK_PATTERN` and `assert_skill_tree_is_english(skill_name: str) -> None`.
- Produces: `test_public_skill_packages_are_english()` that discovers every directory under `skills/` containing `SKILL.md`, plus a fully English sprite workflow.

- [ ] **Step 1: Generalize the language test and translate expected contract fragments**

Replace `test_map_skill_package_is_english` with:

```python
def test_public_skill_packages_are_english(self) -> None:
    skills_root = ROOT / "skills"
    skill_names = tuple(
        path.name
        for path in sorted(skills_root.iterdir())
        if path.is_dir() and (path / "SKILL.md").is_file()
    )
    self.assertEqual(skill_names, ("forge-2d-map", "forge-2d-sprite", "forge-video-to-sprite"))
    for skill_name in skill_names:
        with self.subTest(skill=skill_name):
            self.assert_skill_tree_is_english(skill_name)
```

Replace the sprite `required_body_fragments` with:

```python
"required_body_fragments": (
    "Prefer an existing image",
    "native image tool",
    "If native generation is unavailable, ask the user to choose",
    "ask the user to choose Jimeng or Wanxiang every time",
    "provider, model, non-sensitive parameters, quantity, cost, currency, and request fingerprint",
    "Never install",
    "Never resubmit",
    "submission_unknown",
    "Submit one grouped intake card",
    "--visual-review",
    "character-identity-consistency",
    "semantic-duplicate-frames",
    "sprite plan",
    "sprite route",
    "sprite ingest",
    "sprite process",
    "sprite validate",
),
```

- [ ] **Step 2: Run the generalized test and verify the Chinese sprite body fails**

Run: `python -m unittest tests.test_skill_contracts.SkillContractTests.test_public_skill_packages_are_english -v`

Expected: FAIL for `forge-2d-sprite/SKILL.md`; map and video subtests PASS.

- [ ] **Step 3: Replace the sprite skill body with concise English instructions**

Keep the existing YAML frontmatter unchanged and replace everything after it with:

````markdown
# Forge 2D Sprite

Use the shared CLI to orchestrate 2D Sprite generation, ingestion, processing,
and quality validation. Interpret the user request, invoke a native Agent image
tool when selected, and obtain every required user choice. Leave deterministic
media processing to the local runtime. Never duplicate processing code or
credentials in this Skill.

## Standard interaction

Submit one grouped intake card that collects asset type and identity, action,
direction and frame count, art direction and references, background treatment,
canvas/anchor/output formats, engine delivery, and source policy. Ask once for
all missing or contradictory fields; do not repeat answered questions. Route
the source only after the user confirms the consolidated summary.

## Source order

1. Prefer an existing image. Select `existing-file` and run `sprite ingest`.
2. When no image exists, check whether the Agent exposes a suitable native image tool.
3. When native generation is available and selected, build the prompt package,
   generate the image, and return its local path to the `RawImageRecord` flow.
4. If native generation is unavailable, ask the user to choose Jimeng,
   Wanxiang, a configured local image tool, or an existing image.
5. If native generation fails or its quality is rejected, ask the user to retry
   native generation, switch the source, accept the current image, or stop.
6. After entering a third-party route, ask the user to choose Jimeng or Wanxiang
   every time. Never infer the provider from credentials, login state, or history.

## Paid submission gate

Before a third-party submission, display and confirm the provider, model,
non-sensitive parameters, quantity, cost, currency, and request fingerprint.
One confirmation authorizes one submission and must be consumed and persisted
before invoking the external CLI.

Never install dependencies, CLIs, models, or credentials automatically. Never
resubmit a failed or `submission_unknown` task; recover an unknown submission
only through query or manual provider verification.

## CLI commands

Every command emits versioned JSON. `plan` and `route` do not access the
network; `ingest`, `process`, and `validate` operate only on local files.

```powershell
python skills/forge-2d-sprite/scripts/run.py sprite plan `
  --request <request.json> --out-dir <output> --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py sprite route `
  --request <output/sprite-request.json> --capabilities <capabilities.json> `
  --out <output/source-decision.json> --state <output/job-state.json> `
  --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py sprite ingest `
  --request <output/sprite-request.json> --decision <output/source-decision.json> `
  --image <repo-relative-image> --repo-root <repo> --out <output/raw-image.json> `
  --state <output/job-state.json> --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py sprite process `
  --request <output/sprite-request.json> --raw-image <output/raw-image.json> `
  --repo-root <repo> --out-dir <repo>/outputs/<asset-id> `
  --state <output/job-state.json> --now <utc-rfc3339>

python skills/forge-2d-sprite/scripts/run.py sprite validate `
  --request <output/sprite-request.json> --raw-image <output/raw-image.json> `
  --processing-result <staging>/processing-result.json --repo-root <repo> `
  --staging-dir <staging> --final-dir <repo>/outputs/<asset-id> `
  --visual-review <output/visual-review.json> `
  --state <output/job-state.json> --now <utc-rfc3339>
```

The first validation keeps staging and reports `needs_attention` until a manual
review is supplied. The review must contain exactly these six checks, each set
to `passed` or `failed`:

```json
{
  "schema_version": 1,
  "checks": {
    "character-identity-consistency": "passed",
    "action-and-direction-correctness": "passed",
    "equipment-continuity": "passed",
    "anatomy-and-silhouette": "passed",
    "unwanted-text-or-watermark": "passed",
    "semantic-duplicate-frames": "passed"
  }
}
```

Run `validate` again with `--visual-review`. Publish the final directory only
when deterministic validation and all six visual checks pass.
````

- [ ] **Step 4: Run the generalized guard, skill contracts, and all three validators**

Run:

```powershell
python -m unittest tests.test_skill_contracts -v
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-2d-map
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-2d-sprite
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-video-to-sprite
```

Expected: every command exits `0`; the language guard discovers exactly three skills and reports no CJK text.

- [ ] **Step 5: Commit the sprite translation and future-language enforcement**

```powershell
git add -- skills/forge-2d-sprite/SKILL.md tests/test_skill_contracts.py
git commit -m "docs: translate forge 2d sprite skill to english"
```

---

### Task 3: Document the policy and verify a clean checkout

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: Task 2 recursive English-only contract and both public READMEs.
- Produces: `test_readmes_document_skill_language_policy()` and a contributor-visible language rule.

- [ ] **Step 1: Add a failing README policy test**

Add:

```python
def test_readmes_document_skill_language_policy(self) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    self.assertIn("All files under `skills/` use English", readme)
    self.assertIn("`skills/` 目录下的文件统一使用英文", chinese)
```

- [ ] **Step 2: Run the policy test and verify both READMEs lack the rule**

Run: `python -m unittest tests.test_skill_contracts.SkillContractTests.test_readmes_document_skill_language_policy -v`

Expected: FAIL on the first missing README phrase.

- [ ] **Step 3: Add one concise policy sentence to each development-check section**

Append to the prose immediately before each README's test command block:

```markdown
All files under `skills/` use English. Chinese public documentation belongs only in `README.zh-CN.md`.
```

```markdown
`skills/` 目录下的文件统一使用英文；中文公共文档仅保留在 `README.zh-CN.md`。
```

- [ ] **Step 4: Run focused, full, and launcher verification in the primary worktree**

Run in the primary worktree:

```powershell
python -m unittest tests.test_skill_contracts -v
python -m unittest discover -s tests -q
python skills/forge-2d-map/scripts/run.py --help
python skills/forge-2d-sprite/scripts/run.py --help
python skills/forge-video-to-sprite/scripts/run.py --help
git diff --check
```

- [ ] **Step 5: Commit the public language policy**

```powershell
git add -- README.md README.zh-CN.md tests/test_skill_contracts.py
git commit -m "docs: enforce english-only skill authoring"
```

- [ ] **Step 6: Verify the committed checkout in an isolated worktree**

Run:

```powershell
$verifyPath = "G:\GitProject\game-visual-forge-clean-english-skills-20260810"
if (Test-Path -LiteralPath $verifyPath) { throw "Verification path already exists: $verifyPath" }
git worktree add --detach $verifyPath HEAD

Push-Location $verifyPath
try {
    python -m unittest discover -s tests -q
    python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-2d-map
    python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-2d-sprite
    python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" skills/forge-video-to-sprite

    $forbidden = rg -n -i "generate2dmap|agent-sprite-forge" skills src tests README.md README.zh-CN.md
    if ($LASTEXITCODE -eq 0) { throw "Forbidden repository references found: $forbidden" }
    if ($LASTEXITCODE -ne 1) { throw "Reference scan failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

$resolved = (Resolve-Path -LiteralPath $verifyPath).Path
if ($resolved -ne $verifyPath) { throw "Unexpected verification path: $resolved" }
git worktree remove $verifyPath
git worktree prune
```

Expected: the committed checkout passes all tests and validators, the forbidden-reference scan returns no matches, and the primary worktree's unrelated adaptive-river-crossing evidence remains unstaged.
