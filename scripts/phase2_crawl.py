"""
Phase 2: Crawl all 34 pages of the article list.
Target: https://www.cers.org.cn/site/term/9253f1.html
Uses: a[href*="/site/content/"] selector, resumable progress, 15-60s random sleep
"""
import asyncio
import json
import random
import re
import sys
from pathlib import Path
from datetime import datetime

from patchright.async_api import async_playwright

TARGET_URL = "https://www.cers.org.cn/site/term/9253f1.html"
HOMEPAGE = "https://www.cers.org.cn"
DOMAIN = "www.cers.org.cn"
TOTAL_PAGES = 34
PER_PAGE = 15

OUTPUT_DIR = Path(__file__).parent.parent / "output"
PROGRESS_FILE = OUTPUT_DIR / "crawl_progress.json"
OUTPUT_FILE_TEMPLATE = "{domain}_{timestamp}.json"


def normalize_title(text):
    """Clean article title by removing date prefix and read-more suffix."""
    t = text.strip()
    # Remove date prefix like [03-28]
    t = re.sub(r'^\[\d{2}-\d{2}\]\s*', '', t)
    # Remove 阅读全文>> suffix
    t = re.sub(r'阅读全文\s*>>\s*$', '', t)
    t = re.sub(r'>>\s*$', '', t)
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def classify_link(url, target_domain=DOMAIN):
    """Classify a link per the output format rules."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or ''

    # isWechatLink
    is_wechat = host == 'mp.weixin.qq.com'

    # isOutLink: host outside target domain scope
    # Target domain is www.cers.org.cn, also accept subdomains of cers.org.cn
    is_out = not (host == target_domain or host.endswith('.cers.org.cn'))

    # isFileLink: check extension and download cues
    path_lower = parsed.path.lower()
    file_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.ppt', '.pptx', '.zip', '.rar', '.7z', '.txt', '.rtf']
    is_file = any(path_lower.endswith(ext) for ext in file_extensions)
    if not is_file:
        query_lower = (parsed.query or '').lower()
        is_file = any(cue in query_lower or cue in path_lower for cue in ['/download/', 'download=', 'attachment', 'file='])

    return {
        "isOutLink": is_out,
        "isFileLink": is_file,
        "isWechatLink": is_wechat,
    }


async def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "completed_pages": [],
        "failed_pages": [],
        "collected_links": [],  # {url, title}
        "current_page": 1,
        "timestamp": None,
    }


def save_progress(progress):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


async def warmup(page):
    """Perform warm-up browsing session."""
    await page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(5, 10))
    # Natural scroll
    await page.evaluate("window.scrollBy(0, 300)")
    await asyncio.sleep(random.uniform(1, 3))
    await page.evaluate("window.scrollBy(0, 600)")
    await asyncio.sleep(random.uniform(1, 3))
    await page.evaluate("window.scrollTo(0, 0)")
    print("  [Warmup] Homepage browsed")


async def scroll_naturally(page):
    """Simulate natural scrolling behavior."""
    scroll_y = random.randint(300, 600)
    await page.evaluate(f"window.scrollBy(0, {scroll_y})")
    await asyncio.sleep(random.uniform(1, 2))
    scroll_y = random.randint(400, 800)
    await page.evaluate(f"window.scrollBy(0, {scroll_y})")
    await asyncio.sleep(random.uniform(1, 2))


async def extract_links_from_page(page):
    """Extract article links using the /site/content/ selector."""
    links = await page.evaluate("""() => {
        const anchors = document.querySelectorAll('a[href*="/site/content/"]');
        return Array.from(anchors).map(a => ({
            url: a.href,
            title: (a.textContent || '').trim(),
        }));
    }""")
    return links


async def crawl_page(page, page_num, progress):
    """Crawl a single list page."""
    url = f"{TARGET_URL}?page={page_num}&per-page={PER_PAGE}"

    print(f"\n--- Page {page_num}/{TOTAL_PAGES} ---")
    print(f"  URL: {url}")

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"  Networkidle timeout, trying domcontentloaded...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # Wait for rendering
    await asyncio.sleep(random.uniform(2, 5))

    # Scroll naturally to trigger any lazy content
    await scroll_naturally(page)
    await asyncio.sleep(random.uniform(1, 3))

    # Extract links
    raw_links = await extract_links_from_page(page)
    print(f"  Extracted {len(raw_links)} raw links")

    # Process links
    new_links = []
    existing_urls = {l["url"] for l in progress["collected_links"]}

    for raw in raw_links:
        norm_url = raw["url"]
        # Normalize URL (remove fragment, etc.)
        if '#' in norm_url:
            norm_url = norm_url.split('#')[0]

        if norm_url not in existing_urls:
            clean_title = normalize_title(raw["title"])
            if clean_title:
                classification = classify_link(norm_url)
                entry = {
                    "url": norm_url,
                    "title": clean_title,
                    "isOutLink": classification["isOutLink"],
                    "isFileLink": classification["isFileLink"],
                    "isWechatLink": classification["isWechatLink"],
                }
                new_links.append(entry)
                existing_urls.add(norm_url)

    print(f"  New unique links added: {len(new_links)}")

    progress["collected_links"].extend(new_links)
    progress["completed_pages"].append(page_num)
    progress["current_page"] = page_num

    return len(new_links)


async def main():
    progress = await load_progress()

    # Set timestamp for output file
    if progress["timestamp"] is None:
        progress["timestamp"] = datetime.now().strftime("%Y%m%d_%H%M%S")

    completed = set(progress["completed_pages"])
    failed = set(progress["failed_pages"])

    pending_pages = [p for p in range(1, TOTAL_PAGES + 1) if p not in completed and p not in failed]
    # Also retry failed pages
    pending_pages = [p for p in range(1, TOTAL_PAGES + 1) if p not in completed]

    print(f"=== Phase 2: Crawl ===")
    print(f"Domain: {DOMAIN}")
    print(f"Total pages: {TOTAL_PAGES}")
    print(f"Already completed: {len(completed)}")
    print(f"Previously failed: {len(failed)}")
    print(f"Pending: {len(pending_pages)}")
    print(f"Collected links so far: {len(progress['collected_links'])}")
    print(f"Starting from page: {min(pending_pages) if pending_pages else 'N/A'}")

    if not pending_pages:
        print("All pages already completed!")
        return progress

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            viewport={"width": random.randint(1280, 1440), "height": random.randint(720, 900)},
            device_scale_factor=random.choice([1, 1.25, 1.5, 2]),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        # Warmup
        if not completed:
            print("\n[Warmup] Starting fresh session...")
            await warmup(page)

        total_added = 0

        for pg_num in pending_pages:
            try:
                added = await crawl_page(page, pg_num, progress)

                if added == 0 and pg_num < TOTAL_PAGES - 1:
                    # Might be a loading issue, but let's not retry just for 0 links
                    # Only last few pages might have fewer links
                    print(f"  Note: 0 new links on page {pg_num}")

                total_added += added

                # Vary interaction pattern
                interaction = random.choice(['scroll_then_next', 'direct_next', 'wait_extra'])
                if interaction == 'scroll_then_next':
                    await page.evaluate(f"window.scrollBy(0, {random.randint(200, 500)})")
                    await asyncio.sleep(random.uniform(2, 5))
                elif interaction == 'wait_extra':
                    await asyncio.sleep(random.uniform(3, 8))

                # Randomized long sleep (15-60 seconds)
                sleep_time = random.uniform(15, 60)
                print(f"  Sleeping {sleep_time:.0f}s... (collected: {len(progress['collected_links'])} total links)")

                # Save progress BEFORE sleep so we can resume if interrupted during sleep
                save_progress(progress)

                await asyncio.sleep(sleep_time)

            except Exception as e:
                print(f"  ERROR on page {pg_num}: {e}")
                progress["failed_pages"].append(pg_num)
                save_progress(progress)
                # Still sleep after error
                sleep_time = random.uniform(15, 30)
                print(f"  Error sleep {sleep_time:.0f}s...")
                await asyncio.sleep(sleep_time)

        # Final save
        save_progress(progress)

        # Write output file
        output_filename = OUTPUT_FILE_TEMPLATE.format(
            domain=DOMAIN,
            timestamp=progress["timestamp"]
        )
        output_path = OUTPUT_DIR / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(progress["collected_links"], f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"CRAWL COMPLETE")
        print(f"{'='*60}")
        print(f"Total links exported: {len(progress['collected_links'])}")
        print(f"Pages completed: {len(progress['completed_pages'])}/{TOTAL_PAGES}")
        print(f"Pages failed: {len(progress['failed_pages'])}")
        print(f"Output file: {output_path}")

        await browser.close()

    return progress


if __name__ == "__main__":
    asyncio.run(main())
