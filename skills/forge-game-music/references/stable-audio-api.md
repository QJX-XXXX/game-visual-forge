# Stable Audio 3.0 API reference

## Verified route

This skill targets Stable Audio 3.0, separate from the local Small-SFX model. The official asynchronous route is:

- `POST https://api.stability.ai/v2beta/audio/stable-audio/text-to-audio`
- `GET https://api.stability.ai/v2beta/audio/results/{id}`

The submit request is multipart with a bearer credential, prompt, model `stable-audio-3`, duration from 1 to 380 seconds, seed from 0 to 4294967294, steps from 4 to 8, CFG scale from 1 to 25, and `mp3` or `wav` output. A successful submission returns HTTP 202 and an ID. A 202 result query means processing; 200 provides the audio; 404 means the result is missing or expired. The observed result-retention guidance is 24 hours, so successful audio is downloaded immediately.

The current pricing snapshot is 26 credits per successful result, with pricing subject to the account's current plan. A failed generation is documented as not charged. The adapter records the date and account response instead of treating this estimate as a permanent price.

## Vocal policy

Stable Audio is primarily an instrumental route for this skill. A request that explicitly requires lyrics or singing is rejected during preflight with `unsupported` and kept available for a different provider. Non-lexical vocal-like texture may still occur in an instrumental result; listening review must check it. `standalone-instrumental` therefore has a strict review rule that rejects audible voice-like content.

Do not use the local Small-SFX model's 120-second contract or any older synchronous endpoint for this route. Do not automatically retry a paid POST after an unknown response. If a task ID exists, query and download only; if it does not, preserve `submission_unknown` and require explicit resolution.

## Sources

- [Stability API reference](https://platform.stability.ai/docs/api-reference) — verified 2026-10-10; endpoint, request, async response, and result query.
- [Stability pricing](https://platform.stability.ai/pricing) — verified 2026-10-10; credit snapshot.
- [Stable Audio 3 prompt guide](https://kb.stability.ai/knowledge-base/stable-audio-3-prompt-guide) — verified 2026-10-10; instrumental prompt guidance and vocal caveat.
- [Stable Audio commercial usage](https://kb.stability.ai/knowledge-base/stable-audio-commerical-and-usage-licensing) — verified 2026-10-10; game embedding is allowed subject to the service terms and policy.
