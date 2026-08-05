"""Polite HTTP fetching: robots.txt respect, UA rotation, random delay, retry.

Doc 02 §1 Shared Configuration + §5 Legal compliance. One session per vendor
run (cookies persist, headers stable). All fetches funnel through
`fetch_html` / `fetch_bytes` so delay/retry/robots rules apply everywhere.
"""
import logging
import random
import time
import urllib.robotparser

import requests

from .. import config

log = logging.getLogger("scraper.http")


class PoliteSession:
    """requests.Session wrapper with robots check, delay and retry."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._rp: urllib.robotparser.RobotFileParser | None = None
        self._rp_loaded = False
        self.session = requests.Session()
        self.session.headers["X-Purpose"] = "Product catalogue aggregation"
        self.last_request_at = 0.0

    # -- robots.txt -----------------------------------------------------
    def _robots(self):
        if not self._rp_loaded:
            self._rp_loaded = True
            rp = urllib.robotparser.RobotFileParser()
            try:
                # Fetch robots.txt through OUR session (real UA). robotparser's
                # own urllib fetch gets 403'd by Cloudflare/etc -> empty entries.
                resp = self._get(f"{self.base_url}/robots.txt")
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                    self._rp = rp
                else:
                    log.warning("robots.txt %s -> %d", self.base_url, resp.status_code)
            except Exception as e:  # robots fetch failure -> be permissive
                log.warning("robots.txt fetch failed for %s: %s", self.base_url, e)
        return self._rp

    def allowed(self, url: str) -> bool:
        rp = self._robots()
        if rp is None or not rp.can_fetch("*", url):
            return False
        return True

    # -- politeness -----------------------------------------------------
    def _throttle(self, image: bool = False):
        elapsed = time.monotonic() - self.last_request_at
        if image:
            want = random.uniform(config.IMAGE_MIN_DELAY_S, config.IMAGE_MAX_DELAY_S)
        else:
            want = random.uniform(config.MIN_DELAY_S, config.MAX_DELAY_S)
        if elapsed < want:
            time.sleep(want - elapsed)

    def _get(self, url: str, image: bool = False, **kw):
        self._throttle(image=image)
        kw.setdefault("timeout", config.REQUEST_TIMEOUT_S)
        kw.setdefault("headers", {})
        kw["headers"].setdefault(
            "User-Agent", random.choice(config.USER_AGENTS)
        )
        kw["headers"].setdefault(
            "Accept",
            "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        )
        resp = self.session.get(url, **kw)
        self.last_request_at = time.monotonic()
        return resp

    def fetch_html(self, url: str) -> str | None:
        """GET a page honouring robots.txt + retry. Returns HTML text or None."""
        if not self.allowed(url):
            log.info("robots.txt disallows: %s", url)
            return None
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                resp = self._get(url)
                if resp.status_code == 200:
                    # sites that omit the charset default to ISO-8859-1 in
                    # requests, mojibaking UTF-8 text (idealbathrooms.im does).
                    # Modern pages are UTF-8 — default to it unless the server
                    # explicitly declared a different charset.
                    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                        resp.encoding = "utf-8"
                    return resp.text
                if resp.status_code in (403, 429, 503):
                    log.warning(
                        "[%s] %s -> %d (attempt %d/%d)",
                        self.base_url, url, resp.status_code, attempt, config.MAX_RETRIES,
                    )
                else:
                    log.warning("[%s] %s -> %d", self.base_url, url, resp.status_code)
                    return None
            except requests.RequestException as e:
                log.warning("[%s] request error %s: %s", self.base_url, url, e)
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF_S * attempt)
        return None

    def fetch_bytes(self, url: str) -> bytes | None:
        """GET binary content (images) with retry. robots.txt not consulted for
        CDN image hosts — they are asset servers, not crawl targets. Uses the
        shorter image delay (config.IMAGE_*_DELAY_S)."""
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                resp = self._get(url, image=True)
                if resp.status_code == 200:
                    return resp.content
                log.warning("[img] %s -> %d", url, resp.status_code)
                return None
            except requests.RequestException as e:
                log.warning("[img] request error %s: %s", url, e)
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF_S * attempt)
        return None

    def close(self):
        self.session.close()
