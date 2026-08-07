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
    },
    JobStatus.AWAITING_CONFIRMATION: {
        JobStatus.READY,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.CANCELLED,
        JobStatus.REJECTED,
    },
    JobStatus.READY: {
        JobStatus.SUBMITTING,
        JobStatus.RUNNING,
        JobStatus.CANCELLED,
        JobStatus.REJECTED,
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
        JobStatus.READY,
        JobStatus.VERIFYING,
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
