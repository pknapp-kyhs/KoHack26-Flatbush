# Repository Guidelines

## Project Structure & Module Organization

This repository contains a small Flask web application for the Kohelet 2026 coding competition.

- `app.py` is the primary Flask entry point and exposes the prayer, activity-stream, check-in, and chart routes.
- `fullapp.py` is an alternate, more self-contained entry point with chart rendering enabled.
- `stats.py` contains anxiety, focus, scrolling, and plotting logic shared by the application.
- `templates/index.html` is the Jinja page template; `static/script.js` contains browser interaction and activity tracking.
- `WireFrame.html` is a standalone UI wireframe. `README.md` documents the client/server architecture.

## Build, Test, and Development Commands

Create and activate the existing virtual environment (or a new one), then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the primary application locally with `python app.py` and open `http://127.0.0.1:5000`. Use `python fullapp.py` to exercise the alternate full application. There is no compiled build step. No automated test command is currently configured; perform a smoke test by loading the page, requesting a prayer, sending activity samples, and submitting a check-in.

## Coding Style & Naming Conventions

Use Python 3, four-space indentation, lowercase `snake_case` for functions and variables, and descriptive route names matching the existing API paths. Keep Flask handlers thin and place reusable analysis in `stats.py`. Preserve the existing HTML/CSS/JavaScript organization and use clear camelCase or existing naming patterns in frontend code. Before submitting, remove debug output and keep imports grouped at the top of each file. No formatter or linter is configured, so keep changes PEP 8-compatible and manually review them.

## Testing Guidelines

There is currently no test framework, test directory, or coverage threshold. For behavioral changes, add focused tests if introducing a framework, otherwise document manual verification steps in the pull request. Test API success and malformed-input paths, especially for `/get_prayer`, `/stream_sample`, and `/submit_checkin`.

## Commit & Pull Request Guidelines

Recent commits use short, imperative-style summaries such as `fixes`, `rename`, and `remove unused`. Keep commits focused and use a concise imperative subject describing the change. Local commits are allowed when useful, but do not push them or publish changes to a remote repository without explicit approval. Pull requests should explain the user-visible behavior, list manual checks or tests run, identify any new dependency or external API assumption, and include screenshots or a short recording for UI changes. Keep generated files, virtual environments, and secrets out of commits.

## Security & Configuration Tips

The app calls the external Sefaria API at runtime, so local development requires network access. Validate request payloads and handle upstream failures without exposing stack traces. Do not commit credentials, personal data, or local environment directories.
