# Working on this repository

New here? Read [docs/onboarding.md](docs/onboarding.md) first: the objective, what is where,
the rules, the state of the work and the next steps.

## Git

- Commit and push straight to `main`. No pull request and no feature branch unless asked for one.
- Author and committer: `martinjensen37 <martin.jensen37@gmail.com>`. Before the first commit
  of a session run `git config user.name martinjensen37` and
  `git config user.email martin.jensen37@gmail.com`.
- No Claude attribution anywhere: no `Co-Authored-By: Claude`, no `Claude-Session:` line, no
  "Generated with Claude Code" in commits or pull requests.
- Many small commits, each one change that stands on its own (tests pass after each).
- Commit messages of 1 to 3 lines: an imperative subject line, at most two short lines more.
  No long bodies or bullet lists.

## Design log

- While building, add every design consideration to [docs/design-log.md](docs/design-log.md),
  newest first and dated: what was chosen, why, instead of what, and for which paper (CIRP, the
  CIRP CMS paper; Journal, the journal paper). Commit it with the change it explains.
- What belongs in the journal paper also goes into the journal notes, `papers/journal/journal-paper.md`
  in the local material folder (below).

## Material outside git

Presentations, figure sources (draw.io), the papers and their notes are kept in
`AASPIRE-material` beside the repos folder (`../../AASPIRE-material` from here), never in git:
`presentations/`, `figures/` (with the shape library), `papers/` (`cirp/`, `journal/`,
`orchestration/`, `literature/`, `references.bib`) and `misc/`. The papers are under a
publisher's copyright; nothing of them is committed.
