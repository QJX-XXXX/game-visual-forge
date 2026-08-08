# README HD Cleanup Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add practical HD sprite-cleanup tooling, advantages, installation, model-cache, and selection guidance to both concise README pages.

**Architecture:** Keep all new information inside the existing HD sprite cleanup showcase section. Enforce the public documentation contract in `tests/test_repository_contract.py`; do not change runtime dependencies or processing behavior.

**Tech Stack:** Markdown, Python `unittest`, PowerShell, existing `pyproject.toml` optional extras.

## Global Constraints

- Modify only `README.md`, `README.zh-CN.md`, and `tests/test_repository_contract.py` during implementation.
- Keep each README at or below 180 lines.
- Document only behavior verified in `src/game_visual_forge/processing/background.py`, `src/game_visual_forge/processing/matting.py`, and `pyproject.toml`.
- Keep `forge-2d-map`, `forge-2d-sprite`, and `forge-video-to-sprite` as the only repository Skills.
- Preserve all unrelated modified and untracked user files.
- Do not add dependencies, assets, or production workflow command chains.

---

### Task 1: Define the README HD cleanup contract

**Files:**
- Modify: `tests/test_repository_contract.py`
- Test: `tests/test_repository_contract.py`

**Interfaces:**
- Consumes: UTF-8 text from `README.md` and `README.zh-CN.md`.
- Produces: assertions that keep installation and behavior guidance present in both languages.

- [ ] **Step 1: Add the failing contract test**

Add this test to `RepositoryContractTests`:

```python
def test_readmes_explain_hd_cleanup_tools_and_installation(self) -> None:
    required = (
        "birefnet-general",
        'python -m pip install -e ".[image]"',
        'python -m pip install -e ".[background]"',
        'python -m pip install "rembg[cpu]"',
        'python -m pip install "rembg[gpu]"',
        'python -m pip install -e ".[matting]"',
        "U2NET_HOME",
        "PyMatting",
        "CUDA",
        "CPU",
    )
    for readme_name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / readme_name).read_text(encoding="utf-8")
        for fragment in required:
            self.assertIn(fragment, text, f"{readme_name} missing HD cleanup guidance: {fragment}")
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```powershell
python -m unittest tests.test_repository_contract.RepositoryContractTests.test_readmes_explain_hd_cleanup_tools_and_installation -v
```

Expected: FAIL because the concise README pages do not yet contain the required tool and installation details.

### Task 2: Expand the bilingual HD cleanup sections

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Test: `tests/test_repository_contract.py`

**Interfaces:**
- Consumes: the exact dependency extras from `pyproject.toml` and fallback order from `background.py`.
- Produces: equivalent English and Simplified Chinese sections containing tool, advantage, install, cache, and selection guidance.

- [ ] **Step 1: Add the English tool chain and advantages**

Below the existing comparison image, explain:

- Pillow handles RGBA conversion and export;
- NumPy/SciPy support masks and known-background reconstruction;
- rembg uses `birefnet-general` for semantic foreground separation;
- known-magenta reconstruction reduces spill on anti-aliased edges;
- provider order is CUDA, then CPU, then deterministic chroma fallback;
- PyMatting is optional and slower, and is not guaranteed to improve every asset.

- [ ] **Step 2: Add the English installation and selection table**

Include these exact commands:

```powershell
python -m pip install -e ".[image]"
python -m pip install -e ".[background]"
python -m pip install "rembg[cpu]"
python -m pip install "rembg[gpu]"
python -m pip install -e ".[matting]"
python -c "from rembg import new_session; new_session('birefnet-general')"
```

Explain that CPU is the compatibility default, GPU requires a verified
ONNX Runtime/CUDA environment, the model cache is selected by `U2NET_HOME` or
defaults to `~/.u2net`, and installation/download is never silent.

- [ ] **Step 3: Mirror the content in Simplified Chinese**

Translate the same behavior and commands without expanding into the complete
sprite production workflow. Retain the English tool and configuration names
needed by the contract test.

- [ ] **Step 4: Run focused README tests**

Run:

```powershell
python -m unittest tests.test_repository_contract -v
```

Expected: PASS, including the 180-line limit.

### Task 3: Verify and commit

**Files:**
- Verify: `README.md`
- Verify: `README.zh-CN.md`
- Verify: `tests/test_repository_contract.py`

**Interfaces:**
- Consumes: completed documentation and contract tests.
- Produces: one scoped documentation commit.

- [ ] **Step 1: Validate local Markdown paths**

Extract relative Markdown links from both README files and confirm every target
exists. Expected: no missing local path.

- [ ] **Step 2: Run the full suite**

Run:

```powershell
python -m unittest discover -s tests -q
```

Expected: all tests pass.

- [ ] **Step 3: Audit scope**

Run `git diff --check` and `git status --short`. Stage only the two README files
and `tests/test_repository_contract.py`; preserve all other working-tree files.

- [ ] **Step 4: Commit**

```powershell
git add README.md README.zh-CN.md tests/test_repository_contract.py
git commit -m "docs: explain HD sprite cleanup setup"
```
