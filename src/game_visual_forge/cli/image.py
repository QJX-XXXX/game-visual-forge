from __future__ import annotations

from pathlib import Path

from game_visual_forge.contracts.serialization import dump_json, load_json
from game_visual_forge.providers.image import (
    confirm_image_attempt, download_image_attempt, image_adapter,
    prepare_image_attempt, query_image_attempt, submit_image_attempt,
)


def register_image_commands(commands):
    image = commands.add_parser("image", help="Shared image API generation and recovery")
    provider = image.add_subparsers(dest="image_command", required=True).add_parser("provider")
    operations = provider.add_subparsers(dest="image_provider_command", required=True)
    for name in ("models", "preflight"):
        command = operations.add_parser(name)
        command.add_argument("--provider", choices=("minimax", "jimeng", "dreamina", "wanxiang"), default="minimax")
        command.add_argument("--out", type=Path)
    prepare = operations.add_parser("prepare")
    prepare.add_argument("--request", type=Path, required=True)
    prepare.add_argument("--decision", type=Path, required=True)
    prepare.add_argument("--parameters", type=Path)
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
    if operation in {"models", "preflight"}:
        payload = getattr(image_adapter(args.provider), operation)()
        if args.out:
            dump_json(args.out, payload)
        return payload
    if operation == "prepare":
        provider = load_json(args.decision).get("selected_provider")
        model = args.model or image_adapter(provider).models()["models"][0]["model"]
        return prepare_image_attempt(args.request, args.decision, args.parameters, args.out, kind=args.kind, model=model, quantity=args.quantity, state_path=args.state, repo_root=args.repo_root, now=args.now)
    if operation == "confirm":
        return confirm_image_attempt(args.attempt, args.quote, args.out, now=args.now)
    if operation == "submit":
        return submit_image_attempt(args.attempt, args.confirmation, repo_root=args.repo_root, now=args.now)
    if operation == "query":
        return query_image_attempt(args.attempt, repo_root=args.repo_root, now=args.now, recovered_task_id=args.task_id)
    if operation == "download":
        return download_image_attempt(args.attempt, repo_root=args.repo_root, now=args.now)
    raise ValueError("unsupported image provider command")
