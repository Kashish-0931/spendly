# Spendly — Expense Tracker (Project Overview)

> Exported 2026-08-29

## Summary

**"Spendly," a personal expense-tracker web app — currently a starter scaffold for a coding course, not a finished app.**

The instructor provides a polished UI shell + Flask skeleton; the learner incrementally builds auth, a profile page, and expense CRUD backed by SQLite, with filtering by category/date range and monthly/category summaries.

## What's here

| Layer | Tech | State |
|---|---|---|
| Backend | Flask 3.1 (`app.py`, port 5001) | Only 3 real routes: `/`, `/register`, `/login` (render templates). Everything else is a stub returning `"coming in Step N"` |
| Database | SQLite (`database/db.py`) | **Empty** — just a comment block telling students to write `get_db()`, `init_db()`, `seed_db()` |
| Frontend | Jinja templates + hand-written CSS | Landing, login, register pages are fully designed and styled (INR-themed "Spendly" branding). `main.js` is empty |
| Tests | pytest + pytest-flask in requirements | No test files yet |

## The tell

`app.py` has a section header `# Placeholder routes — students will implement these`, and stubs reference numbered steps:

- Step 1 – Database setup
- Step 3 – Logout / sessions
- Step 4 – Profile
- Step 7/8/9 – Add / edit / delete expenses

## Repo notes

- Single commit: `95e5e5f Initial commit: expense tracker starter`
- Branch: `main` (with `origin/main`)
- The actual repo is nested: `Desktop/expense-tracker/expense-tracker/`

## Tracked files

```
.gitignore
app.py
database/__init__.py
database/db.py
requirements.txt
static/css/style.css
static/js/main.js
templates/base.html
templates/landing.html
templates/login.html
templates/register.html
```

## requirements.txt

```
flask==3.1.3
werkzeug==3.1.6
pytest==8.3.5
pytest-flask==1.3.0
```
