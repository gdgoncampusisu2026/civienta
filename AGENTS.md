# Civienta - agent rules

Campus-only web platform for Istinye University students: listings and matching, course notes, verified profile. Read `docs/data-model.md` before touching any data code.

## Stack
- `apps/web`: Next.js, TypeScript, Tailwind, shadcn/ui. Hosted on Vercel.
- Firebase: Auth and Firestore on the free Spark plan.
- `services/ai`: Python, FastAPI, multilingual embeddings, vectors stored in Firestore.
- Sign-in: school account only (`@stu.istinye.edu.tr`).

## Rules
- Firestore is accessed only from `apps/web/src/features/*/api.ts`. Components never call Firestore directly.
- Skills, departments and courses come from `shared/*.json`. Do not hardcode these lists.
- Collection names and relations are fixed by `docs/data-model.md`. Fields can change: update the doc in the same PR.
- Everything must run on free plans. No Cloud Functions, no paid services, no credit card.
- In the MVP, course notes are links (OneDrive or Drive), not file uploads.
- Never commit secrets: `.env` files, API keys, service account JSON.

## Code style
- Code, identifiers, file names, commit messages and docs are in English.
- Code comments, docstrings and console messages are in Turkish.
- Run lint and tests before opening a PR.

## Git
- One task = one issue = one branch = one PR.
- Branch names: `feat/<issue>-short-name` or `fix/<issue>-short-name`.
- PR description includes `Closes #<issue>`. Check your change on the preview link.
- Keep PRs focused. Split big tasks into smaller ones.
- No direct pushes to `main`. Serhan reviews and merges.

## Keeping this file useful
- Only rules that apply to everyone go here. Keep it short.
- No personal notes, long explanations or temporary info.
- Folder-specific rules go in that folder's own `AGENTS.md`.
- Changes to this file go in a separate PR.
