"""
Playwright stealth browser base for bot scraping.
Patches browser fingerprints to mimic Nigerian mobile Chrome users (Tecno, Infinix, itel devices).
"""

import asyncio
import json
import logging
import random
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from app.collectors.proxy_pool import ProxyEntry, ProxyPool, SessionEntry, proxy_pool

log = logging.getLogger(__name__)

# ── Nigerian mobile browser fingerprints ─────────────────────────────────────
# Tecno, Infinix, itel, Samsung mid-range (dominant Nigerian market share)
NIGERIAN_MOBILE_USER_AGENTS = [
    (
        "Mozilla/5.0 (Linux; Android 13; Tecno Camon 20) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Linux; Android 12; Infinix Hot 20 Play) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Linux; Android 13; TECNO Spark 10 Pro) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Linux; Android 12; itel A70) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Linux; Android 11; Samsung SM-A125F) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Linux; Android 13; Xiaomi Redmi 12C) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Linux; Android 14; TECNO Camon 30) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Mobile Safari/537.36"
    ),
]

# Screen resolutions common on Nigerian mobile devices
MOBILE_VIEWPORTS = [
    {"width": 360, "height": 800},
    {"width": 375, "height": 812},
    {"width": 390, "height": 844},
    {"width": 412, "height": 915},
    {"width": 393, "height": 851},
    {"width": 360, "height": 780},
]

# JavaScript injected before every page to patch automation fingerprints
STEALTH_INIT_SCRIPT = """
// 1. Remove webdriver flag
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. Realistic plugin count
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

// 3. Nigerian locale languages
Object.defineProperty(navigator, 'languages', {
  get: () => ['en-NG', 'en-US', 'en'],
});

// 4. ARM platform (Android)
Object.defineProperty(navigator, 'platform', { get: () => 'Linux armv8l' });

// 5. Realistic hardware (mid-range Android)
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 4 });

// 6. Inject chrome runtime object to pass bot detection checks
window.chrome = {
  runtime: {},
  loadTimes: function() {},
  csi: function() {},
  app: {},
};

// 7. Spoof WebGL vendor/renderer (Mali GPU — common in Tecno/Infinix)
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
  if (parameter === 37445) return 'ARM';
  if (parameter === 37446) return 'Mali-G57 MC2';
  return getParameter.apply(this, arguments);
};

// 8. Prevent automation detection via permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
  parameters.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : originalQuery(parameters);
"""


async def _random_delay(min_ms: int = 500, max_ms: int = 2500) -> None:
    """Human-like pause between actions."""
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


async def _ghost_move(page: Page, target_x: float, target_y: float, steps: int = 12) -> None:
    """Simulate ghost cursor with Bezier-like curved movement and micro-jitter."""
    for i in range(1, steps + 1):
        progress = i / steps
        # Ease-in-out curve
        eased = progress * progress * (3 - 2 * progress)
        ix = eased * target_x + random.uniform(-4, 4)
        iy = eased * target_y + random.uniform(-3, 3)
        await page.mouse.move(ix, iy)
        await asyncio.sleep(random.uniform(0.008, 0.04))


async def _human_scroll(page: Page, times: int = 3) -> None:
    """Scroll the page in a natural reading pattern with occasional small retractions."""
    for _ in range(times):
        distance = random.randint(250, 750)
        await page.mouse.wheel(0, distance)
        await _random_delay(400, 1400)
        # ~25% chance of small scroll-back (simulates re-reading)
        if random.random() < 0.25:
            await page.mouse.wheel(0, -random.randint(40, 160))
            await _random_delay(200, 700)


