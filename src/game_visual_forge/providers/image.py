from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from pathlib import Path

from game_visual_forge.contracts import (
    BackgroundRemoval, CostEstimate, ExternalProvider, JobStatus, MapRequest, PaidConfirmation,
    SourceType, SpriteRequest, TileMapRequest,
)
from game_visual_forge.contracts.job import _validate_timestamp
from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.jobs import fingerprint_request, load_job, save_job, transition_job
from game_visual_forge.errors import ErrorCode, ForgeError
from game_visual_forge.processing.images import ingest_image, sha256_file
from game_visual_forge.providers.image_http import (
    ImageApiError, assert_safe, bind_references, file_lock, json_bytes,
    repo_path, verify_references,
)
from game_visual_forge.providers.jimeng_image import JimengImageAdapter
from game_visual_forge.providers.minimax_image import MiniMaxImageAdapter
from game_visual_forge.providers.wanxiang_image import WanxiangImageAdapter
from game_visual_forge.routing.sprite import build_prompt_package


_BINDING_FIELDS = ("schema_version", "attempt_id", "kind", "provider", "model", "parameters", "quantity", "request_fingerprint", "output_dir", "workflow_state")
_STATUSES = {"prepared", "submitting", "submitted", "running", "completed", "downloaded", "failed", "submission_unknown", "needs_attention"}


def image_adapter(provider: str, transport=None, *, execution=None, repo_root=None, output_dir=None):
    provider = ExternalProvider(provider)
    if execution is not None and not isinstance(execution, dict):
        raise ValueError("execution configuration must be a JSON object")
    if execution and execution.get("backend", "api") != "api":
        from game_visual_forge.providers.tool_images import ToolImageAdapter
        return ToolImageAdapter(provider, execution, root=repo_root, output_dir=output_dir, transport=transport)
    if provider is ExternalProvider.MINIMAX:
        return MiniMaxImageAdapter(transport=transport)
    if provider in {ExternalProvider.JIMENG, ExternalProvider.DREAMINA}:
        return JimengImageAdapter(transport=transport, provider=provider)
    if provider is ExternalProvider.WANXIANG:
        return WanxiangImageAdapter(transport=transport)
    raise ValueError("unsupported image provider")


def _binding(attempt):
    return hashlib.sha256(json_bytes({key: attempt[key] for key in _BINDING_FIELDS})).hexdigest()


def _load_attempt(path: Path):
    attempt = load_json(path)
    assert_safe(attempt)
    if attempt.get("schema_version") != 1 or attempt.get("status") not in _STATUSES:
        raise ValueError("invalid image attempt")
    if attempt.get("binding_sha256") != _binding(attempt):
        raise ValueError("image attempt binding has changed")
    image_adapter(attempt["provider"], execution=attempt["parameters"].get("execution")).normalize(attempt["model"], attempt["parameters"], attempt["quantity"])
    return attempt


def _write_attempt(path, attempt, now):
    _validate_timestamp(now, field_name="now")
    attempt["updated_at"] = now
    assert_safe(attempt)
    dump_json(path, attempt)
    return attempt


def _image_prompt(request, kind):
    if kind != "sprite":
        return request.prompt
    # These APIs return opaque images. Preserve the sheet and seed constraints;
    # the existing local processor meets the transparent delivery contract.
    chroma = request.chroma_color or "#ff00ff"
    opaque_request = replace(request, background_removal=BackgroundRemoval.CHROMA, chroma_color=chroma)
    prompt = build_prompt_package(opaque_request).positive_prompt
    if request.background_removal is not BackgroundRemoval.PRESERVE:
        prompt += f" Use a uniform solid {chroma} background, without shadows or checkerboards, for local background removal."
    return prompt


