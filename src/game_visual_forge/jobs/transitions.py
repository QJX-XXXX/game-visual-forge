from __future__ import annotations

from dataclasses import replace

from game_visual_forge.contracts.job import JobState, JobStatus


LEGAL_TRANSITIONS = {
    JobStatus.PLANNED: {
        JobStatus.AWAITING_CONFIRMATION,
        JobStatus.READY,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.CANCELLED,
        JobStatus.REJECTED,
        JobStatus.NEEDS_USER_ACTION,
    },
    JobStatus.AWAITING_CONFIRMATION: {
        JobStatus.READY,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.CANCELLED,
        JobStatus.REJECTED,
    },
    JobStatus.READY: {
        JobStatus.AWAITING_CONFIRMATION,
        JobStatus.SUBMITTING,
        JobStatus.RUNNING,
        JobStatus.CANCELLED,
        JobStatus.REJECTED,
        JobStatus.NEEDS_USER_ACTION,
    },
    JobStatus.SUBMITTING: {
        JobStatus.RUNNING,
        JobStatus.FAILED,
        JobStatus.SUBMISSION_UNKNOWN,
        JobStatus.REJECTED,
    },
    JobStatus.RUNNING: {
        JobStatus.DOWNLOADING,
        JobStatus.VERIFYING,
        JobStatus.FAILED,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.REJECTED,
        JobStatus.GENERATION_UNKNOWN,
    },
    JobStatus.DOWNLOADING: {
        JobStatus.VERIFYING,
        JobStatus.FAILED,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.REJECTED,
    },
    JobStatus.VERIFYING: {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.REJECTED,
    },
    JobStatus.NEEDS_ATTENTION: {
        JobStatus.AWAITING_CONFIRMATION,
        JobStatus.READY,
        JobStatus.VERIFYING,
        JobStatus.CANCELLED,
        JobStatus.REJECTED,
    },
    JobStatus.NEEDS_USER_ACTION: {
        JobStatus.READY,
        JobStatus.CANCELLED,
        JobStatus.REJECTED,
    },
    JobStatus.GENERATION_UNKNOWN: {
        JobStatus.FAILED,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.CANCELLED,
        JobStatus.REJECTED,
    },
    JobStatus.SUBMISSION_UNKNOWN: {
        JobStatus.RUNNING,
        JobStatus.FAILED,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.REJECTED,
    },
    JobStatus.FAILED: {JobStatus.REJECTED},
    JobStatus.COMPLETED: {JobStatus.REJECTED},
    JobStatus.CANCELLED: {JobStatus.REJECTED},
    JobStatus.REJECTED: set(),
}


def _is_paid_provider_job(state: JobState) -> bool:
    return state.provider is not None


def select_image_source(state: JobState, provider: str | None, *, now: str) -> JobState:
    """Re-select an image source before processing, retaining its paid gate."""
    if state.status not in {JobStatus.PLANNED, JobStatus.READY, JobStatus.AWAITING_CONFIRMATION, JobStatus.NEEDS_ATTENTION}:
        raise ValueError("image source cannot change while processing or after completion")
    target = JobStatus.AWAITING_CONFIRMATION if provider is not None else JobStatus.READY
    selected = replace(state, provider=provider, external_task_id=None, error_code=None, ready_provenance=None)
    if selected.status is not target:
        selected = transition_job(selected, target, now=now)
    else:
        selected = replace(selected, updated_at=now)
    if provider is None:
        selected = replace(selected, ready_provenance=None)
    return selected


def _validate_provider_confirmation(state: JobState, target: JobStatus) -> None:
    if not _is_paid_provider_job(state):
        return
    if state.status is JobStatus.PLANNED and target is JobStatus.READY:
        raise ValueError(
            "provider jobs require explicit confirmation before becoming ready"
        )
    if state.status is JobStatus.READY and target is JobStatus.SUBMITTING:
        if state.ready_provenance != JobStatus.AWAITING_CONFIRMATION.value:
            raise ValueError(
                "provider jobs require an awaiting_confirmation marker before submitting"
            )


def transition_job(
    state: JobState,
    target: JobStatus,
    *,
    now: str,
    external_task_id: str | None = None,
    error_code: str | None = None,
) -> JobState:
    if target not in LEGAL_TRANSITIONS[state.status]:
        raise ValueError(f"illegal transition: {state.status.value} -> {target.value}")
    _validate_provider_confirmation(state, target)
    ready_provenance = state.ready_provenance
    if target is JobStatus.READY:
        ready_provenance = state.status.value
    return replace(
        state,
        status=target,
        updated_at=now,
        external_task_id=external_task_id or state.external_task_id,
        error_code=error_code,
        ready_provenance=ready_provenance,
    )