class BotScraper:
    """
    Async context manager wrapping a Playwright browser with full stealth configuration.
    Mimics Nigerian mobile Chrome users with proxy rotation and session injection.

    Usage:
        async with BotScraper(platform="tiktok") as bot:
            page = await bot.new_page()
            success = await bot.navigate(page, "https://www.tiktok.com/@username")
            html = await page.content()
    """

    def __init__(
        self,
        platform: str,
        use_proxy: bool = True,
        headless: bool = True,
        pool: Optional[ProxyPool] = None,
    ) -> None:
        self.platform = platform
        self.use_proxy = use_proxy
        self.headless = headless
        self.pool = pool or proxy_pool

        self.user_agent: str = random.choice(NIGERIAN_MOBILE_USER_AGENTS)
        self.viewport: dict = random.choice(MOBILE_VIEWPORTS)
        self.device_scale_factor: float = random.choice([2.0, 2.5, 3.0])

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._proxy_entry: Optional[ProxyEntry] = None
        self._session_entry: Optional[SessionEntry] = None

    async def __aenter__(self) -> "BotScraper":
        self._playwright = await async_playwright().start()

        launch_kwargs: dict = {
            "headless": self.headless,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-zygote",
                "--disable-extensions",
                "--ignore-certificate-errors",
            ],
        }

        if self.use_proxy:
            self._proxy_entry = self.pool.get_proxy(proxy_type="mobile")
            if self._proxy_entry:
                launch_kwargs["proxy"] = {"server": self._proxy_entry.url}
                log.debug(
                    "Bot using proxy %s (%s)", self._proxy_entry.id, self._proxy_entry.carrier
                )
            else:
                log.warning("No proxy available — proceeding without proxy rotation")

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self, inject_session: bool = True) -> Page:
        """
        Create a new stealth page in a fresh browser context.
        Injects session cookies if available and applies the stealth init script.
        """
        context_kwargs: dict = {
            "user_agent": self.user_agent,
            "viewport": self.viewport,
            "locale": "en-NG",
            "timezone_id": "Africa/Lagos",
            "is_mobile": True,
            "has_touch": True,
            "device_scale_factor": self.device_scale_factor,
            "extra_http_headers": {
                "Accept-Language": "en-NG,en-US;q=0.9,en;q=0.8",
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-platform": '"Android"',
            },
        }

        if inject_session:
            self._session_entry = self.pool.get_session(self.platform)

        context: BrowserContext = await self._browser.new_context(**context_kwargs)

        if self._session_entry:
            try:
                cookies: list[dict] = json.loads(self._session_entry.cookies)
                await context.add_cookies(cookies)
                log.debug(
                    "Injected %d cookies from session %s",
                    len(cookies),
                    self._session_entry.id,
                )
            except Exception as exc:
                log.warning("Session cookie injection failed: %s", exc)
                if self._session_entry:
                    self.pool.invalidate_session(self._session_entry.id)
                    self._session_entry = None

        await context.add_init_script(STEALTH_INIT_SCRIPT)
        page = await context.new_page()
        return page

    async def navigate(
        self,
        page: Page,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 35_000,
    ) -> bool:
        """Navigate to URL with retry logic. Returns True on success."""
        for attempt in range(3):
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                await _random_delay(800, 2200)
                return True
            except Exception as exc:
                log.warning("Navigation attempt %d failed for %s: %s", attempt + 1, url, exc)
                if self._proxy_entry:
                    self.pool.mark_proxy_failed(self._proxy_entry.id)
                if attempt < 2:
                    await _random_delay(3000, 7000)
        return False

    async def human_click(self, page: Page, selector: str) -> bool:
        """Click an element using ghost cursor movement to avoid bot detection."""
        try:
            element = page.locator(selector).first
            bbox = await element.bounding_box()
            if not bbox:
                return False
            cx = bbox["x"] + bbox["width"] / 2 + random.uniform(-5, 5)
            cy = bbox["y"] + bbox["height"] / 2 + random.uniform(-3, 3)
            await _ghost_move(page, cx, cy)
            await _random_delay(80, 350)
            await page.mouse.click(cx, cy)
            await _random_delay(400, 1200)
            return True
        except Exception as exc:
            log.debug("human_click failed on '%s': %s", selector, exc)
            return False

    async def scroll_to_load(self, page: Page, times: int = 4) -> None:
        """Scroll down to trigger lazy-loaded content (TikTok / LinkedIn infinite scroll)."""
        await _human_scroll(page, times=times)

    async def wait_for_selector_safe(
        self, page: Page, selector: str, timeout: int = 10_000
    ) -> bool:
        """Returns True if selector appears before timeout, False otherwise."""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def save_session(self, page: Page, account_age_days: int = 0) -> Optional[str]:
        """Capture current page cookies and save them to the session pool. Returns session ID."""
        try:
            cookies = await page.context.cookies()
            entry = self.pool.save_page_session(
                platform=self.platform,
                cookies=cookies,
                user_agent=self.user_agent,
                proxy_id=self._proxy_entry.id if self._proxy_entry else None,
                account_age_days=account_age_days,
            )
            log.info("Session saved: %s (%s)", entry.id, self.platform)
            return entry.id
        except Exception as exc:
            log.warning("Failed to save session: %s", exc)
            return None

    def mark_proxy_failed(self) -> None:
        """Signal that the current proxy failed — called by collectors on HTTP errors."""
        if self._proxy_entry:
            self.pool.mark_proxy_failed(self._proxy_entry.id)

    def invalidate_session(self) -> None:
        """Signal that the current session is no longer valid."""
        if self._session_entry:
            self.pool.invalidate_session(self._session_entry.id)
            self._session_entry = None
