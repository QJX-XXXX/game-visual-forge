# Provider CLI and MCP

Use the Agent's native image tool first. When it cannot perform the required
operation, ask the user to select an external source. Recommend MiniMax among
external image providers. Then select an API, installed CLI, or MCP route and
show its model, account/region, parameters and total cost before confirmation.

## Prerequisites and installation

Run the [Python environment check](python-environment.md) for the actual OS and
interpreter. Explain missing Python or packages and provide environment-specific
instructions. Help set up the environment when the user authorizes installation.
The optional MCP runtime uses Python 3.11+, `mcp>=2,<3` and Pillow.

Generation, query, download and preflight commands never install a vendor tool,
run a package downloader, authenticate an account, or register an MCP server.
Missing prerequisites return `requires_installation_confirmation=true` and an
official setup link. Obtain the user's installation confirmation before following
that setup procedure. Login and paid-generation consent are separate user actions.

After installation approval, the project MCP extra can be installed in the
selected environment with `python -m pip install -e ".[mcp]"` from this repository.
Use the selected interpreter's absolute path when multiple environments exist.

| Provider | Installed CLI | MCP route | Image model |
| --- | --- | --- | --- |
| MiniMax | `mmx` | Official local `minimax-mcp`, stdio | `MiniMax-H3-Image` |
| Jimeng / Dreamina | `dreamina` | Project-provided stdio workflow bridge | `dreamina-default` for CLI, API profile separately |
| Wanxiang | `bl` | Official Bailian `TextGenerateImage`; project bridge for explicit Wan models | CLI/bridge `wan2.7-image` / `wan2.7-image-pro`; official MCP `bailian-image-auto` |

The official Bailian MCP tool selects its own model and exposes no `model`
parameter. Its profile identifies a server preset. For a specific Wan model,
select CLI/API execution or register the project Wanxiang MCP bridge described
below. The MiniMax API also retains the
Highspeed profile. The current official tools expose the verified H3 image
profile listed above.

