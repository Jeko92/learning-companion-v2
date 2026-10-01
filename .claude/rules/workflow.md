# Development workflow

All feature work in this project follows a fixed pipeline. Each phase is a skill, each phase produces an artifact in `work/<ticket-id>/`, and hooks enforce the gates. The current phase lives in `.claude/state/workflow.json` and is injected into every prompt.

Tickets live on the GitHub project board (repo and board are configured in `.claude/hooks/config.sh`). `work/backlog.md` is a local, git-ignored mirror of the board, kept in sync by `python3 .claude/scripts/board.py sync`. `factory-manager` picks the next ticket from the board and drives the phases below; it advances exactly one step per call, so it can run in a `/loop`.

| Phase          | Skill            | Artifact                         | Board status | Exit condition                       |
|----------------|------------------|----------------------------------|--------------|--------------------------------------|
| `idle`         | —                | —                                | Todo         | factory-manager picks a ticket (only when `main` has the last one) |
| `refined`      | `refine-ticket`  | `work/<id>/ticket.md`, branch    | In Progress  | User approves acceptance criteria    |
| `planned`      | `plan-ticket`    | `work/<id>/plan.md`              | In Progress  | User approves the plan               |
| `implementing` | `tdd-implement`  | green commits, ticked plan       | In Progress  | All plan steps done, suite green     |
| `reviewing`    | `final-review`   | `work/<id>/review.md`            | In Progress  | Verdict PASS                         |
| `done`         | `factory-manager`| pushed branch, PR into `develop` | Done         | PR squash-merged, issue closed, release started |
| `releasing`    | `release`        | PR `develop` -> `main` merged    | Done         | Release PR merged into `main`, back to `idle` |

Rules that always apply:

- Never skip a phase and never set the phase yourself outside of the skill that owns the transition. Phases are changed only via `bash .claude/hooks/set-state.sh`, exactly where a skill says so.
- Source code is write-protected outside the `implementing` phase (enforced by a hook). If a write is blocked, do not work around it — you are in the wrong phase.
- Each phase works from the previous phase's artifact, not from the conversation. If `plan.md` is missing context, fix `plan.md`, don't improvise. The issue on the board is the input for `refine-ticket`.
- Every ticket is released to `main` before the next one starts: after `done`, `factory-manager` runs `release`, and no ticket is selected while `develop` has commits `main` lacks (a hook also blocks new ticket branches then). A blocked release (`release_status: blocked`) returns to `idle` and only lets a `type:fix` ticket start until that fix's release succeeds (or a human retries `/release`). See `.claude/rules/git.md`.
- Review findings are not fixed during review. They become new steps in `plan.md` and go back through `tdd-implement`.
- Board status changes go through `board.py status`, never by hand-editing `work/backlog.md`. New ideas may be added to `work/backlog.md` as plain `- [ ] <description>` lines; the next sync turns them into issues.
- If a ticket adds or changes commands, dependencies, apps or architecture, updating `CLAUDE.md` (and `README.md` where it applies) is part of that ticket's plan.
- If the user asks for a quick change outside the workflow (typo, config tweak, docs), say so explicitly and ask whether to bypass the workflow for it; markdown and config files are not write-protected.
