from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PwTimeoutError
from playwright.sync_api import sync_playwright

from .utils import random_wait, write_json


ANSWER_ITEM = "div.List-item, div.ContentItem.AnswerItem, div.SearchResult-Card"
QUESTION_ANSWER_ITEM = "div.List-item div.ContentItem.AnswerItem, div.List-item"


def _build_launch_kwargs(browser_cfg: dict) -> dict:
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    extra_args = browser_cfg.get("args", [])
    if isinstance(extra_args, list):
        args.extend(extra_args)

    kwargs = {
        "user_data_dir": browser_cfg.get("user_data_dir", "./.pw_profile"),
        "headless": browser_cfg.get("headless", False),
        "slow_mo": browser_cfg.get("slow_mo_ms", 80),
        "args": args,
        "locale": browser_cfg.get("locale", "zh-CN"),
    }

    # 优先用本机 Chrome，通常比 Playwright 内置 Chromium 更不容易触发风控
    channel = browser_cfg.get("channel", "chrome")
    if channel:
        kwargs["channel"] = channel

    if browser_cfg.get("executable_path"):
        kwargs["executable_path"] = browser_cfg.get("executable_path")

    if browser_cfg.get("user_agent"):
        kwargs["user_agent"] = browser_cfg.get("user_agent")

    return kwargs


def _is_zhihu_blocked(page) -> bool:
    txt = (page.content() or "")[:50000]
    return ("40362" in txt) or ("您当前请求存在异常" in txt) or ("验证中心" in txt)


def _raise_if_zhihu_blocked(page):
    if _is_zhihu_blocked(page):
        raise RuntimeError(
            "知乎风控拦截（40362）。建议：1) 用 --login 在同一 profile 完成人机验证；"
            "2) 保持同一网络/IP；3) 使用本机 Chrome 渠道运行（已默认开启）。"
        )


def _wait_user_solve_challenge(page, wait_seconds: int = 180) -> bool:
    print(f"[风控] 检测到知乎验证页（40362），请在浏览器中完成验证，最多等待 {wait_seconds}s ...")
    waited = 0
    while waited < wait_seconds:
        if not _is_zhihu_blocked(page):
            print("[风控] 验证已通过，继续抓取。")
            return True
        time.sleep(1)
        waited += 1
        if waited % 10 == 0:
            print(f"[风控] 仍在等待人工验证... {waited}s/{wait_seconds}s")
    return False


def _parse_upvote(raw: str) -> int:
    raw = raw.strip().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*万", raw)
    if m:
        return int(float(m.group(1)) * 10000)
    m2 = re.search(r"(\d+)", raw)
    return int(m2.group(1)) if m2 else 0


