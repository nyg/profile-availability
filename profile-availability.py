import asyncio
import html
import json
import os
import re
import sys
import tomllib
import unicodedata
import urllib.error
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlparse

from seleniumbase import cdp_driver
from seleniumbase.undetected.cdp_driver.browser import Browser
from seleniumbase.undetected.cdp_driver.tab import Tab

APP_NAME = "profile-availability"
CHECK_INTERVAL = 300
OFFLINE_TIMEOUT = 5
READY_TIMEOUT = 10
DISCLAIMER_CONTROLS = ("button", 'input[type="submit"]', 'input[type="button"]', "a")
DISCLAIMER_TIMEOUT = 5
REDIRECT_TIMEOUT = 15
STATUS_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / APP_NAME
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / APP_NAME
SCREENSHOT_DIR = STATE_DIR / "screenshots"
DEBUG_DIR = STATE_DIR / "debug"
CONFIG_FILE = CONFIG_DIR / "config.toml"
RESEND_ENDPOINT = "https://api.resend.com/emails"
MAIL_TIMEOUT = 30


@dataclass(frozen=True)
class Disclaimer:
    form_selector: str
    button_label: str

    @property
    def controls_selector(self) -> str:
        return ", ".join(f"{self.form_selector} {control}" for control in DISCLAIMER_CONTROLS)


@dataclass(frozen=True)
class Site:
    offline_text: str
    ready_selector: str | None
    text_selector: str | None
    disclaimer: Disclaimer | None


@dataclass(frozen=True)
class Mailer:
    api_key: str
    sender: str
    recipients: tuple[str, ...]


@dataclass(frozen=True)
class Config:
    urls: tuple[str, ...]
    site: Site
    mailer: Mailer | None


