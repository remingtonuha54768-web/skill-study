"""
Phase 3: Validation - Verify that exported link count matches actual article-list count.
Re-checks pages using Patchright to count actual article links on each page.
"""
import asyncio
import json
import random
from pathlib import Path

from patchright.async_api import async_playwright

TARGET_URL = "https://www.cers.org.cn/site/term/9253f1.html"
HOMEPAGE = "https://www.cers.org.cn"
TOTAL_PAGES = 34
PER_PAGE = 15
OUTPUT_DIR = Path(__file__).parent.parent / "output"


async def validate():
    print("=== Phase 3: Validation ===")

    # Load exported links
    output_file = OUTPUT_DIR / "www.cers.org.cn_20260531_130357.json"
    with open(output_file, "r", encoding="utf-8") as f:
        exported_links = json.load(f)
    exported_count = len(exported_links)
    print(f"Exported links: {exported_count}")

    # Load progress to see completed pages
    progress_file = OUTPUT_DIR / "crawl_progress.json"
    with open(progress_file, "r", encoding="utf-8") as f:
        progress = json.load(f)
    completed_pages = progress["completed_pages"]
    failed_pages = progress["failed_pages"]
    print(f"Completed pages: {len(completed_pages)}/{TOTAL_PAGES}")
    print(f"Failed pages: {len(failed_pages)}")

    # Deduplication check
    urls = [l["url"] for l in exported_links]
    unique_urls = set(urls)
    if len(urls) != len(unique_urls):
        duplicates = len(urls) - len(unique_urls)
        print(f"WARNING: {duplicates} duplicate URLs in export!")

    # Now validate by checking a sample of rendered pages
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": random.randint(1280, 1440), "height": random.randint(720, 900)},
            device_scale_factor=random.choice([1, 1.25, 1.5, 2]),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # Warmup
        print("\n[Validation warmup]...")
        await page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(5, 10))

        # Check pages at intervals: first, a few middle, and last
        check_pages = [1, 5, 10, 17, 25, 34]

        page_counts = {}
        total_actual = 0

        for pg_num in check_pages:
            url = f"{TARGET_URL}?page={pg_num}&per-page=15"
            try:
                await page.goto(url, wait_until="networkidle", timeout=20000)
            except Exception:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            await asyncio.sleep(random.uniform(3, 6))

            # Count actual article links on this page
            count = await page.evaluate("""() => {
                return document.querySelectorAll('a[href*="/site/content/"]').length;
            }""")

            # Also extract the actual links for comparison
            links_on_page = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a[href*="/site/content/"]'))
                    .map(a => a.href.split('#')[0]);
            }""")

            page_counts[pg_num] = {
                "actual_count": count,
                "urls": links_on_page,
            }
            print(f"  Page {pg_num}: {count} actual article links in DOM")

            total_actual += count

            # Sleep between validation checks
            await asyncio.sleep(random.uniform(15, 30))

        await browser.close()

    # Calculate expected total
    # Pages 1-33 each have ~15, page 34 has fewer
    expected_min = (TOTAL_PAGES - 1) * 14 + 1  # conservative minimum
    expected_max = TOTAL_PAGES * 15  # maximum possible

    print(f"\n=== Validation Results ===")
    print(f"Exported unique links: {exported_count}")
    print(f"Sample page counts: {page_counts}")
    print(f"Expected range: {expected_min} - {expected_max}")

    # Key check: exported count vs estimated actual total
    # If all non-sample pages have ~15 links like the sampled ones
    avg_per_page = sum(v["actual_count"] for v in page_counts.values()) / len(page_counts)
    estimated_total = int(avg_per_page * TOTAL_PAGES)
    print(f"Estimated total based on sample: {estimated_total}")

    # Verify URL uniqueness
    all_sample_urls = set()
    for v in page_counts.values():
        all_sample_urls.update(v["urls"])
    print(f"Unique URLs across sample pages: {len(all_sample_urls)}")

    # Cross-check: do any exported URLs match across different pages?
    url_page_map = {}
    for pg_num in [1, 5, 10, 17, 25, 34]:
        for u in page_counts[pg_num]["urls"]:
            if u not in url_page_map:
                url_page_map[u] = set()
            url_page_map[u].add(pg_num)

    cross_page = {u: pages for u, pages in url_page_map.items() if len(pages) > 1}
    print(f"URLs appearing on multiple checked pages: {len(cross_page)}")

    # Final verdict
    print(f"\n=== VERDICT ===")
    if exported_count >= expected_min and exported_count <= expected_max:
        print(f"PASS: Exported count ({exported_count}) within expected range ({expected_min}-{expected_max})")
    else:
        print(f"FAIL: Exported count ({exported_count}) outside expected range ({expected_min}-{expected_max})")

    print(f"All target pages completed: Yes" if len(completed_pages) == TOTAL_PAGES else f"Unfinished pages: {TOTAL_PAGES - len(completed_pages)}")
    print(f"Failed pages: {len(failed_pages)}")

    return {
        "exported_count": exported_count,
        "completed_pages": len(completed_pages),
        "failed_pages": len(failed_pages),
        "sample_page_counts": {str(k): v["actual_count"] for k, v in page_counts.items()},
        "cross_page_duplicates": len(cross_page),
        "estimated_total": estimated_total,
    }


if __name__ == "__main__":
    result = asyncio.run(validate())
    print(f"\nFinal result: {json.dumps(result, ensure_ascii=False, indent=2)}")
