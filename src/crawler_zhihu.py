from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PwTimeoutError
from playwright.sync_api import sync_playwright

from .utils import random_wait, write_json


ANSWER_ITEM = "div.List-item"


def _parse_upvote(raw: str) -> int:
    raw = raw.strip().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*万", raw)
    if m:
        return int(float(m.group(1)) * 10000)
    m2 = re.search(r"(\d+)", raw)
    return int(m2.group(1)) if m2 else 0


def _crawl_search_fallback(page, max_answers: int) -> list[dict]:
    answers: list[dict] = []
    page.goto(f"https://www.zhihu.com/search?type=content&q={quote_plus('机器人 人工智能')}", wait_until="domcontentloaded")
    random_wait(1.0, 2.0)

    cards = page.locator(".List-item, .SearchResult-Card")
    for i in range(min(cards.count(), max_answers * 3)):
        card = cards.nth(i)
        txt = card.inner_text().strip()
        if len(txt) < 80:
            continue
        if "机器人" not in txt and "人工智能" not in txt and "AI" not in txt:
            continue

        href = ""
        links = card.locator("a[href*='/question/']")
        if links.count() > 0:
            href = links.first.get_attribute("href") or ""
            if href.startswith("/"):
                href = "https://www.zhihu.com" + href

        answers.append(
            {
                "answer_id": f"ans_{len(answers)+1}",
                "author": "",
                "upvotes": 0,
                "source_url": href,
                "text": txt,
            }
        )
        if len(answers) >= max_answers:
            break
    return answers


def crawl_topic(topic_url: str, out_path: str | Path, max_answers: int, browser_cfg: dict) -> list[dict]:
    out_path = Path(out_path)
    answers: list[dict] = []

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=browser_cfg.get("user_data_dir", "./.pw_profile"),
            headless=browser_cfg.get("headless", False),
            slow_mo=browser_cfg.get("slow_mo_ms", 80),
        )
        page = ctx.new_page()
        page.set_default_timeout(browser_cfg.get("timeout_ms", 20000))
        page.goto(topic_url, wait_until="domcontentloaded")

        random_wait(browser_cfg.get("random_wait_min", 0.8), browser_cfg.get("random_wait_max", 2.0))

        for label in ["热门", "最热", "Hot"]:
            loc = page.get_by_role("button", name=label)
            if loc.count() > 0:
                loc.first.click()
                break

        seen = set()
        idle_rounds = 0

        while len(answers) < max_answers and idle_rounds < 6:
            items = page.locator(ANSWER_ITEM)
            count = items.count()
            before = len(answers)

            for i in range(count):
                if len(answers) >= max_answers:
                    break
                item = items.nth(i)
                text = item.inner_text().strip()
                if len(text) < 40:
                    continue

                links = item.locator("a[href*='/question/']")
                href = ""
                if links.count() > 0:
                    href = links.first.get_attribute("href") or ""
                if href and href.startswith("/"):
                    href = "https://www.zhihu.com" + href
                if href in seen:
                    continue
                seen.add(href)

                author = ""
                author_loc = item.locator(".AuthorInfo-name")
                if author_loc.count() > 0:
                    author = author_loc.first.inner_text().strip()

                upvote_text = "0"
                upvote_loc = item.locator("button:has-text('赞同')")
                if upvote_loc.count() > 0:
                    upvote_text = upvote_loc.first.inner_text().strip()

                answers.append({"answer_id": f"ans_{len(answers)+1}", "author": author, "upvotes": _parse_upvote(upvote_text), "source_url": href, "text": text})

            page.mouse.wheel(0, 3000)
            random_wait(browser_cfg.get("random_wait_min", 0.8), browser_cfg.get("random_wait_max", 2.0))
            idle_rounds = idle_rounds + 1 if len(answers) == before else 0

        if not answers:
            answers = _crawl_search_fallback(page, max_answers)

        answers.sort(key=lambda x: x.get("upvotes", 0), reverse=True)
        answers = answers[:max_answers]
        write_json(out_path, {"topic_url": topic_url, "answers": answers})

        try:
            page.close()
        except PwTimeoutError:
            pass
        ctx.close()

    return answers


def open_browser_for_login(topic_url: str, browser_cfg: dict):
    """打开浏览器让用户手动登录知乎，并保存登录态供后续使用"""
    user_data_dir = browser_cfg.get("user_data_dir", "./.pw_profile")
    headless = browser_cfg.get("headless", False)

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page()
        page.goto(topic_url, wait_until="networkidle")
        print(f"已打开浏览器：{topic_url}")
        print("请在浏览器中完成知乎登录，然后关闭浏览器窗口即可。")
        # 等待用户手动关闭浏览器
        browser.wait_for_event("close")