Official setup and contract sources are the [MiniMax CLI](https://github.com/MiniMax-AI/cli),
[MiniMax MCP](https://github.com/MiniMax-AI/MiniMax-MCP),
[Dreamina CLI](https://jimeng.jianying.com/cli),
[Bailian CLI](https://help.aliyun.com/zh/model-studio/cli/overview), and
[Bailian MCP integration](https://help.aliyun.com/zh/model-studio/cli/mcp-skill).

## Image execution

Use any visual Skill's `scripts/run.py` launcher for the shared commands.
Append `--backend cli` or `--backend mcp` to `image provider models`,
`preflight`, and `prepare`. An existing source decision carries its selected
backend into preparation. Without a backend selection, the existing API default
applies.

```powershell
python skills/forge-2d-sprite/scripts/run.py image provider models --provider minimax --backend cli
python skills/forge-2d-sprite/scripts/run.py image provider preflight --provider minimax --backend cli
python skills/forge-2d-sprite/scripts/run.py image provider models --provider wanxiang --backend mcp
```

Preflight checks installed prerequisites and credential presence locally.
`authenticated=false` / `authentication_verified=false` leave live account
verification pending. A ready CLI/MCP installation can be explicitly selected
while its authentication is unverified. A verified authentication failure or
missing prerequisites blocks that route. Before an MCP submission consumes confirmation, the
adapter connects, discovers the required tool and validates arguments against
its current JSON Schema.

For custom installed paths or connections, pass `--execution <json-file>` to
models, preflight or prepare. The same object may be placed in the image
parameters under `execution`. A CLI example follows.

```json
{"backend":"cli","command":["C:/Tools/mmx.exe"],"timeout_seconds":600}
```

MiniMax official MCP uses the already installed server executable.

```json
{"backend":"mcp","transport":"stdio","command":["minimax-mcp"],"credential_env":"MINIMAX_API_KEY","timeout_seconds":900}
```

The adapter supplies the confirmed MiniMax region through `MINIMAX_API_HOST`
and requests URL results through `MINIMAX_API_RESOURCE_MODE=url`. It downloads
and validates results using the project's image processing path.

Bailian's official default MCP connection is equivalent to the following.

```json
{"backend":"mcp","transport":"streamable-http","url":"https://dashscope.aliyuncs.com/api/v1/mcps/TextGenerateImage/mcp","credential_env":"DASHSCOPE_API_KEY","timeout_seconds":600}
```

Store environment variable names in configuration. Put credential values in
the process environment or the user's secret store. Endpoint URLs must exclude
credentials and query parameters. Stdio commands must invoke existing
executables. Generation rejects installing launchers such as `uvx` and `npx`.

Execution configuration is bound inside attempt parameters and the existing
one-time paid confirmation. Submit, query and download reuse that configuration.
Changing the provider, model, backend or connection requires a new prepared
attempt and confirmation.

Follow the existing [image workflow](../skills/forge-2d-sprite/references/image-api.md)
for source selection, preparation, cost confirmation, submission and ingestion.
MiniMax and Wan CLI/MCP image calls complete synchronously. An uncertain result
can recover downloaded local output without another generation. Dreamina keeps
`submit_id` and uses `query_result --submit_id=... --download_dir=...` to fetch
the existing task. Its preview URL fields are unsuitable for final downloads.
Before submission, Dreamina parameters are checked against the installed
subcommand's `-h`; model selection uses the tool's current default profile.

## Jimeng MCP bridge

Register the project bridge in the user's Agent only after they choose to
configure MCP. Use the already configured Python interpreter and intact
repository. A host-neutral registration example follows.

```json
{
  "mcpServers": {
    "game-visual-forge-jimeng": {
      "command": "<absolute-python-executable>",
      "args": ["<repo>/skills/forge-2d-sprite/scripts/run.py", "mcp", "serve", "--provider", "jimeng", "--repo-root", "<asset-workspace>"]
    }
  }
}
```

The bridge exposes `jimeng_image_models`, `jimeng_image_preflight`,
`jimeng_image_prepare`, `jimeng_image_confirm`, `jimeng_image_submit`,
`jimeng_image_query`, and `jimeng_image_download`. All paths are workspace-relative.
Preparation selects CLI or API execution inside the bridge. The confirm tool
requires `user_confirmed=true` after explicit user approval and a verified quote.
Submission consumes the same file-backed one-time confirmation used by the CLI.
The bridge also exposes submit/query/download for existing confirmed Jimeng
video attempts. This is the project's bridge, with no claim of a vendor-hosted
Jimeng MCP endpoint.

For a specific Wan model through MCP, use the same bridge registration with
`--provider wanxiang` and a distinct server name. It exposes
`wanxiang_image_models`, `wanxiang_image_preflight`, `wanxiang_image_prepare`,
`wanxiang_image_confirm`, `wanxiang_image_submit`, `wanxiang_image_query`, and
`wanxiang_image_download`. Preparation supports `backend=cli|api` and explicit
`model=wan2.7-image|wan2.7-image-pro`. User-confirmed spending and model/backend
bindings follow the same workflow. The official Bailian MCP remains available
for its server preset. No tools or MCP registrations are installed automatically.

## Existing video routes

MiniMax and Jimeng video wrappers accept explicit `backend=cli` and bind optional
`parameters.execution` to the attempt. Queries and downloads carry the same
configuration. MiniMax CLI supports the base `MiniMax-H3` V2 model. Select API
execution for H3 Highspeed, Lite, or Max. The CLI download
uses the URL returned by the CLI task query and the project's media downloader.
MiniMax's official video MCP has a separate verified `MiniMax-Hailuo-02` profile
for text or first-frame generation. Unsupported H3 video MCP profiles are rejected.
Use the Jimeng bridge with a CLI or API video attempt for MCP access.

Refresh the model snapshot for the selected backend before preparation. A CLI
snapshot and an API snapshot have separate bindings. Missing tools, unsupported
flags and unknown submission results require configuration or recovery of that
route. Repeating a paid submission requires a new user confirmation.
