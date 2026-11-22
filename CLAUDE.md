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

### In Progress
- S0-01: first PR (`feat/s0-01-working-notes`) with these notes. README local setup steps fill in as S0-05 and S0-07 land. AGENTS.md check in Claude, Codex and Gemini still to do.
- S0-02: Firebase project (free Spark plan) to be created by Serhan. Team invites come later (needs everyone's Google account).
- S0-03: data model v1 to be sent to Onuralp and Melike for review.

### Decisions
- Ruleset bypass for the Repository admin role is fine (org owners also get it, they will not open PRs).
- Repo is public, so rulesets and Vercel previews work on free plans. Announced to the team and the GDG organizer through ADR 003 (and the next PDF).

### Next Steps
- Create the Sprint 0 issues with `scripts/create-sprint-0-issues.sh` and set up the GitHub Projects board.
- Share the kickoff PDFs, ADR 003 link and the board with the team and the GDG organizer.

### Blockers
- None right now.
