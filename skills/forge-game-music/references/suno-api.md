# Suno API discovery gate

## Current status

Status is `needs_user_action`. The official platform landing page confirms that Suno offers a REST API product, but anonymous access redirects to account login. As of the 2026-10-10 inspection, the public surface did not expose a readable official API reference, OpenAPI document, request schema, task recovery contract, pricing table, or API-specific game licensing terms.

The adapter must remain disabled until an authorized account supplies official documentation or a written contract. Unknown values stay unknown. This reference deliberately contains no guessed request field names, model identifiers, instrumental controls, task states, candidate counts, or prices.

## Discovery checklist

After the user signs in through the official platform, record the URL and document version/date for:

- base URL, API version, authentication and credential scope;
- prompt, lyric, vocal, instrumental, model, length, format, seed, and candidate fields;
- response shape, candidate count, task identifier, state values, result URL, retention, and cancellation;
- idempotency, rate limits, HTTP errors, retry rules, failure charges, and usage accounting;
- API-specific rights for embedding audio in a commercial game, including plan and download restrictions, attribution, watermark, and disclosure requirements.

Until every required item is verified, a Suno route returns `needs_user_action` with the missing item list. It never falls back to cookies, browser scraping, or an unofficial client. A user can continue with local Music 3 or the verified Stable Audio 3.0 route.

## Rights boundary

The public [Suno Terms](https://suno.com/terms) and [paid-plan help article](https://help.suno.com/en/articles/9601665) discuss commercial use for eligible paid outputs, including video games. Those web terms are not treated as proof of API-account authorization. The [free-plan help article](https://help.suno.com/en/articles/9601601) limits free use to personal, non-commercial use. The API adapter requires the account's own API terms or written confirmation before paid generation.

## Sources

- [Suno Platform](https://platform.suno.com/) — verified 2026-10-10; confirms the official REST API product and login requirement.
- [Suno Terms](https://suno.com/terms) — verified 2026-10-10; web product rights context, not an API schema.
- [Paid plan rights](https://help.suno.com/en/articles/9601665) — verified 2026-10-10; says eligible paid downloads may be used in video games.
- [Free plan rights](https://help.suno.com/en/articles/9601601) — verified 2026-10-10; says free outputs are personal and non-commercial.
- Official account documentation — not available anonymously on 2026-10-10; this is the explicit blocker, not a missing implementation guess.
