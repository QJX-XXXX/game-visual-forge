from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from game_visual_forge.contracts import (
    BackgroundRemoval,
    ExternalProvider,
    PromptPackage,
    ProviderPreflight,
    SourceDecision,
    SourceType,
    SpriteRequest,
    SpriteSourcePreference,
)
from game_visual_forge.jobs.fingerprints import fingerprint_request


TRANSPARENT_BACKGROUND_PROMPT = (
    "移除此图像的背景。保持所有前景主体不变且完整，边缘干净平滑。将背景设为透明。"
)


@dataclass(frozen=True)
class AgentImageCapabilities:
    supported: bool
    operations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.supported, bool):
            raise TypeError("supported must be a boolean")
        if not isinstance(self.operations, tuple) or not all(isinstance(item, str) for item in self.operations):
            raise TypeError("operations must be a tuple of strings")


class NativeAttemptOutcome(StrEnum):
    NOT_ATTEMPTED = "not-attempted"
    FAILED = "failed"
    QUALITY_REJECTED = "quality-rejected"


def _decision(
    request: SpriteRequest,
    source_type: SourceType | None,
    *,
    requires_user_selection: bool,
    requires_paid_confirmation: bool,
    reason: str,
    provider: ExternalProvider | None = None,
) -> SourceDecision:
    return SourceDecision(
        schema_version=1,
        source_type=source_type,
        requires_user_selection=requires_user_selection,
        requires_paid_confirmation=requires_paid_confirmation,
        reason=reason,
        request_fingerprint=fingerprint_request(request.to_dict()),
        selected_provider=provider,
    )


def route_sprite(
    request: SpriteRequest,
    native: AgentImageCapabilities,
    *,
    native_outcome: NativeAttemptOutcome = NativeAttemptOutcome.NOT_ATTEMPTED,
    selected_source: SourceType | None = None,
    provider_preflight: ProviderPreflight | None = None,
) -> SourceDecision:
    if request.source_preference is SpriteSourcePreference.EXISTING_FILE:
        return _decision(
            request,
            SourceType.EXISTING_FILE,
            requires_user_selection=False,
            requires_paid_confirmation=False,
            reason="existing-file-supplied",
        )

    if selected_source is SourceType.EXISTING_FILE:
        return _decision(
            request,
            SourceType.EXISTING_FILE,
            requires_user_selection=False,
            requires_paid_confirmation=False,
            reason="user-selected-existing-file",
        )

    native_supported = native.supported and "text-to-image" in native.operations
    if native_supported and native_outcome is NativeAttemptOutcome.NOT_ATTEMPTED:
        return _decision(
            request,
            SourceType.AGENT_NATIVE,
            requires_user_selection=False,
            requires_paid_confirmation=False,
            reason="agent-native-supported",
        )

    if selected_source is SourceType.AGENT_NATIVE:
        if not native_supported:
            return _decision(
                request,
                None,
                requires_user_selection=True,
                requires_paid_confirmation=False,
                reason="agent-native-unavailable",
            )
        return _decision(
            request,
            SourceType.AGENT_NATIVE,
            requires_user_selection=False,
            requires_paid_confirmation=False,
            reason="user-selected-native-retry",
        )

    if selected_source is SourceType.LOCAL_TOOL:
        return _decision(
            request,
            SourceType.LOCAL_TOOL,
            requires_user_selection=False,
            requires_paid_confirmation=False,
            reason="user-selected-local-tool",
        )

    if selected_source in {SourceType.DREAMINA, SourceType.WANXIANG}:
        provider = ExternalProvider(selected_source.value)
        if provider_preflight is None or provider_preflight.provider is not provider:
            raise ValueError("selected provider requires matching preflight")
        if not provider_preflight.available or not provider_preflight.authenticated:
            return _decision(
                request,
                None,
                requires_user_selection=True,
                requires_paid_confirmation=False,
                reason="selected-provider-unavailable",
                provider=provider,
            )
        return _decision(
            request,
            selected_source,
            requires_user_selection=False,
            requires_paid_confirmation=True,
            reason="user-selected-paid-provider",
            provider=provider,
        )

    reason = {
        NativeAttemptOutcome.FAILED: "native-failed-user-selection-required",
        NativeAttemptOutcome.QUALITY_REJECTED: "native-quality-rejected-user-selection-required",
    }.get(native_outcome, "native-unsupported-user-selection-required")
    return _decision(
        request,
        None,
        requires_user_selection=True,
        requires_paid_confirmation=False,
        reason=reason,
    )


def build_prompt_package(request: SpriteRequest) -> PromptPackage:
    transparent_background = request.background_removal is BackgroundRemoval.AUTO
    transparent_background_prompt = (
        TRANSPARENT_BACKGROUND_PROMPT if transparent_background else None
    )
    frames_per_direction = request.frame_count // len(request.directions)
    frame_order = tuple(
        f"{direction}:{index:02d}"
        for direction in request.directions
        for index in range(frames_per_direction)
    )
    negatives = (
        "no text",
        "no watermark",
        "no cropped body parts",
        *(("no white background", "no checkerboard background") if transparent_background else ()),
        *request.identity_constraints,
    )
    positive_prompt = request.prompt
    if transparent_background:
        positive_prompt = (
            f"{positive_prompt} {transparent_background_prompt} "
            "Return a PNG with a true transparent background "
            "and a real Alpha channel; every background pixel must have alpha 0."
        )
    return PromptPackage(
        schema_version=1,
        positive_prompt=positive_prompt,
        negative_constraints=negatives,
        reference_paths=request.reference_paths,
        canvas_width=request.canvas_width,
        canvas_height=request.canvas_height,
        grid_rows=request.grid_rows,
        grid_columns=request.grid_columns,
        frame_order=frame_order,
        transparent_background=transparent_background,
        solid_background=(
            request.chroma_color
            if request.background_removal in {BackgroundRemoval.CHROMA, BackgroundRemoval.REMBG}
            else None
        ),
        expected_output_path=f"{request.output_dir}/raw/source.png",
        transparent_background_prompt=transparent_background_prompt,
    )
