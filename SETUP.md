# Setting up on a new computer

How to continue the spiral project on another Mac. The repo carries the code,
docs, results and Claude's working notes (CLAUDE.md, notes/context.md); a few
things live outside it, listed at the end.

## 1. Tools

* Apple's command line tools (git, Python 3):
  `xcode-select --install`
* Homebrew (https://brew.sh), then the GitHub CLI and sign in:
  `brew install gh` and `gh auth login`
* Optional, a newer Python: `brew install python@3.12` (use `python3.12`
  below). The system Python 3.9 works too.
* Claude Code (or the Claude desktop app).

## 2. The repo and its Python environment

```bash
mkdir -p ~/Desktop/cc && cd ~/Desktop/cc && gh repo clone adamfinkelstein/spiral
cd ~/Desktop/cc/spiral && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## 3. Check it works

* Rebuild card.html from the cached results (about a minute); `git status`
  should then show nothing, or only redrawn images:
  `.venv/bin/python build_card.py && git status --short`
* View the pages: `.venv/bin/python -m http.server 8765`, then open
  http://localhost:8765/procedure.html (or the live site,
  https://adamfinkelstein.github.io/spiral/).

## 4. Start Claude

* Start a new session in `~/Desktop/cc` (or `~/Desktop/cc/spiral`), e.g.
  "Read spiral/CLAUDE.md, especially the Handoff section, and
  procedure.html, then let's continue."
* Conversations don't travel: they stay on the computer they ran on. The
  project's state is in CLAUDE.md's Handoff section and notes/context.md.
* Claude's memory doesn't travel either, so the preferences it held are
  copied into spiral/CLAUDE.md ("Working with Adam"). Two more were for the
  slide projects, not spiral; add them to those repos' CLAUDE.md, or tell
  Claude again:
  - Slides: terse phrases, not sentences; speaker notes are short cues that
    never repeat the slide (COS 126 / COS 426 Slidev decks).
  - Poll answers in slide source or a public repo are fine; only assignment
    solutions and precept answer keys must stay private.

## 5. Outside the repo (copy by hand if wanted)

* `~/Desktop/cc/tomaz-results/` (28 MB, not in git): Tomaz's results on the
  real cards, a read-only reference the docs cite.
* `~/Desktop/cc/CLAUDE.md`: the note for the whole `cc` folder (not in git).
  Its text as of Nov 2026, to recreate it:

````markdown
# ~/Desktop/cc

Adam's home for all local Claude work: start Claude sessions here (e.g.
`claude --remote-control` in this folder). It holds many unrelated projects,
each in its own subfolder (course materials, exams, small apps, research
experiments, …). Each project is its own world: read its own CLAUDE.md /
README before working in it, and don't touch other projects' files unless
asked. New projects get a new subfolder here.

Some projects are git repositories and some are not (as of Nov 2026):

- git: cos126-ml-slides, cos126fall2026exams, cos426-slides-test,
  mccosh50-seating, nn-playground, spiral
- not git: backups, cos126-ml-precepts, exam-timer, grade-midterm,
  iclicker-qs-for-jen, old-midterm-solutions, res-colleges, tomaz-results

Check with `git -C <folder> status` rather than trusting this list. In a
folder without git there is no history to fall back on, so be careful with
edits and never delete without asking. This top folder itself is not a git
repo.

Several Claude sessions may be open on different subfolders at once, so keep
to one active session per git repo (two sessions in the same repo can clash
on edits and leave git lock files).

## Current work: spiral + tomaz-results (Adam Finkelstein, Nov 2026)

Goal: recover audio from scanned "sonorine" recording cards, which carry a
spiral groove (hill-and-dale: the sound is cut into the groove's depth, not
sideways like vinyl).

- `tomaz-results/` — someone else's results on the real cards (read-only
  reference): aligned scans → photometric-stereo normals → Poisson depth →
  hillshade, a groove mask, FFT spacing (~29 px), a RANSAC spiral fit. Start
  at its `index.html` (presentation with images 01–27). Measurements we took
  from it (spacing, grain, drift, annulus) are listed in
  `spiral/CLAUDE.md` and `spiral/procedure.html` Part 3.
- `spiral/` — our experiments (git repo, GitHub adamfinkelstein/spiral,
  deployed to GitHub Pages: https://adamfinkelstein.github.io/spiral/).
  Static browser pages: spacing.html (ring spacing via FFT), center.html
  (center/phase from chunks), card.html (simulated card, whole pipeline).
  `spiral/CLAUDE.md` has full notes and a "Handoff" section with the current
  state and next steps.

## How we work

- Adam reviews; commit locally when asked, and push when asked (in a
  remote-control session `git push` / `gh` work as Adam; in a Cowork session
  they don't — there Adam pushes himself).
- Keep docs current: spiral/procedure.html (method, step by step), CLAUDE.md,
  README.
- Prefer RANSAC-style robust methods; drop features that don't help; report
  results honestly with numbers.
````

* Not needed: `spiral/.venv/` (rebuilt in step 2) and `spiral/Claude outputs/`
  (old, gitignored leftovers from the Cowork sessions).
