# Civienta

Campus-only web platform for Istinye University students, built by the GDG Istinye software team.

- **Listings and matching:** campus startups, clubs and social projects post listings, students apply with their skill profile.
- **Course notes:** notes, summaries and resources shared by department and course.
- **Verified profile:** finished work is confirmed by the listing owner and shows up on the student's profile as a portfolio.
- **AI:** listings picked for you (embedding based), team suggestions, skill gap hints.

Goal: live on campus in February 2027.

## Repo layout

```
apps/web/      Next.js app
services/ai/   FastAPI recommendation service
firebase/      Firestore rules, indexes, rules tests, seed data
shared/        skills.json, departments.json, courses.json
docs/          data-model.md, api/, decisions/, sprint-0.md
scripts/       helper scripts for maintainers
```

Rules for people and AI tools working in this repo are in [AGENTS.md](AGENTS.md).

## This repo is public

Anyone can read the code, issues and pull requests ([why](docs/decisions/003-public-repo.md)). Never commit `.env` files, API keys or service account JSON, and keep personal information out of issues, PRs and seed data. If a secret is pushed by mistake, tell Serhan right away so it can be rotated.

## Local setup

1. Clone the repo and install Node.js 26.13.1 (pinned in `.nvmrc`).
2. `apps/web`: install and run the app:
   ```bash
   cd apps/web
   npm ci
   npm run dev
   ```
   Open http://localhost:3000 in your browser.
3. Firebase Auth and Firestore emulators:
   - Install the Java 21 JDK. Check that `java -version` runs in your terminal.
   - From the repository root, run `npm ci` and then `npm run emulators`. Keep this terminal open.
   - In a second terminal at the repository root, run `npm run seed` to create 10 fictional Auth accounts and Firestore profiles, 15 listings, and 20 course notes. Run it again to recreate missing fixtures.
   - Open [Emulator UI](http://127.0.0.1:4000) to inspect the `demo-civienta` data. Local test accounts use `ornek.ogrenciNN@stu.istinye.edu.tr` and the fixture password pattern `civienta-local-fixture-NN`, with `NN` from `01` to `10`.
   - To test the Firestore rules, stop the running emulator with `Ctrl+C` and run `npm run test:rules` from the repository root. The command starts and stops the test emulator automatically.
4. `services/ai`: Python environment and run command (later, not in Sprint 0).

## Contributing

1. Pick a task from the board. One task = one issue = one branch = one PR.
2. Branch name: `feat/<issue>-short-name` or `fix/<issue>-short-name`.
3. Open a PR with `Closes #<issue>` and check the preview link.
4. Serhan reviews and merges.

## Maintainers

Branch protection for `main` (repository Settings, Rules, Rulesets, New branch ruleset):

- Target: default branch.
- Require a pull request before merging, 1 approval.
- Require review from Code Owners. `.github/CODEOWNERS` lists only the tech lead, so only his approval counts.
- Block force pushes and branch deletion.
- Bypass list: the Repository admin role, so the tech lead can merge his own PRs. Organization owners also have this role; they do not open PRs here.

Also enable secret scanning and push protection (repository Settings, Advanced Security).

Sprint issues can be created in bulk with `scripts/create-sprint-0-issues.sh` (see the comments at the top of the script).
