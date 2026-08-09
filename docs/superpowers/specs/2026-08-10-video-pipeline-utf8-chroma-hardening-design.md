# Video Pipeline UTF-8 and Chroma Hardening Design

## Goal

Make `forge-video-to-sprite` reliable on Windows for non-ASCII provider JSON and prevent visible configured-key-color residue from reaching published Sprite frames after lossy video decoding and image resampling.

## Scope

This change covers two deterministic boundaries:

1. MiniMax and Jimeng provider subprocess stdin, stdout, and diagnostic stderr handling.
2. Chroma-key removal, transparent-edge resizing, residue measurement, and publication gating.

It does not change provider selection, credentials, paid confirmation, submission recovery, model capabilities, prompt content, frame sampling, or Unity integration. Tests must remain zero-network and must not create paid provider tasks.

## Provider UTF-8 Boundary

Provider launchers use a shared binary JSON protocol. They read all stdin bytes and decode them as strict UTF-8, require one JSON object, and serialize one response object with `ensure_ascii=False` followed by a newline encoded as UTF-8. They write through `sys.stdout.buffer` when available and retain a text-stream fallback only for in-process tests.

MiniMax and Jimeng launchers delegate to provider `main()` entry points that use this shared protocol. Provider logic remains in the adapter modules; launcher files contain only repository bootstrap and entry-point dispatch.

Parent orchestration invokes provider processes with argument arrays and `shell=False` in byte mode. It sends UTF-8 JSON bytes, decodes stdout as strict UTF-8, and treats invalid stdout as an invalid provider response. Stderr is diagnostic-only and may be decoded with replacement so a third-party CLI using a Windows code page cannot crash the orchestration before a sanitized error is produced. Secret and media redaction checks continue to run on decoded output.

Timeout, launch failure, nonzero exit, invalid JSON, and submission-unknown behavior retain their existing error codes and recovery semantics.

## Chroma Processing

Chroma-key video input must not assume that decoded pixels exactly equal the requested key color. The processor removes pixels within a codec-drift tolerance of the configured key color before trimming and layout. Fully transparent pixels have their RGB channels cleared so hidden key-color data cannot contaminate later resampling.

HD resizing must be alpha-safe. The resize step must avoid mixing RGB values from fully transparent pixels into visible foreground edges. After resizing, a generic cleanup pass uses the configured key color rather than hard-coded magenta channel rules. It removes only visible pixels classified as residual key-color contamination and clears RGB wherever alpha becomes zero.

The existing pixel-processing path keeps nearest-neighbor scaling. The residue cleanup applies only when `background_mode=chroma`; preserve and rembg modes retain their current behavior.

## Quality Gate

For chroma output, deterministic validation examines every delivered frame at every requested density. It measures visible pixels sufficiently close to the configured key color and records the maximum residue percentage.

The `chroma-residue` check fails when the maximum exceeds `1.0%`. A failed residue check makes deterministic quality fail and prevents publication. The report message includes the configured limit and measured maximum. Empty transparent margins do not count as residue, and fully transparent RGB values do not count as visible pixels.

## Skill Guidance

Keep `skills/forge-video-to-sprite/SKILL.md` concise. Add only the mandatory guarantees: provider JSON transport is UTF-8 and chroma publication requires the residue gate. Put Windows subprocess behavior, codec drift, alpha-safe resizing, and troubleshooting details in the existing provider and processing reference documents.

## Tests

Zero-network tests cover:

- MiniMax and Jimeng launcher round trips with Chinese text, typographic punctuation, and non-ASCII response data;
- parent-to-child UTF-8 JSON transport through a real local Python subprocess;
- non-UTF-8 diagnostic stderr without an uncaught decode failure;
- strict rejection of invalid UTF-8 provider stdout;
- codec-shifted key colors such as `#FE00FD` against configured `#FF00FF`;
- absence of key-color fringe after HD resampling;
- generic behavior with a non-magenta configured key color;
- residue quality failure above `1.0%` and success at or below it;
- unchanged preserve/rembg and pixel-mode behavior.

Focused provider, processing, quality, skill-contract, and clean-workflow suites must pass before the full unittest discovery run.

## Acceptance Criteria

- MiniMax and Jimeng accept and return non-ASCII JSON on Windows without depending on the active console code page.
- Third-party diagnostic encoding cannot crash provider orchestration.
- Invalid UTF-8 protocol stdout is rejected deterministically.
- Chroma delivery frames contain no visible configured-key-color fringe introduced by codec drift or resizing beyond the `1.0%` publication limit.
- The cleanup is based on the configured key color and is not magenta-only.
- No live provider call, provider charge, new dependency, or unrelated repository refactor is introduced.
