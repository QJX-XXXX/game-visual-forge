from __future__ import annotations

from pathlib import Path

from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.providers.image import (
    confirm_image_attempt, download_image_attempt, image_adapter,
    prepare_image_attempt, query_image_attempt, submit_image_attempt,
)


def register_image_commands(commands):
    image = commands.add_parser("image", help="Shared image API, CLI and MCP generation and recovery")
    provider = image.add_subparsers(dest="image_command", required=True).add_parser("provider")
    operations = provider.add_subparsers(dest="image_provider_command", required=True)
    for name in ("models", "preflight"):
        command = operations.add_parser(name)
        command.add_argument("--provider", choices=("minimax", "jimeng", "dreamina", "wanxiang"), default="minimax")
        command.add_argument("--out", type=Path)
        command.add_argument("--backend", choices=("api", "cli", "mcp"))
        command.add_argument("--execution", type=Path, help="Non-secret execution JSON, bound to the attempt")
    prepare = operations.add_parser("prepare")
    prepare.add_argument("--request", type=Path, required=True)
    prepare.add_argument("--decision", type=Path, required=True)
    prepare.add_argument("--parameters", type=Path)
    prepare.add_argument("--backend", choices=("api", "cli", "mcp"))
    prepare.add_argument("--execution", type=Path)
    prepare.add_argument("--kind", choices=("sprite", "map", "tilemap"), default="sprite")
    prepare.add_argument("--model", help="Defaults to the selected provider's first documented model")
    prepare.add_argument("--quantity", type=int, default=1, help="Image candidates; a whole sprite sheet is one image")
    prepare.add_argument("--state", type=Path)
    prepare.add_argument("--out", type=Path, required=True)
    confirm = operations.add_parser("confirm")
    confirm.add_argument("--attempt", type=Path, required=True)
    confirm.add_argument("--quote", type=Path, required=True)
    confirm.add_argument("--out", type=Path, required=True)
    for name in ("submit", "query", "download"):
        command = operations.add_parser(name)
        command.add_argument("--attempt", type=Path, required=True)
        if name == "submit":
            command.add_argument("--confirmation", type=Path, required=True)
        if name == "query":
            command.add_argument("--task-id", help="Recover an unknown async submission using a provider-verified task ID")
        command.add_argument("--repo-root", type=Path, required=True)
        command.add_argument("--now", required=True)
    prepare.add_argument("--repo-root", type=Path, required=True)
    prepare.add_argument("--now", required=True)
    confirm.add_argument("--now", required=True)


def dispatch_image_command(args):
    operation = args.image_provider_command
    execution = load_json(args.execution) if getattr(args, "execution", None) else None
    backend = getattr(args, "backend", None)
    if backend and backend != "api":
        execution = dict(execution or {})
        if "backend" in execution and execution["backend"] != backend:
            raise ValueError("backend conflicts with execution configuration")
        execution["backend"] = backend
    elif backend == "api" and execution:
        raise ValueError("API execution uses provider parameters and environment credentials")
    if operation in {"models", "preflight"}:
        payload = getattr(image_adapter(args.provider, execution=execution), operation)()
        if args.out:
            dump_json(args.out, payload)
        return payload
    if operation == "prepare":
        decision = load_json(args.decision)
        provider = decision.get("selected_provider")
        parameters = load_json(args.parameters) if args.parameters else {}
        selected_execution = execution or parameters.get("execution")
        if selected_execution is None and decision.get("selected_backend") in {"cli", "mcp"}:
            selected_execution = {"backend": decision["selected_backend"]}
        if backend and decision.get("selected_backend") and backend != decision["selected_backend"]:
            raise ValueError("backend differs from the selected source route")
        if backend == "api" and parameters.get("execution"):
            raise ValueError("backend conflicts with parameters.execution")
        model = args.model or image_adapter(provider, execution=selected_execution).models()["models"][0]["model"]
        return prepare_image_attempt(args.request, args.decision, args.parameters, args.out, kind=args.kind, model=model, quantity=args.quantity, state_path=args.state, repo_root=args.repo_root, now=args.now, execution=execution)
    if operation == "confirm":
        return confirm_image_attempt(args.attempt, args.quote, args.out, now=args.now)
    if operation == "submit":
        return submit_image_attempt(args.attempt, args.confirmation, repo_root=args.repo_root, now=args.now)
    if operation == "query":
        return query_image_attempt(args.attempt, repo_root=args.repo_root, now=args.now, recovered_task_id=args.task_id)
    if operation == "download":
        return download_image_attempt(args.attempt, repo_root=args.repo_root, now=args.now)
    raise ValueError("unsupported image provider command")
