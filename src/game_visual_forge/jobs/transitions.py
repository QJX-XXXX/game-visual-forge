from __future__ import annotations

from dataclasses import replace

from game_visual_forge.contracts.job import JobState, JobStatus


LEGAL_TRANSITIONS = {
    JobStatus.PLANNED: {
        JobStatus.AWAITING_CONFIRMATION,
        JobStatus.READY,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.CANCELLED,
    },
    JobStatus.AWAITING_CONFIRMATION: {
        JobStatus.READY,
        JobStatus.NEEDS_ATTENTION,
        JobStatus.CANCELLED,
    },
    JobStatus.READY: {
        JobStatus.SUBMITTING,
        JobStatus.RUNNING,
        JobStatus.CANCELLED,
    },
    JobStatus.SUBMITTING: {
        JobStatus.RUNNING,
        JobStatus.FAILED,
        JobStatus.SUBMISSION_UNKNOWN,
    },
    JobStatus.RUNNING: {
        JobStatus.DOWNLOADING,
        JobStatus.VERIFYING,
        JobStatus.FAILED,
        JobStatus.NEEDS_ATTENTION,
    },
    JobStatus.DOWNLOADING: {
        JobStatus.VERIFYING,
        JobStatus.FAILED,
        JobStatus.NEEDS_ATTENTION,
    },
    JobStatus.VERIFYING: {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.NEEDS_ATTENTION,
    },
    JobStatus.NEEDS_ATTENTION: {
        JobStatus.READY,
        JobStatus.CANCELLED,
    },
    JobStatus.SUBMISSION_UNKNOWN: {
        JobStatus.RUNNING,
        JobStatus.FAILED,
        JobStatus.NEEDS_ATTENTION,
    },
    JobStatus.FAILED: set(),
    JobStatus.COMPLETED: set(),
    JobStatus.CANCELLED: set(),
}


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
    return replace(
        state,
        status=target,
        updated_at=now,
        external_task_id=external_task_id or state.external_task_id,
        error_code=error_code,
    )