def _normalize_question_href(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = "https://www.zhihu.com" + href
    if href.startswith("https://www.zhihu.com//"):
        href = href.replace("https://www.zhihu.com//", "https://")
    return href


def _extract_answer_from_item(item, idx: int) -> dict | None:
    text = item.inner_text().strip()
    if len(text) < 40:
        return None

    href = ""
    links = item.locator("a[href*='/question/']")
    if links.count() > 0:
        href = _normalize_question_href(links.first.get_attribute("href") or "")

    author = ""
    author_loc = item.locator(".AuthorInfo-name")
    if author_loc.count() > 0:
        author = author_loc.first.inner_text().strip()

    upvote_text = "0"
    upvote_loc = item.locator("button:has-text('赞同')")
    if upvote_loc.count() > 0:
        upvote_text = upvote_loc.first.inner_text().strip()

    return {
        "answer_id": f"ans_{idx}",
        "author": author,
        "upvotes": _parse_upvote(upvote_text),
        "source_url": href,
        "text": text,
    }


def _crawl_search_fallback(page, max_answers: int, query: str = "机器人 人工智能") -> list[dict]:
    answers: list[dict] = []
    page.goto(f"https://www.zhihu.com/search?type=content&q={quote_plus(query)}", wait_until="domcontentloaded")
    random_wait(1.0, 2.0)

    cards = page.locator(".List-item, .SearchResult-Card")
    for i in range(min(cards.count(), max_answers * 4)):
        card = cards.nth(i)
        row = _extract_answer_from_item(card, len(answers) + 1)
        if not row:
            continue
        txt = row["text"]
        if len(txt) < 80:
            continue
        if "机器人" not in txt and "人工智能" not in txt and "AI" not in txt:
            continue

        answers.append(row)
        if len(answers) >= max_answers:
            break
    return answers


def _crawl_question_answers(page, question_url: str, max_answers: int, browser_cfg: dict) -> list[dict]:
    page.goto(question_url, wait_until="domcontentloaded")
    if _is_zhihu_blocked(page):
        wait_ok = _wait_user_solve_challenge(page, int(browser_cfg.get("challenge_wait_sec", 240)))
        if not wait_ok:
            _raise_if_zhihu_blocked(page)
    random_wait(browser_cfg.get("random_wait_min", 0.8), browser_cfg.get("random_wait_max", 2.0))

    # 尝试展开“查看全部回答”
    for label in ["查看全部", "查看全部回答", "全部回答", "更多回答"]:
        btn = page.get_by_role("button", name=label)
        if btn.count() > 0:
            try:
                btn.first.click()
                random_wait(0.5, 1.2)
                break
            except Exception:
                pass

    answers: list[dict] = []
    seen = set()
    idle_rounds = 0

    while len(answers) < max_answers and idle_rounds < 8:
        items = page.locator(QUESTION_ANSWER_ITEM)
        count = items.count()
        before = len(answers)

        for i in range(count):
            if len(answers) >= max_answers:
                break
            item = items.nth(i)
            row = _extract_answer_from_item(item, len(answers) + 1)
            if not row:
                continue

            text = row.get("text", "")
            if "赞同" not in text and "发布于" not in text and len(text) < 120:
                continue

            sig = text[:80]
            if sig in seen:
                continue
            seen.add(sig)

            row["source_url"] = question_url
            answers.append(row)

        page.mouse.wheel(0, 2800)
        random_wait(browser_cfg.get("random_wait_min", 0.8), browser_cfg.get("random_wait_max", 2.0))
        idle_rounds = idle_rounds + 1 if len(answers) == before else 0

    return answers[:max_answers]


def crawl_topic(topic_url: str, out_path: str | Path, max_answers: int, browser_cfg: dict) -> list[dict]:
    out_path = Path(out_path)
    answers: list[dict] = []

    # 若传入 answer URL，统一转成 question URL，降低触发风控概率
    m = re.search(r"(https://www\.zhihu\.com/question/\d+)", topic_url)
    if m:
        normalized_question_url = m.group(1)
        if normalized_question_url != topic_url:
            print(f"[crawl] 已将 answer 链接归一化为问题链接: {normalized_question_url}")
        topic_url = normalized_question_url

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(**_build_launch_kwargs(browser_cfg))
        page = ctx.new_page()
        page.set_default_timeout(browser_cfg.get("timeout_ms", 20000))

        is_question_url = "/question/" in topic_url

        if is_question_url:
            print("[crawl] 检测到问题链接，按“问题下回答”模式抓取")
            answers = _crawl_question_answers(page, topic_url, max_answers, browser_cfg)
        else:
            page.goto(topic_url, wait_until="domcontentloaded")
            if _is_zhihu_blocked(page):
                wait_ok = _wait_user_solve_challenge(page, int(browser_cfg.get("challenge_wait_sec", 240)))
                if not wait_ok:
                    _raise_if_zhihu_blocked(page)
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
                    row = _extract_answer_from_item(item, len(answers) + 1)
                    if not row:
                        continue

                    href = row.get("source_url", "")
                    if href in seen:
                        continue
                    seen.add(href)
                    answers.append(row)

                page.mouse.wheel(0, 3000)
                random_wait(browser_cfg.get("random_wait_min", 0.8), browser_cfg.get("random_wait_max", 2.0))
                idle_rounds = idle_rounds + 1 if len(answers) == before else 0

            if not answers:
                query = "机器人 人工智能"
                title_loc = page.locator("h1")
                if title_loc.count() > 0:
                    title = title_loc.first.inner_text().strip()
                    if title:
                        query = title
                answers = _crawl_search_fallback(page, max_answers, query=query)

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
        login_cfg = dict(browser_cfg)
        login_cfg["user_data_dir"] = user_data_dir
        login_cfg["headless"] = headless
        browser = pw.chromium.launch_persistent_context(**_build_launch_kwargs(login_cfg))
        page = browser.new_page()
        page.goto(topic_url, wait_until="domcontentloaded", timeout=120000)
        try:
            _raise_if_zhihu_blocked(page)
        except RuntimeError:
            print("[WARN] 当前打开即命中风控页，请先在页面完成验证再继续。")

        print("\n=== 知乎登录步骤 ===")
        print(f"1) 已打开页面：{topic_url}")
        print("2) 在浏览器里完成知乎登录（看到右上角头像/已登录状态）")
        print("3) 登录后可直接关闭浏览器；或不关闭，程序检测到登录态也会自动结束")
        print("4) 终端出现“已保存登录态”后，再执行 --force-crawl")
        print("===================\n")

        wait_seconds = int(browser_cfg.get("login_wait_timeout_sec", 300))
        waited = 0
        logged_in_streak = 0

        while waited < wait_seconds:
            # 条件A：用户手动关闭了登录页
            if page.is_closed():
                print("[OK] 检测到登录窗口已关闭，结束登录流程。")
                break

            # 条件B：检测到知乎登录cookie（z_c0）连续出现，视为登录成功
            try:
                cookies = browser.cookies(["https://www.zhihu.com"])
                has_auth_cookie = any(c.get("name") == "z_c0" and c.get("value") for c in cookies)
            except Exception:
                has_auth_cookie = False

            if has_auth_cookie:
                logged_in_streak += 1
                if logged_in_streak >= 3:
                    print("[OK] 已检测到知乎登录态（z_c0 cookie），自动结束登录流程。")
                    break
            else:
                logged_in_streak = 0

            waited += 1
            if waited % 10 == 0:
                print(f"[等待中] {waited}s / {wait_seconds}s（登录后可关闭浏览器）")
            time.sleep(1)
        else:
            print("[WARN] 登录等待超时，自动结束。若仍未登录成功，请重试 --login。")

        browser.close()
