from __future__ import annotations

import hashlib
import json
from pathlib import Path

from game_visual_forge.contracts.music import MusicRequest, MusicProcessingOptions, MusicProcessingResult, MusicSourceRecord, build_music_prompt_package
from game_visual_forge.contracts.music_provider import MusicProvider, MusicGenerationAttempt, MusicPaidConfirmation, MusicProviderCapability, MusicProviderReceipt, default_music_capabilities
from game_visual_forge.contracts.music_review import MusicQualityReport, MusicReview
from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.routing.music import route_music
from game_visual_forge.processing.music import ingest_music_source, process_music_candidate
from game_visual_forge.quality.music import assess_music_outputs, record_music_review, publish_music_bundle
from game_visual_forge.providers.music import prepare_music_attempt, begin_music_submission, record_music_receipt, submit_cloud_music_attempt, query_cloud_music_attempt, download_cloud_music_attempt


def _request(path): return MusicRequest.from_dict(load_json(Path(path)))


def run_music_plan(request_path: Path, out_dir: Path, *, now: str):
    request = _request(request_path); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    cap = default_music_capabilities(local_ready=False)[MusicProvider.COMFYUI_MUSIC3]
    prompt = build_music_prompt_package(request, MusicProvider.COMFYUI_MUSIC3, request.brief)
    plan = {"schema_version": 1, "status": "planned", "created_at": now, "request": request.to_dict(), "default_provider": MusicProvider.COMFYUI_MUSIC3.value, "prompt": prompt.to_dict(), "references": ["skills/forge-game-music/references/prompt-guide.md", "skills/forge-game-music/references/game-music-templates.md"], "provider_capability": cap.to_dict()}
    dump_json(out_dir / "music-plan.json", plan)
    return plan


