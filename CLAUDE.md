@AGENTS.md

# Claude Code notes

## Session rules
- After finishing any work, stop. List the changed files and a proposed commit message, then wait for an explicit "yes" before commit and push.
- Update the working notes below after every step.

## Working notes
Maintained by the tech lead (Serhan). Other team members do not edit this section. Cleaned up at the start of each sprint.

### Completed
- Local repo skeleton created (folders, AGENTS.md, CLAUDE.md, README, .github templates).
- Data model v1 written (`docs/data-model.md`).
- Sprint 0 task list and issue script prepared (`docs/sprint-0.md`, `scripts/`).
- Public repo decision recorded (`docs/decisions/003-public-repo.md`), linked from README and `docs/sprint-0.md`.
- CODEOWNERS set to `@serhandenizhan`.
- Initial commit `4f5cf72` pushed to `gdgoncampusisu2026/civienta` `main` (public).
- Ruleset `protect-main` active on the default branch: PR required, 1 Code Owner approval, stale approvals dismissed, conversations resolved, squash only, no deletion or force push. Admin bypass for pull requests only. Secret scanning and push protection on. Squash-only merges and auto-delete of head branches in repo settings.
- Direct push to `main` tested and rejected for the admin account.
- PR #1 (working notes) squash-merged; the bypass merge flow works.
- S0-03 done: Onuralp and Melike approved data model v1 over WhatsApp with no changes. Issue #4 closed, board card Done, status line updated in `docs/data-model.md` (PR #16 merged).
- Board `Civienta` created and linked: https://github.com/orgs/gdgoncampusisu2026/projects/1 (the "item closed -> Done" workflow does not fire, move cards by hand).

### In Progress
- S0-01: README local setup steps fill in as S0-05 and S0-07 land. AGENTS.md check in Claude, Codex and Gemini still to do.
- S0-02: Firebase project `civienta-gdg` created (Spark, Firestore `(default)` in Frankfurt, production mode, web app registered). Team invites come later (needs everyone's Google account).
- S0-04: 14 Sprint 0 issues opened (#2 to #15, S0-01 to S0-14, label `sprint-0`) with `owner:<name>` labels and the owner name in the issue body. Board: https://github.com/orgs/gdgoncampusisu2026/projects/1 (Status: Todo / In Progress / Review / Done, repo linked, all 14 issues added, Serhan's 4 In Progress). Assigned so far: Serhan (#2-#5), Melike (#10), Buse (#11, #12). Still to assign when they join the org: Layan (#6, #7), Onuralp (#8, #9), Mustafa (#13, #14), Batuhan (#15). The org owner (Mehmet) invites; `civienta-team` has Write on the repo, Serhan adds members to the team as they join. Labels stay next to assignees. Do not run the issue script again (it would duplicate the issues).

### Org roles
- `gdgoncampusisu` is the club's account, `vmhmtemin` is the club organizer (org owner). Neither writes code.

### Decisions
- Ruleset bypass for the Repository admin role is fine (org owners also get it, they will not open PRs).
- Repo is public, so rulesets and Vercel previews work on free plans. Announced to the team and the GDG organizer through ADR 003 (and the next PDF).

### Decisions on Buse's S0-10 questions (final 2026-11-23)
PDF for Buse: `~/Desktop/GDG/GDG_Istinye_Kararlar_TR.pdf` (kept outside the repo).
- Gemini free tier with real student data: not acceptable. Unpaid quota content may be used to improve Google products and reviewed by humans, and the terms say not to send personal data (archived 2025 terms, re-check the live page). Paid terms need billing, which AGENTS.md forbids. Gemini is fine for the benchmark on synthetic data only. Leaning to a local model (e5-small or MiniLM) for production.
- Firestore Spark: 50K reads, 20K writes per day, 1 GiB, resets at midnight Pacific (about 11:00 Istanbul in winter). Expected scale is not defined anywhere: Serhan sets planning numbers. Rules `get()`/`getAfter()` and vector query index entries also count as reads. Plan: stay on Spark for the pilot, one-time queries plus client cache instead of listeners, small pages, separate dev Firebase project for previews and tests, no whole-collection client-side note search, recommendations returned as ids by the AI service. Growth ladder: trigger is daily reads above about 35K for several days, then extra optimization (data bundle, AI cache), then a free move to Supabase or Cloudflare D1, and a paid Blaze plan only as a temporary last resort (needs a card and organizer approval, AGENTS.md rule changes in its own PR). Decided: stay on Spark, no switch to D1 now (stack change, rules rewrite, limits are enforced there too).
- Vector search: decided to compute similarity in memory (cosine) in the AI service from the start, no dependency on Firestore vector search. The emulator runs `findNearest` on top-level vector fields (open bug for nested ones), but parity with production and Spark support were never verified. Embeddings stay in `embedding` as a plain number array.

### Next Steps
- Update `docs/data-model.md`: embedding type (plain number array) and open questions 2 and 3, via PR.
- Create a second Spark project `civienta-dev` for previews and tests (S0-02 follow-up). Write ADR 004 (quota plan) only if wanted.
- Team joins the org (Mehmet invites), Serhan adds members to `civienta-team`, then assign the remaining issues and add everyone to Firebase.
- `GEMINI.md` with `@AGENTS.md` to finish the S0-01 tool check (untested assumption), README setup steps after S0-05 and S0-07.
- Share the kickoff PDFs, ADR 003 link and the board with the team and the GDG organizer.
- Draft Sprint 1 tasks (login, profile, listing, application) once S0-09 and S0-10 are decided.

### Blockers
- None right now.
