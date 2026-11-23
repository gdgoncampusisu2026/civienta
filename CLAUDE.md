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
- S0-04 done (#5 closed): 14 Sprint 0 issues (#2 to #15, label `sprint-0`, `owner:<name>` labels) all assigned; everyone is in the org and in `civienta-team` with Write. Board is visible to org members only. Do not run the issue script again (it would duplicate the issues).
- S0-02 done (#3 closed): `civienta-gdg` (Spark, Firestore `(default)` in Frankfurt, production mode, web app registered), everyone added with their roles, team confirmed access.
- Rule from Serhan (2026-11-23): commit messages and PR titles in Turkish. `AGENTS.md` updated in PR #20 (merged).
- Team guide PDFs (5 pages each, kept outside the repo, to be sent by Serhan): `~/Desktop/GDG/GDG_Istinye_GitHub_Rehberi_TR.pdf` for the team and `~/Desktop/GDG/GDG_Istinye_GitHub_Guide_EN.pdf` for Layan. They explain issues, board, branches and PRs step by step with real GitHub screenshots (Serhan's own for the Turkish one; the English one uses new dark-mode captures for the example issue #6 and PR #19 so nothing in it mentions Turkish). Both have LLM prompt boxes for the branch, work, commit and PR steps. The English guide does not say what language commit messages and PR titles use.
- AGENTS.md says commit messages and PR titles are in Turkish for everyone, but Layan works in English: PR #22 adds "English is fine for team members who do not speak Turkish" (own PR, waiting for Serhan's merge).
- Guide PDF fixes (2026-11-23): the screenshots were blurry because WebKit embedded images at display size (72 ppi). Pages are now rendered at 3x and scaled down to A4, so images keep their full resolution (about 185 to 216 ppi). The LLM prompts and code blocks use highlighted placeholders (issue number, short name, commit type) instead of fixed branch names, so copy-pasting does not give every branch the same name.
- Comments asking Layan (#6, English) and Onuralp (#8, Turkish) to add their README setup steps were posted on 2026-11-23. S0-01 (#2) closes when both PRs are merged.

### In Progress
- S0-01 (#2): AGENTS.md check done. Claude reads it through `CLAUDE.md`, Gemini through `GEMINI.md` (PR #19), Antigravity tested by Serhan on 2026-11-23 and answered from the rules without opening files (its Customizations panel has no Rules tab). Codex reads `AGENTS.md` natively (not tested). Only open criterion: README local setup steps, now part of #6 (Layan) and #8 (Onuralp). Close #2 when both are merged.
- `civienta-dev` (second Spark project for previews and tests) created by Serhan; team access and web config for Layan still to do.
- Issues #6 to #15 rewritten in the two-layer format (what to do, out of scope, acceptance criteria, review). Layan's issues (#6, #7) in English, all others in Turkish with English technical terms. Issue template updated in PR #21 (merged). #11 was rewritten in full with the S0-10 decisions. Issue bodies were edited on 2026-11-23 without notifying the team.

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
- PRs #18 (data model), #19 (`GEMINI.md`) and #20 (AGENTS.md: Turkish commit messages and PR titles) merged on 2026-11-23.
- Issue format (agreed with Serhan): "what to do" in natural language, usable as an AI prompt, then "out of scope", acceptance criteria as checkboxes, and "review" for Serhan. The owner follows the steps, Serhan checks the criteria. Layan's issues in English, the rest in Turkish.
- Branch names follow AGENTS.md: `feat/<issue>-short-name` or `fix/<issue>-short-name`.
- Sprint 0 order (answer to Serhan, 2026-11-23): issues are not sequential, everyone starts now. Only dependencies: #7 (Vercel) after #6 (web setup) is merged, #9 (rules) after #8 (emulator), #8 seed prefers `shared/skills.json` from #12 (temporary slugs are fine), README steps from #6 and #8 close #2. Issue numbers are S0 numbers plus one (S0-05 is #6). The note "start after #8 is merged" was added to #9 on 2026-11-23. Serhan wants everything finished today and the notes PR opened last.
- Give the team access to `civienta-dev` (suggested: Editor for Onuralp, Melike, Buse and Layan, Viewer for Mustafa and Batuhan, Owner only Serhan), register a web app there and send its web config to Layan (S0-06 previews). Write ADR 004 (quota plan) only if wanted.
- Share the kickoff PDFs, ADR 003 link and the board with the team and the GDG organizer.
- Draft Sprint 1 tasks (login, profile, listing, application) once S0-09 and S0-10 are decided.

### Blockers
- None right now.
