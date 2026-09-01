# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo layout

The project is flat: app code, `requirements.txt`, `.git`, and this `CLAUDE.md`
all live at the repo root `C:\Users\kunal\Desktop\expense-tracker\`. Run git
and the app from there. Remote: `github.com/Kashish-0931/spendly`.

## Project

"Spendly", a personal expense-tracker web app. This is a **course scaffold**, not a
finished app. The instructor provides a styled UI shell + Flask skeleton; the learner
builds features incrementally.

- Stack: Flask 3.1, SQLite, Jinja templates, hand-written CSS. No JS framework.
- Real routes today: `/`, `/register`, `/login`, `/terms`, `/privacy` (render templates).
- Routes returning `"coming in Step N"` are **intentionally unimplemented**. So is
  `database/db.py` (a comment block for `get_db()` / `init_db()` / `seed_db()`).
  Only implement these when explicitly asked, and only the step requested — do not
  build ahead or fill in other stubs unprompted.

## Commands

Run from the repo root:

- Dev server: `python app.py` — serves on **port 5001** (`debug=True`).
- Tests: `pytest` (pytest + pytest-flask are in requirements; no test files exist yet).
- Deps: `pip install -r requirements.txt`.
- The SQLite file `expense_tracker.db` is gitignored and created at runtime.

## Conventions

- Commit messages: lowercase `area: description` (e.g. `landing: add privacy policy page`).
  One narrowly-scoped commit per change. Don't `git push` unless asked.
- Templates extend `base.html`; use `{% block content %}` / `{% block scripts %}`.
  Use `url_for()` for static assets and routes.
- One stylesheet: `static/css/style.css`. Match its existing class-naming and section style.
- JavaScript: vanilla only, in `static/js/main.js` — no libraries or CDN dependencies.
- Branding is INR-themed ("Track every rupee"); keep currency examples in ₹.
