# profile-availability

Watches a list of profile pages and records when each one goes online or offline. A profile counts as offline while its page shows a text you configure, and as online otherwise. Every change is appended to a per-profile log, a screenshot is saved when a profile comes online, and an email can be sent through [Resend](https://resend.com).

Nothing about the watched site is hardcoded: the URLs, the offline text, the selectors and the optional disclaimer page all live in the config file.

## How it works

Every 5 minutes the script starts Chrome through [SeleniumBase](https://github.com/seleniumbase/SeleniumBase)'s CDP mode and visits each URL in turn:

1. Load the page.
2. If `[site.disclaimer]` is configured and its form shows up within 5 seconds, click the control whose label matches `button_label`, then wait up to 15 seconds for the form to go away.
3. If `ready_selector` is configured, wait up to 10 seconds for it to appear.
4. Read the page text (`document.body.innerText`, plus the text of every `text_selector` element) and normalize it: NFC, non-breaking spaces to spaces, whitespace collapsed, lowercase. If `offline_text` appears within 5 seconds the profile is offline, otherwise it is online.

The profile name is the last path segment of its URL, so `https://example.com/profiles/alice` is `alice`.

## Requirements

- Python 3.11 or newer
- Google Chrome or Chromium
- macOS or Linux

## Install

```bash
git clone https://github.com/nyg/profile-availability.git ~/.local/opt/profile-availability
mkdir -p ~/.config/profile-availability
cp ~/.local/opt/profile-availability/config.example.toml ~/.config/profile-availability/config.toml
chmod 600 ~/.config/profile-availability/config.toml
```

Edit `~/.config/profile-availability/config.toml`, then start the checker:

```bash
~/.local/opt/profile-availability/run.sh
```

`run.sh` creates a `.venv` next to itself on first use, installs `requirements.txt` into it, and starts the checker detached with `nohup`, appending its output to `run.log`. It does not stop a running instance, so stop the old one first when restarting:

```bash
pkill -f profile-availability.py
```

## Configuration

The config file is `$XDG_CONFIG_HOME/profile-availability/config.toml` (`~/.config/profile-availability/config.toml` by default). See [config.example.toml](config.example.toml).

| Key | Required | Purpose |
| --- | --- | --- |
| `urls` | yes | Profile pages to watch |
| `site.offline_text` | yes | Text whose presence marks a profile as offline, matched case-insensitively after normalization |
| `site.ready_selector` | no | CSS selector to wait for before reading the page, so the text is not read before the profile has rendered |
| `site.text_selector` | no | CSS selector whose elements' text is read in addition to `document.body.innerText` |
| `site.disclaimer.form_selector` | with `[site.disclaimer]` | A single CSS selector for an interstitial form shown before the profile, such as an age gate |
| `site.disclaimer.button_label` | with `[site.disclaimer]` | Label of the control that dismisses it, matched by prefix, then by substring, then by a page-wide text search |
| `resend.api_key` | for email | Resend API key |
| `resend.from` | for email | Sender, as `address` or `Name <address>` |
| `resend.to` | for email | One recipient, or a list |

Leave out `[site.disclaimer]` when the site has no interstitial. Leave out `[resend]` to run without email; the checker prints one warning at startup and keeps going.

The file holds the Resend API key, so keep it private (`chmod 600`) and outside the repository.

## Email

When a profile's status differs from the last recorded one, the checker sends an email with the subject `<profile> is now online` or `<profile> is now offline`. The first check of a profile has nothing to compare with and sends nothing. A failed send is logged as `MAIL ERROR` and does not interrupt the checks.

`resend.from` must be an address on a domain you verified at [resend.com/domains](https://resend.com/domains). Without one, use `onboarding@resend.dev`: it only delivers to the email address of your Resend account.

## Files

| Path | Content |
| --- | --- |
| `$XDG_DATA_HOME/profile-availability/<profile>.txt` | One line per status change: `YYYY-MM-DD HH:MM:SS online` or `offline` |
| `$XDG_DATA_HOME/profile-availability/<profile>.errors.txt` | One line per failed check |
| `$XDG_DATA_HOME/profile-availability/run.log` | Output of the checker when started with `run.sh` |
| `$XDG_STATE_HOME/profile-availability/screenshots/` | Full-page PNG each time a profile comes online |
| `$XDG_STATE_HOME/profile-availability/debug/` | Page source saved on each failed check |

`XDG_DATA_HOME` defaults to `~/.local/share` and `XDG_STATE_HOME` to `~/.local/state`.

## License

[MIT](LICENSE)