def prepare_image_attempt(request_path, decision_path, parameters_path, attempt_path, *, kind, model, quantity, repo_root, now, state_path=None, transport=None, execution=None):
    _validate_timestamp(now, field_name="now")
    root = Path(repo_root).resolve()
    attempt_path = Path(attempt_path)
    request_types = {"sprite": SpriteRequest, "map": MapRequest, "tilemap": TileMapRequest}
    if kind not in request_types:
        raise ValueError("image request kind must be sprite, map, or tilemap")
    request = request_types[kind].from_dict(load_json(Path(request_path)))
    fingerprint = fingerprint_request(request.to_dict())
    decision = load_json(Path(decision_path))
    if decision.get("request_fingerprint") != fingerprint or decision.get("requires_user_selection") or not decision.get("requires_paid_confirmation"):
        raise ValueError("image source decision does not match the confirmed request")
    provider = ExternalProvider(decision.get("selected_provider"))
    if decision.get("source_type") != provider.value:
        raise ValueError("image source/provider binding does not match")
    parameters = load_json(Path(parameters_path)) if parameters_path else {}
    if execution is not None:
        if "execution" in parameters and parameters["execution"] != execution:
            raise ValueError("conflicting image execution configurations")
        parameters["execution"] = execution
    selected_backend = decision.get("selected_backend")
    if selected_backend:
        if selected_backend != "api":
            parameters.setdefault("execution", {"backend": selected_backend})
        if parameters.get("execution", {}).get("backend", "api") != selected_backend:
            raise ValueError("image backend differs from the selected source route")
    adapter = image_adapter(provider, transport, execution=parameters.get("execution"), repo_root=root)
    parameters.setdefault("prompt", _image_prompt(request, kind))
    if "references" not in parameters:
        paths = list(getattr(request, "reference_paths", ()))
        seed = getattr(request, "seed_frame_path", None)
        if seed and seed not in paths:
            paths.insert(0, seed)
        parameters["references"] = [{"path": path} for path in paths]
    parameters = adapter.normalize(model, parameters, quantity)
    parameters["references"] = bind_references(parameters["references"], root, provider.value, adapter.transport, allow_local=parameters.get("execution", {}).get("backend") == "cli")
    workflow_state = None
    if state_path:
        state_path = Path(state_path).resolve()
        workflow_state = state_path.relative_to(root).as_posix()
        state = load_job(state_path)
        if state.request_fingerprint != fingerprint or state.provider != provider.value or state.status not in {JobStatus.AWAITING_CONFIRMATION, JobStatus.READY}:
            raise ValueError("workflow state does not match the selected image provider")
    attempt_id = uuid.uuid4().hex
    output_dir = (attempt_path.resolve().parent / "images" / attempt_id).relative_to(root).as_posix()
    attempt = {
        "schema_version": 1, "attempt_id": attempt_id, "kind": kind,
        "provider": provider.value, "model": model, "parameters": parameters,
        "quantity": quantity, "request_fingerprint": fingerprint,
        "output_dir": output_dir, "workflow_state": workflow_state,
        "status": "prepared", "created_at": now, "updated_at": now,
        "external_task_id": None, "outputs": [], "errors": [], "error_code": None,
    }
    attempt["binding_sha256"] = _binding(attempt)
    with file_lock(attempt_path):
        if attempt_path.exists():
            raise ValueError("image attempt already exists; recover it or prepare a new attempt path")
        return _write_attempt(attempt_path, attempt, now)


def _confirmation_values(attempt, estimate):
    return {
        "attempt_id": attempt["attempt_id"], "provider": ExternalProvider(attempt["provider"]),
        "model": attempt["model"], "parameters": attempt["parameters"],
        "quantity": attempt["quantity"], "estimate": estimate,
        "request_fingerprint": attempt["request_fingerprint"],
    }


