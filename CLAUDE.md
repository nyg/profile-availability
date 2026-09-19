# CLAUDE.md

Guidance for AI coding agents working in this repo. Keep it accurate: update it when the behavior or conventions below change.

## What this is

A single-file Python checker, `profile-availability.py`, that loops forever: every `CHECK_INTERVAL` seconds it opens each configured profile URL in Chrome through SeleniumBase's CDP driver, decides `online` or `offline` from the page text, records changes, and emails them through the Resend REST API. [README.md](README.md) documents the user-facing behavior, config keys and files.

## Layout

```
profile-availability.py  the checker
config.example.toml      template for ~/.config/profile-availability/config.toml
run.sh                   creates .venv next to itself, installs requirements, starts the checker with nohup
requirements.txt         pinned seleniumbase
```

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
XDG_CONFIG_HOME=/some/scratch/config XDG_DATA_HOME=/some/scratch/data XDG_STATE_HOME=/some/scratch/state .venv/bin/python profile-availability.py
```

Point the three XDG variables at a scratch directory to avoid touching the user's real config, status history and screenshots. There is no test suite. Config loading and mail sending can be exercised without Chrome by stubbing the `seleniumbase` modules in `sys.modules` before importing the script, and by pointing `RESEND_ENDPOINT` at a local HTTP server.

## Conventions

**No site-specific strings in the repo.** The URLs, the offline text, every CSS selector that depends on the watched site (including `location_selector`), and the disclaimer button label come from `config.toml`. Keep the code generic, and keep `config.example.toml` on placeholder values (`example.com`, generic selectors). The only built-in selectors are the generic disclaimer controls in `DISCLAIMER_CONTROLS`.

**Standard library only, apart from SeleniumBase.** The config is TOML read with `tomllib` (so Python 3.11+), and Resend is called with `urllib.request`. Don't add `requests`, `httpx` or `python-dotenv` for this.

**Paths follow XDG** and never point inside the checkout: config in `$XDG_CONFIG_HOME/profile-availability`, status and error logs plus `run.log` in `$XDG_DATA_HOME/profile-availability`, screenshots and debug HTML in `$XDG_STATE_HOME/profile-availability`.

**The status log is the state.** `<profile>.txt` only gets a line when the status changes, and its last line is the previous status. A line is `date time status`, followed by the location on `online` lines when one was found; the location may contain spaces, so parse the status as the third whitespace-separated field. Read the previous status before `write_status`, since that call makes the new one the last line. A missing file means an unknown previous status: no email is sent, but a screenshot is still taken when the first status is `online`.

**Failures are per profile.** Any exception during a check writes the page source to the debug directory and a line to `<profile>.errors.txt`, then the loop moves on. A mail failure is printed and swallowed, so it never turns into a check failure.

**Resend requires a `User-Agent` header** and rejects requests without one with a 403, so keep the header in `send_mail`.

## Don't commit

`config.toml` (it holds the Resend API key and the watched URLs), `.venv/`, status logs, screenshots or debug HTML. Commit directly on `master`.