def run_music_route(request_path: Path, capabilities_path: Path | None, selection: str | None, out: Path, state: Path, *, now: str):
    request = _request(request_path); capabilities = default_music_capabilities(local_ready=False)
    if capabilities_path:
        raw = load_json(Path(capabilities_path)); items = raw if isinstance(raw, list) else raw.get("capabilities", [])
        capability_type = __import__("game_visual_forge.contracts.music_provider", fromlist=["MusicProviderCapability"]).MusicProviderCapability
        capabilities = {MusicProvider(item["provider"]): capability_type.from_dict(item) for item in items}
    decision = route_music(request, capabilities, selection)
    value = {"schema_version": 1, "status": decision.status, "selected_provider": decision.selected_provider.value, "reason": decision.reason, "requires_paid_confirmation": decision.requires_paid_confirmation, "now": now, "request_sha256": hashlib.sha256(json.dumps(request.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()}
    dump_json(Path(out), value); dump_json(Path(state), value); return value


def run_music_provider_preflight(provider: str):
    from game_visual_forge.providers.suno_music import preflight as suno_preflight
    from game_visual_forge.providers.stable_audio_music import preflight as stable_preflight
    if provider == MusicProvider.SUNO_API.value: return suno_preflight({})
    if provider == MusicProvider.STABLE_AUDIO_API.value: return stable_preflight({"duration": 1, "prompt": "instrumental"})
    return {"status": "needs_user_action", "reason": "Comfy MCP workflow inspection must run in the active Comfy Desktop session"}


def run_music_prepare(request_path, prompt_path, capability_path, parameters_path, out, now):
    request = _request(request_path); prompt = __import__("game_visual_forge.contracts.music", fromlist=["MusicPromptPackage"]).MusicPromptPackage(**load_json(Path(prompt_path))); capability = MusicProviderCapability.from_dict(load_json(Path(capability_path))); parameters = load_json(Path(parameters_path)); attempt = prepare_music_attempt(request, prompt, capability, parameters, now=now); dump_json(Path(out), attempt.to_dict()); return attempt.to_dict()


def run_music_begin(attempt_path, confirmation_path, now):
    return begin_music_submission(Path(attempt_path), Path(confirmation_path) if confirmation_path else None, now=now).to_dict()


def run_music_record_receipt(attempt_path, receipt_path, now):
    return record_music_receipt(Path(attempt_path), MusicProviderReceipt.from_dict(load_json(Path(receipt_path))), now=now).to_dict()


def run_music_submit(attempt_path, confirmation_path, executable, now):
    return submit_cloud_music_attempt(Path(attempt_path), Path(confirmation_path), Path(executable), now=now).to_dict()


def run_music_query(attempt_path, executable, now):
    return query_cloud_music_attempt(Path(attempt_path), Path(executable), now=now).to_dict()


def run_music_download(attempt_path, executable, output_dir, now):
    return download_cloud_music_attempt(Path(attempt_path), Path(executable), Path(output_dir), now=now).to_dict()


def run_music_ingest(request_path, source_path, repo_root, attempt_path, out, ffprobe=None):
    del request_path, ffprobe
    attempt = MusicGenerationAttempt.from_dict(load_json(Path(attempt_path)))
    source = ingest_music_source(Path(repo_root), Path(source_path), attempt, Path("unused"))
    dump_json(Path(out), source.to_dict()); return source.to_dict()


def run_music_process(source_path, options_path, repo_root, out, ffmpeg=None, ffprobe=None):
    source = MusicSourceRecord.from_dict(load_json(Path(source_path)))
    options = MusicProcessingOptions.from_dict(load_json(Path(options_path))) if options_path else MusicProcessingOptions()
    result = process_music_candidate(Path(repo_root), source, options, Path(ffmpeg or "unused"), Path(ffprobe or "unused"))
    dump_json(Path(out), result.to_dict()); return result.to_dict()


def run_music_record_review(request_path, processing_path, quality_path, checks_path, out, repo_root, now):
    request = _request(request_path); processing = MusicProcessingResult(**load_json(Path(processing_path))); quality = MusicQualityReport.from_dict(load_json(Path(quality_path))); checks = load_json(Path(checks_path))
    review = record_music_review(request, processing, quality, checks, now, repo_root)
    dump_json(Path(out), review.to_dict()); return review.to_dict()


def run_music_validate(request_path, processing_path, quality_path, review_path, repo_root, final_dir):
    request = _request(request_path); processing = MusicProcessingResult(**load_json(Path(processing_path))); quality = MusicQualityReport.from_dict(load_json(Path(quality_path))); review = MusicReview.from_dict(load_json(Path(review_path)))
    return publish_music_bundle(Path(repo_root), request, processing, quality, review, Path(final_dir))


def register_music_commands(audio_commands):
    music = audio_commands.add_parser("music", help="Create reviewed game BGM and instrumental music")
    commands = music.add_subparsers(dest="audio_music_command", required=True)
    plan = commands.add_parser("plan"); plan.add_argument("--request", type=Path, required=True); plan.add_argument("--out-dir", type=Path, required=True); plan.add_argument("--now", required=True)
    route = commands.add_parser("route"); route.add_argument("--request", type=Path, required=True); route.add_argument("--capabilities", type=Path); route.add_argument("--selection", choices=[item.value for item in MusicProvider]); route.add_argument("--out", type=Path, required=True); route.add_argument("--state", type=Path, required=True); route.add_argument("--now", required=True)
    ingest = commands.add_parser("ingest"); ingest.add_argument("--request", type=Path); ingest.add_argument("--source", type=Path, required=True); ingest.add_argument("--repo-root", type=Path, required=True); ingest.add_argument("--attempt", type=Path, required=True); ingest.add_argument("--out", type=Path, required=True)
    process = commands.add_parser("process"); process.add_argument("--source-record", type=Path, required=True); process.add_argument("--options", type=Path); process.add_argument("--repo-root", type=Path, required=True); process.add_argument("--out", type=Path, required=True); process.add_argument("--ffmpeg", type=Path); process.add_argument("--ffprobe", type=Path)
    review = commands.add_parser("record-review"); review.add_argument("--request", type=Path, required=True); review.add_argument("--processing", type=Path, required=True); review.add_argument("--quality", type=Path, required=True); review.add_argument("--checks", type=Path, required=True); review.add_argument("--repo-root", type=Path, required=True); review.add_argument("--out", type=Path, required=True); review.add_argument("--now", required=True)
    validate = commands.add_parser("validate"); validate.add_argument("--request", type=Path, required=True); validate.add_argument("--processing", type=Path, required=True); validate.add_argument("--quality", type=Path, required=True); validate.add_argument("--review", type=Path, required=True); validate.add_argument("--repo-root", type=Path, required=True); validate.add_argument("--final-dir", type=Path, required=True)
    provider = commands.add_parser("provider"); provider_commands = provider.add_subparsers(dest="audio_music_provider_command", required=True)
    preflight = provider_commands.add_parser("preflight"); preflight.add_argument("--provider", choices=[item.value for item in MusicProvider], default=MusicProvider.COMFYUI_MUSIC3.value)
    prepare = provider_commands.add_parser("prepare"); prepare.add_argument("--request", type=Path, required=True); prepare.add_argument("--prompt", type=Path, required=True); prepare.add_argument("--capability", type=Path, required=True); prepare.add_argument("--parameters", type=Path, required=True); prepare.add_argument("--out", type=Path, required=True); prepare.add_argument("--now", required=True)
    begin = provider_commands.add_parser("begin-submit"); begin.add_argument("--attempt", type=Path, required=True); begin.add_argument("--confirmation", type=Path); begin.add_argument("--now", required=True)
    receipt = provider_commands.add_parser("record-receipt"); receipt.add_argument("--attempt", type=Path, required=True); receipt.add_argument("--receipt", type=Path, required=True); receipt.add_argument("--now", required=True)
    submit = provider_commands.add_parser("submit"); submit.add_argument("--attempt", type=Path, required=True); submit.add_argument("--confirmation", type=Path, required=True); submit.add_argument("--executable", type=Path, required=True); submit.add_argument("--now", required=True)
    query = provider_commands.add_parser("query"); query.add_argument("--attempt", type=Path, required=True); query.add_argument("--executable", type=Path, required=True); query.add_argument("--now", required=True)
    download = provider_commands.add_parser("download"); download.add_argument("--attempt", type=Path, required=True); download.add_argument("--executable", type=Path, required=True); download.add_argument("--output-dir", type=Path, required=True); download.add_argument("--now", required=True)


def dispatch_music_command(args):
    if args.audio_music_command == "plan": return run_music_plan(args.request, args.out_dir, now=args.now)
    if args.audio_music_command == "route": return run_music_route(args.request, args.capabilities, args.selection, args.out, args.state, now=args.now)
    if args.audio_music_command == "ingest": return run_music_ingest(args.request, args.source, args.repo_root, args.attempt, args.out)
    if args.audio_music_command == "process": return run_music_process(args.source_record, args.options, args.repo_root, args.out, args.ffmpeg, args.ffprobe)
    if args.audio_music_command == "record-review": return run_music_record_review(args.request, args.processing, args.quality, args.checks, args.out, args.repo_root, args.now)
    if args.audio_music_command == "validate": return run_music_validate(args.request, args.processing, args.quality, args.review, args.repo_root, args.final_dir)
    if args.audio_music_command == "provider" and args.audio_music_provider_command == "preflight": return run_music_provider_preflight(args.provider)
    if args.audio_music_command == "provider" and args.audio_music_provider_command == "prepare": return run_music_prepare(args.request, args.prompt, args.capability, args.parameters, args.out, args.now)
    if args.audio_music_command == "provider" and args.audio_music_provider_command == "begin-submit": return run_music_begin(args.attempt, args.confirmation, args.now)
    if args.audio_music_command == "provider" and args.audio_music_provider_command == "record-receipt": return run_music_record_receipt(args.attempt, args.receipt, args.now)
    if args.audio_music_command == "provider" and args.audio_music_provider_command == "submit": return run_music_submit(args.attempt, args.confirmation, args.executable, args.now)
    if args.audio_music_command == "provider" and args.audio_music_provider_command == "query": return run_music_query(args.attempt, args.executable, args.now)
    if args.audio_music_command == "provider" and args.audio_music_provider_command == "download": return run_music_download(args.attempt, args.executable, args.output_dir, args.now)
    raise ValueError("unsupported music command")