def confirm_image_attempt(attempt_path, quote_path, confirmation_path, *, now):
    with file_lock(Path(attempt_path)), file_lock(Path(confirmation_path)):
        attempt = _load_attempt(Path(attempt_path))
        if attempt["status"] != "prepared" or Path(confirmation_path).exists():
            raise ValueError("only a prepared image attempt can receive a new confirmation")
        quote = CostEstimate.from_dict(load_json(Path(quote_path)))
        try:
            amount = Decimal(quote.amount)
        except (InvalidOperation, TypeError) as error:
            raise ValueError("a verified total cost quote is required") from error
        if quote.provider.value != attempt["provider"] or not quote.verified or not amount.is_finite() or amount < 0 or not quote.currency:
            raise ValueError("quote must have the selected provider, currency, verified amount, and total cost")
        confirmation = PaidConfirmation.create(**_confirmation_values(attempt, quote), confirmed_at=now)
        dump_json(Path(confirmation_path), confirmation.to_dict())
        return confirmation.to_dict()


def _saved_outputs_valid(attempt, root):
    for item in attempt["outputs"]:
        path = repo_path(root, item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise ValueError("a saved provider image changed or is missing")


def verified_image_model(attempt_path, image_path, root, fingerprint, provider):
    """Bind normal ingestion to a downloaded API candidate and its model."""
    attempt = _load_attempt(Path(attempt_path))
    if attempt["request_fingerprint"] != fingerprint or provider is None or attempt["provider"] != provider.value:
        raise ValueError("image attempt does not match the ingestion source")
    _saved_outputs_valid(attempt, Path(root).resolve())
    if not any(repo_path(Path(root).resolve(), item["path"]) == Path(image_path).resolve() for item in attempt["outputs"]):
        raise ValueError("image is not a downloaded candidate from this attempt")
    return attempt["model"]


def _save_image(attempt, index, data, root):
    directory = repo_path(root, attempt["output_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f".candidate-{index:02d}.part"
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        record = ingest_image(root, temporary, SourceType(attempt["provider"]), attempt["request_fingerprint"], provider=ExternalProvider(attempt["provider"]), model=attempt["model"])
    except ForgeError as error:
        if error.code is ErrorCode.IMAGE_UNREADABLE:
            temporary.unlink(missing_ok=True)
        raise
    extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(record.media_format)
    if extension is None:
        temporary.unlink(missing_ok=True)
        raise ValueError("provider result must be PNG, JPEG, or WEBP")
    destination = directory / f"candidate-{index:02d}{extension}"
    if destination.exists() and sha256_file(destination) != record.sha256:
        raise ValueError("download would overwrite a different provider image")
    # Leave a verified .part file available for local recovery if rename fails.
    os.replace(temporary, destination)
    return {"index": index, "path": destination.relative_to(root).as_posix(), "sha256": record.sha256, "width": record.width, "height": record.height, "media_format": record.media_format, "provider": attempt["provider"], "model": attempt["model"]}


def _image_save_error(attempt, index, error):
    attempt["errors"] = [item for item in attempt["errors"] if item["index"] != index]
    code = error.code.value if isinstance(error, ForgeError) else type(error).__name__
    attempt["errors"].append({"index": index, "code": code})


def _recover_local_images(attempt_path, attempt, root, now):
    directory = repo_path(root, attempt["output_dir"])
    for index in range(1, attempt["quantity"] + 1):
        if any(item["index"] == index for item in attempt["outputs"]):
            continue
        paths = [directory / f".candidate-{index:02d}.part", *(directory / f"candidate-{index:02d}{extension}" for extension in (".png", ".jpg", ".webp"))]
        path = next((candidate for candidate in paths if candidate.is_file()), None)
        if path is None:
            continue
        try:
            if path.stat().st_size > 128 * 1024 * 1024:
                raise ValueError("pending image exceeds local recovery limit")
            attempt["outputs"].append(_save_image(attempt, index, path.read_bytes(), root))
        except (OSError, ValueError, ForgeError) as error:
            _image_save_error(attempt, index, error)
        else:
            attempt["errors"] = [item for item in attempt["errors"] if item["index"] != index]
            _write_attempt(attempt_path, attempt, now)
    attempt["outputs"].sort(key=lambda item: item["index"])
    if len(attempt["outputs"]) == attempt["quantity"]:
        attempt["status"], attempt["error_code"] = "downloaded", None


def submit_image_attempt(attempt_path, confirmation_path, *, repo_root, now, transport=None):
    attempt_path, confirmation_path = Path(attempt_path), Path(confirmation_path)
    root = Path(repo_root).resolve()
    with file_lock(attempt_path), file_lock(confirmation_path):
        attempt = _load_attempt(attempt_path)
        if attempt["status"] != "prepared":
            raise ValueError("image attempt cannot be submitted again; use recovery")
        if attempt["workflow_state"]:
            state = load_job(repo_path(root, attempt["workflow_state"]))
            if state.request_fingerprint != attempt["request_fingerprint"] or state.provider != attempt["provider"] or state.status not in {JobStatus.AWAITING_CONFIRMATION, JobStatus.READY}:
                raise ValueError("workflow source changed after image preparation")
        adapter = image_adapter(attempt["provider"], transport, execution=attempt["parameters"].get("execution"), repo_root=root, output_dir=repo_path(root, attempt["output_dir"]))
        references = verify_references(attempt["parameters"]["references"], root, attempt["provider"], adapter.transport)
        readiness = adapter.preflight()
        if not readiness["available"]:
            raise ValueError(readiness["reason"])
        if hasattr(adapter, "build_body"):
            adapter.build_body(attempt["model"], attempt["parameters"], attempt["quantity"], references)
        confirmation = PaidConfirmation.from_dict(load_json(confirmation_path))
        consumed = confirmation.authorize_attempt(now=now, **_confirmation_values(attempt, confirmation.estimate))
        dump_json(confirmation_path, consumed.to_dict())
        attempt["status"] = "submitting"
        _write_attempt(attempt_path, attempt, now)
        try:
            receipt = adapter.submit(attempt["model"], attempt["parameters"], attempt["quantity"], references)
            if adapter.synchronous:
                attempt["errors"] = receipt.get("errors", [])
                uncertain = receipt.get("uncertain", False)
                for index, data in enumerate(receipt["images"], 1):
                    if data is not None:
                        try:
                            attempt["outputs"].append(_save_image(attempt, index, data, root))
                            _write_attempt(attempt_path, attempt, now)
                        except Exception as error:
                            _image_save_error(attempt, index, error)
                            uncertain = True
                attempt["status"] = "downloaded" if len(attempt["outputs"]) == attempt["quantity"] else "needs_attention" if attempt["outputs"] else "failed"
                if uncertain:
                    attempt["status"] = "submission_unknown"
                    attempt["error_code"] = "incomplete_image_result"
            else:
                task_id = str(receipt.get("external_task_id", ""))
                if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", task_id):
                    raise ImageApiError("invalid_task_id")
                attempt["external_task_id"] = task_id
                attempt["status"] = "submitted"
        except Exception as error:
            if isinstance(error, ImageApiError) and error.external_task_id:
                attempt["external_task_id"] = error.external_task_id
            attempt["status"] = "failed" if isinstance(error, ImageApiError) and error.definite_rejection else "submission_unknown"
            attempt["error_code"] = error.code if isinstance(error, ImageApiError) else type(error).__name__
        return _write_attempt(attempt_path, attempt, now)


def _query_attempt(attempt, adapter):
    if adapter.synchronous:
        raise ValueError("MiniMax image generation is synchronous; inspect saved images and resolve unknown submissions in the provider account")
    if not attempt["external_task_id"]:
        raise ValueError("image query requires an existing task ID")
    return adapter.query(attempt["external_task_id"], attempt["model"], attempt["parameters"])


def query_image_attempt(attempt_path, *, repo_root, now, transport=None, recovered_task_id=None):
    attempt_path = Path(attempt_path)
    with file_lock(attempt_path):
        attempt = _load_attempt(attempt_path)
        if attempt["status"] == "downloaded":
            _saved_outputs_valid(attempt, Path(repo_root).resolve())
            return attempt
        root = Path(repo_root).resolve()
        adapter = image_adapter(attempt["provider"], transport, execution=attempt["parameters"].get("execution"), repo_root=root, output_dir=repo_path(root, attempt["output_dir"]))
        if recovered_task_id:
            if adapter.synchronous or attempt["status"] not in {"submission_unknown", "submitting"} or attempt["external_task_id"]:
                raise ValueError("a recovered task ID can only be attached to an unknown async submission")
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", recovered_task_id):
                raise ValueError("invalid recovered task ID")
            attempt["external_task_id"] = recovered_task_id
            _write_attempt(attempt_path, attempt, now)
        receipt = _query_attempt(attempt, adapter)
        attempt["status"] = receipt["status"]
        attempt["error_code"] = receipt.get("error_code")
        return _write_attempt(attempt_path, attempt, now)


def _ready_workflow(attempt, root, now):
    if not attempt["workflow_state"] or not attempt["outputs"]:
        return
    state_path = repo_path(root, attempt["workflow_state"])
    with file_lock(state_path):
        state = load_job(state_path)
        if state.request_fingerprint != attempt["request_fingerprint"] or state.provider != attempt["provider"]:
            raise ValueError("workflow state binding no longer matches the image attempt")
        if state.status is JobStatus.AWAITING_CONFIRMATION:
            save_job(state_path, transition_job(state, JobStatus.READY, now=now))


def download_image_attempt(attempt_path, *, repo_root, now, transport=None):
    attempt_path = Path(attempt_path)
    root = Path(repo_root).resolve()
    with file_lock(attempt_path):
        attempt = _load_attempt(attempt_path)
        _saved_outputs_valid(attempt, root)
        adapter = image_adapter(attempt["provider"], transport, execution=attempt["parameters"].get("execution"), repo_root=root, output_dir=repo_path(root, attempt["output_dir"]))
        if adapter.synchronous:
            _recover_local_images(attempt_path, attempt, root, now)
            if len(attempt["outputs"]) < attempt["quantity"] and hasattr(adapter, "recover_images"):
                receipt = adapter.recover_images(attempt["quantity"])
                for index, data in enumerate(receipt["images"], 1):
                    if data is not None and not any(item["index"] == index for item in attempt["outputs"]):
                        attempt["outputs"].append(_save_image(attempt, index, data, root))
                        _write_attempt(attempt_path, attempt, now)
                if len(attempt["outputs"]) == attempt["quantity"]:
                    attempt["status"], attempt["error_code"], attempt["errors"] = "downloaded", None, []
            if not attempt["outputs"]:
                raise ValueError("synchronous attempt has no saved image results")
        elif attempt["status"] != "downloaded":
            receipt = _query_attempt(attempt, adapter)
            if receipt["status"] != "completed":
                attempt["status"] = receipt["status"]
                attempt["error_code"] = receipt.get("error_code")
                return _write_attempt(attempt_path, attempt, now)
            urls = receipt.get("result_urls", receipt.get("result_paths", []))
            if len(urls) > 16:
                raise ValueError("provider returned too many image candidates")
            attempt["status"] = "completed"
            for index, url in enumerate(urls, 1):
                if any(item["index"] == index for item in attempt["outputs"]):
                    continue
                if "result_paths" in receipt:
                    path = Path(url).resolve()
                    path.relative_to(repo_path(root, attempt["output_dir"]))
                    data = path.read_bytes()
                else:
                    data = adapter.transport.read_image(url)
                attempt["outputs"].append(_save_image(attempt, index, data, root))
                _write_attempt(attempt_path, attempt, now)
            attempt["status"] = "downloaded" if len(urls) == attempt["quantity"] else "needs_attention"
        _write_attempt(attempt_path, attempt, now)
        manifest_path = repo_path(root, attempt["output_dir"]) / "download-manifest.json"
        dump_json(manifest_path, {"schema_version": 1, "attempt_id": attempt["attempt_id"], "request_fingerprint": attempt["request_fingerprint"], "status": attempt["status"], "provider": attempt["provider"], "model": attempt["model"], "outputs": attempt["outputs"], "errors": attempt["errors"]})
        _ready_workflow(attempt, root, now)
        return attempt