def exit_with(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


def load_config() -> Config:
    if not CONFIG_FILE.exists():
        exit_with(f"Config file not found: {CONFIG_FILE}")
    try:
        raw = tomllib.loads(CONFIG_FILE.read_text())
    except tomllib.TOMLDecodeError as e:
        exit_with(f"Invalid {CONFIG_FILE}: {e}")
    urls = tuple(url.strip() for url in raw.get("urls", []) if url.strip())
    if not urls:
        exit_with(f"No urls in {CONFIG_FILE}")
    return Config(urls, load_site(raw.get("site", {})), load_mailer(raw.get("resend", {})))


def load_site(site: dict) -> Site:
    offline_text = site.get("offline_text", "")
    if not offline_text:
        exit_with(f"Set offline_text under [site] in {CONFIG_FILE}")
    disclaimer = site.get("disclaimer")
    return Site(
        offline_text=offline_text,
        ready_selector=site.get("ready_selector") or None,
        text_selector=site.get("text_selector") or None,
        disclaimer=load_disclaimer(disclaimer) if disclaimer is not None else None,
    )


def load_disclaimer(disclaimer: dict) -> Disclaimer:
    form_selector = disclaimer.get("form_selector", "")
    button_label = disclaimer.get("button_label", "")
    if not (form_selector and button_label):
        exit_with(f"Set form_selector and button_label under [site.disclaimer] in {CONFIG_FILE}")
    return Disclaimer(form_selector, button_label)


def load_mailer(resend: dict) -> Mailer | None:
    api_key = resend.get("api_key", "")
    sender = resend.get("from", "")
    to = resend.get("to", [])
    recipients = tuple([to] if isinstance(to, str) else to)
    if not (api_key and sender and recipients):
        print(f"Email disabled: set api_key, from and to under [resend] in {CONFIG_FILE}", file=sys.stderr)
        return None
    return Mailer(api_key, sender, recipients)


def send_mail(mailer: Mailer, subject: str, body: str) -> None:
    payload = {"from": mailer.sender, "to": list(mailer.recipients), "subject": subject, "html": body}
    request = urllib.request.Request(
        RESEND_ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {mailer.api_key}",
            "Content-Type": "application/json",
            "User-Agent": APP_NAME,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=MAIL_TIMEOUT):
            pass
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend API error {e.code}: {e.read().decode(errors='replace')}") from e


async def notify_change(mailer: Mailer | None, profile: str, url: str, previous: str, status: str) -> None:
    if mailer is None:
        return
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"{profile} is now {status}"
    body = (
        f'<p><a href="{html.escape(url)}">{html.escape(profile)}</a> went from '
        f"<b>{previous}</b> to <b>{status}</b> at {date}.</p>"
    )
    try:
        await asyncio.to_thread(send_mail, mailer, subject, body)
    except Exception as e:
        print(f"{date} {profile} → MAIL ERROR: {e}", file=sys.stderr)


def profile_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.split("/")[-1]


def status_file(profile: str) -> Path:
    return STATUS_DIR / f"{profile}.txt"


def error_file(profile: str) -> Path:
    return STATUS_DIR / f"{profile}.errors.txt"


def get_last_status(profile: str) -> str | None:
    path = status_file(profile)
    if not path.exists():
        return None
    lines = path.read_text().strip().splitlines()
    if not lines:
        return None
    parts = lines[-1].rsplit(maxsplit=1)
    return parts[1] if len(parts) == 2 else None


def write_status(profile: str, status: str) -> None:
    if get_last_status(profile) == status:
        return
    path = status_file(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a") as f:
        f.write(f"{date} {status}\n")


def write_error(profile: str, error: Exception) -> None:
    path = error_file(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a") as f:
        f.write(f"{date} {type(error).__name__}: {error}\n")


async def save_screenshot(tab: Tab, profile: str) -> str:
    date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = SCREENSHOT_DIR / f"{profile}_{date}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return await tab.save_screenshot(path, format="png", full_page=True)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def control_label(control) -> str:
    text = (getattr(control, "text", None) or "").strip()
    if not text:
        text = (control.attrs.get("value") or "").strip()
    return text


async def wait_for_disclaimer(tab: Tab, disclaimer: Disclaimer, present: bool, timeout: float):
    waited = 0.0
    while waited < timeout:
        form = await tab.query_selector(disclaimer.form_selector)
        if bool(form) == present:
            return form
        await tab.sleep(0.5)
        waited += 0.5
    return await tab.query_selector(disclaimer.form_selector)


async def click_disclaimer_button(tab: Tab, disclaimer: Disclaimer) -> bool:
    controls = await tab.query_selector_all(disclaimer.controls_selector)
    labels = [control_label(control) for control in controls]
    wanted = disclaimer.button_label.lower()
    for match in (str.startswith, str.__contains__):
        for control, label in zip(controls, labels):
            if match(label.lower(), wanted):
                await control.click_async()
                return True
    with suppress(Exception):
        control = await tab.find(disclaimer.button_label, best_match=True, timeout=5)
        if control:
            await control.click_async()
            return True
    print(f"Disclaimer controls found: {labels}", file=sys.stderr)
    return False


async def dismiss_disclaimer(tab: Tab, disclaimer: Disclaimer) -> None:
    if not await wait_for_disclaimer(tab, disclaimer, True, DISCLAIMER_TIMEOUT):
        return
    if not await click_disclaimer_button(tab, disclaimer):
        raise RuntimeError(f"No {disclaimer.button_label!r} control found in the disclaimer form")
    if await wait_for_disclaimer(tab, disclaimer, False, REDIRECT_TIMEOUT):
        raise RuntimeError(f"Disclaimer still present after clicking {disclaimer.button_label!r}")


async def save_debug(tab: Tab, profile: str) -> None:
    with suppress(Exception):
        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = DEBUG_DIR / f"{profile}_{date}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(await tab.get_content())


async def page_text(tab: Tab, site: Site) -> str:
    parts = []
    with suppress(Exception):
        rendered = await tab.evaluate("document.body.innerText")
        if rendered:
            parts.append(rendered)
    if site.text_selector:
        with suppress(Exception):
            elements = await tab.query_selector_all(site.text_selector)
            parts.extend(getattr(el, "text", None) or "" for el in elements)
    return normalize(" ".join(parts))


async def check_status(tab: Tab, site: Site, url: str) -> str:
    await tab.get(url)
    if site.disclaimer:
        await dismiss_disclaimer(tab, site.disclaimer)
    if site.ready_selector:
        await tab.select(site.ready_selector, timeout=READY_TIMEOUT)
    target = normalize(site.offline_text)
    waited = 0.0
    while waited < OFFLINE_TIMEOUT:
        if target in await page_text(tab, site):
            return "offline"
        await tab.sleep(0.5)
        waited += 0.5
    return "online"


async def run_checks(config: Config) -> None:
    browser: Browser = await cdp_driver.start_async(ad_block=True)
    tab: Tab = await browser.get("about:blank")
    try:
        for url in config.urls:
            profile = profile_from_url(url)
            try:
                status = await check_status(tab, config.site, url)
                previous = get_last_status(profile)
                write_status(profile, status)
                if status == "online" and previous != "online":
                    await save_screenshot(tab, profile)
                print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {profile} → {status}")
                if previous is not None and previous != status:
                    await notify_change(config.mailer, profile, url, previous, status)
            except Exception as e:
                await save_debug(tab, profile)
                write_error(profile, e)
                print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {profile} → ERROR: {e}", file=sys.stderr)
            await tab.sleep(5)
    finally:
        browser.stop()


async def main() -> None:
    config = load_config()
    while True:
        await run_checks(config)
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
