---
description: Use Context Hub via the `chub` CLI to fetch current third-party API, SDK, and library documentation before writing integration code.
---
# Context Hub API Docs via chub

Use this workflow when you need documentation for a third-party library, SDK, or API before writing code that uses it.

Examples:
- User asks to use the OpenAI API
- User asks to call Stripe, Anthropic, Pinecone, or another external API
- You need current SDK syntax rather than relying on training knowledge
- You are about to write integration code and the external surface may have changed

Fetch docs with `chub` before answering whenever current API reference matters.

## Step 1 — Find the right doc ID

Run:

```bash
chub search "<library name>" --json
```

Pick the best matching `id` from the results.

Examples:
- `openai/chat`
- `anthropic/sdk`
- `stripe/api`

If nothing matches, try a broader or simpler term.

## Step 2 — Fetch the docs

Run:

```bash
chub get <id> --lang py
```

Or use another language variant when appropriate:

```bash
chub get <id> --lang js
chub get <id> --lang ts
```

If the doc only has one language variant, omit `--lang` and let `chub` auto-select.

## Step 3 — Use the docs, not memory

Read the fetched content and use it to answer the question or write code.

Rules:
- Prefer the fetched docs over memorized API shapes
- Match the language the user is working in
- If the docs conflict with prior assumptions, trust the docs
- If the docs are incomplete, say so explicitly instead of inventing missing API details

## Step 4 — Capture useful local annotations

After completing the task, if you learned a concise, actionable detail that is not already obvious from the docs, save it locally:

```bash
chub annotate <id> "Webhook verification requires raw body — do not parse before verifying"
```

Good annotations:
- Version quirks
- Gotchas
- Workarounds
- Project-specific integration notes

Do not annotate things already clearly stated in the fetched doc.

You can inspect saved notes with:

```bash
chub annotate --list
```

## Step 5 — Ask before sending feedback

If the docs were especially good or clearly flawed, ask the user before sending feedback.

Examples:

```bash
chub feedback <id> up
chub feedback <id> down --label outdated
```

Available labels:
- `outdated`
- `inaccurate`
- `incomplete`
- `wrong-examples`
- `wrong-version`
- `poorly-structured`
- `accurate`
- `well-structured`
- `helpful`
- `good-examples`

Never send feedback without asking the user first.

## Quick reference

| Goal | Command |
|------|---------|
| List everything | `chub search` |
| Find a doc | `chub search "stripe"` |
| Exact id detail | `chub search stripe/api` |
| Fetch Python docs | `chub get stripe/api --lang py` |
| Fetch JS docs | `chub get openai/chat --lang js` |
| Save to file | `chub get anthropic/sdk --lang py -o docs.md` |
| Fetch multiple | `chub get openai/chat stripe/api --lang py` |
| Save a note | `chub annotate stripe/api "needs raw body"` |
| List notes | `chub annotate --list` |
| Rate a doc | `chub feedback stripe/api up` |

## Notes

- `chub search` with no query lists everything available
- IDs are typically `<author>/<name>` — confirm the ID from search before fetching
- If multiple languages exist and you do not pass `--lang`, `chub` will show available options
- Assume this workflow requires `chub` to be installed and available on PATH
- If `chub` is not available, stop and ask the user for the installation path or PATH setup
