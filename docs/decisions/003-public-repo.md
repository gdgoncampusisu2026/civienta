# 003 - Public repository

Date: 2026-11-22
Owner: Serhan
Status: accepted

## Context
The repo lives in the club's GitHub organization. Everything must run on free plans. Two free-plan limits apply to private repositories owned by an organization:

- GitHub Free for organizations has rulesets and branch protection only on public repositories. Without them we cannot enforce "no direct pushes to main, only Serhan merges" (S0-01).
- Vercel Hobby cannot deploy from a private repository owned by a GitHub organization, so PR preview links would not work (S0-06).

## Options
1. Private repo, GitHub Team through a faculty advisor's GitHub Education application, fork-based workflow until it is approved, and a different host for previews. Keeps the code private, but adds setup work, waiting time and an unverified hosting alternative.
2. Public repo. Rulesets and Vercel previews work for free today. The code is visible to anyone.

## Decision
The repo is public. The product launching later does not require the source to be secret, and a public repo meets both Sprint 0 acceptance criteria without paid plans. Visibility can be changed later if needed.

## Consequences
- Anyone can read the code, issues, pull requests and comments. Keep personal or private information out of them.
- Never commit secrets: `.env` files, API keys, service account JSON (already in AGENTS.md). If a secret is pushed, rotate it immediately. Deleting the commit is not enough.
- The Firebase web config is public by design. Data is protected by `firestore.rules`, so every rule needs allow and deny tests (see `docs/data-model.md`).
- Seed and test data must be fake. No real student names, emails or student numbers.
- Secret scanning and push protection are enabled on the repo (free for public repositories).
- A good portfolio side effect: team members can link the repo in their CVs.
