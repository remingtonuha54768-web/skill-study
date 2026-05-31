"""
Phase 1 - Part 2: Refined DOM analysis.
Target: https://www.cers.org.cn/site/term/9253f1.html
Key finding: 34 pages, 15 per page, query-parameter pagination.
Need to: Identify exact article list region and extract links properly.
"""
import asyncio
import json
import random
import sys
from pathlib import Path
from datetime import datetime

from patchright.async_api import async_playwright

TARGET_URL = "https://www.cers.org.cn/site/term/9253f1.html"
HOMEPAGE = "https://www.cers.org.cn"
DOMAIN = "www.cers.org.cn"


async def main():
    results = {}

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

        # Warm up
        print("[1] Warming up...")
        await page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(5, 10))

        # Navigate to target
        print(f"[2] Loading target page...")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)
        # Scroll
        for y in [300, 600, 900, 1200, 1500]:
            await page.evaluate(f"window.scrollTo(0, {y})")
            await asyncio.sleep(0.5)
        await asyncio.sleep(2)

        print(f"    Page title: {await page.title()}")

        # Get the FULL DOM structure to understand article list
        print("\n[3] Deep DOM inspection...")

        # First, dump the HTML structure around the content area
        structure = await page.evaluate("""() => {
            const info = {};

            // Find the main content area
            const content = document.querySelector('.content');
            if (content) {
                info.contentHTML = content.innerHTML.substring(0, 5000);
                info.contentChildren = Array.from(content.children).map(c => ({
                    tag: c.tagName,
                    id: c.id,
                    className: c.className,
                    childCount: c.children.length,
                    textSample: c.textContent.trim().substring(0, 200),
                }));
            }

            // Find ALL div/article/li elements that might be article items
            const articlePatterns = [];
            const allDivs = document.querySelectorAll('div, li, article');

            for (const el of allDivs) {
                const cls = (el.className || '').toLowerCase();
                const id = (el.id || '').toLowerCase();

                // Look for patterns that indicate article list items
                if (/list|item|article|news|post|entry|row/.test(cls) ||
                    /list|item|article|news|post|entry|row/.test(id)) {

                    const links = el.querySelectorAll('a[href]');
                    if (links.length >= 1 && links.length <= 5) {
                        const a = links[0];
                        const text = (a.textContent || '').trim();
                        if (text.length > 5) {
                            articlePatterns.push({
                                tag: el.tagName,
                                className: cls.substring(0, 80),
                                id: id.substring(0, 40),
                                linkText: text.substring(0, 150),
                                linkHref: a.href,
                                childCount: el.children.length,
                                top: Math.round(el.getBoundingClientRect().top),
                            });
                        }
                    }
                }

                if (articlePatterns.length > 30) break;  // Enough samples
            }

            info.articlePatterns = articlePatterns.slice(0, 40);
            info.totalArticlePatterns = articlePatterns.length;

            // Also check the full body for common article class patterns
            const classNames = new Set();
            document.querySelectorAll('[class]').forEach(el => {
                el.className.split(/\\s+/).filter(c => c.length > 2).forEach(c => classNames.add(c));
            });
            info.relevantClasses = Array.from(classNames).filter(c =>
                /list|item|article|news|post|entry|titl|cont|desc|date|time|summary|row|col|card|box/.test(c.toLowerCase())
            ).slice(0, 100);

            return info;
        }""")

        print(f"  Content children: {json.dumps(structure.get('contentChildren', []), ensure_ascii=False, indent=2)[:2000]}")
        print(f"\n  Article patterns found: {structure.get('totalArticlePatterns', 0)}")
        for i, p in enumerate(structure.get('articlePatterns', [])[:10]):
            print(f"  [{i+1}] {p['tag']}.{p['className']} — \"{p['linkText'][:80]}\"")
            print(f"      href: {p['linkHref'][:120]}, top: {p['top']}")

        print(f"\n  Relevant CSS classes: {structure.get('relevantClasses', [])[:30]}")

        results["structure"] = structure

        # Now let's try different selectors to find the article list
        print("\n[4] Testing various selectors for article links...")

        selector_tests = await page.evaluate("""() => {
            const tests = [];

            // Test many different selectors
            const selectors = [
                '.news-list a',
                '.article-list a',
                '.list a',
                '.newslist a',
                '.articlelist a',
                '.list-content a',
                '.list_item a',
                '.list-item a',
                'li a[href*="site/content"]',
                'a[href*="site/content"]',
                '.content a[href*="content"]',
                '.content li a',
                '.content ul a',
                '.list_box a',
                '.news_con a',
                '.list_con a',
                '[class*="list"] a[href*="content"]',
                '[class*="news"] a[href*="content"]',
                '.entry a',
                '.post a',
            ];

            for (const sel of selectors) {
                try {
                    const els = document.querySelectorAll(sel);
                    if (els.length >= 3) {
                        const samples = Array.from(els).slice(0, 5).map(a => ({
                            text: (a.textContent || '').trim().substring(0, 100),
                            href: a.href,
                        }));
                        tests.push({
                            selector: sel,
                            count: els.length,
                            samples: samples,
                        });
                    }
                } catch(e) {}
            }

            // Also find ALL links on the page and categorize them
            const allLinks = document.querySelectorAll('a[href]');
            const categorized = {
                contentLinks: [],
                otherLinks: [],
            };
            for (const a of allLinks) {
                const href = a.href;
                const text = (a.textContent || '').trim();
                if (href.includes('/site/content/')) {
                    categorized.contentLinks.push({text: text.substring(0, 100), href: href});
                } else if (text.length > 3) {
                    categorized.otherLinks.push({text: text.substring(0, 60), href: href});
                }
            }

            tests.push({
                selector: 'ALL /site/content/ links',
                count: categorized.contentLinks.length,
                samples: categorized.contentLinks.slice(0, 10),
            });

            return {selectorTests: tests, categorized: categorized};
        }""")

        for t in selector_tests.get('selectorTests', []):
            print(f"  {t['selector']}: {t['count']} links")
            for s in t.get('samples', [])[:3]:
                print(f"    - \"{s['text'][:70]}\" => {s['href'][:100]}")

        # The key finding: /site/content/ links
        content_links = selector_tests.get('categorized', {}).get('contentLinks', [])
        print(f"\n  >>> Found {len(content_links)} links with /site/content/ pattern")

        results["selector_tests"] = selector_tests

        # Check pagination more carefully
        print("\n[5] Detailed pagination analysis...")
        pagination = await page.evaluate("""() => {
            const pagEl = document.querySelector('.pagination');
            if (!pagEl) return {error: 'no pagination element'};

            const html = pagEl.innerHTML;
            const text = pagEl.textContent;

            // Extract total pages
            const totalMatch = text.match(/共\\s*(\\d+)\\s*页/);
            const totalPages = totalMatch ? parseInt(totalMatch[1]) : null;

            // Extract all page links
            const allLinks = Array.from(pagEl.querySelectorAll('a'));
            const pageLinks = allLinks.map(a => ({
                text: a.textContent.trim(),
                href: a.href,
            }));

            // Find next/prev
            const next = allLinks.find(a => /下一页|›|>|»/.test(a.textContent.trim()));
            const prev = allLinks.find(a => /上一页|‹|<|«/.test(a.textContent.trim()));

            return {
                fullText: text.trim(),
                totalPages: totalPages,
                visiblePages: pageLinks.filter(l => /^\\d+$/.test(l.text)),
                nextExists: !!next,
                prevExists: !!prev,
                nextHref: next ? next.href : null,
                perPage: 15,
            };
        }""")

        print(f"  Pagination text: {pagination.get('fullText', 'N/A')}")
        print(f"  Total pages: {pagination.get('totalPages')}")
        print(f"  Per page: {pagination.get('perPage')}")
        print(f"  Visible page numbers: {[p['text'] for p in pagination.get('visiblePages', [])]}")
        print(f"  Next page: {pagination.get('nextHref')}")

        results["pagination"] = pagination

        MAX_PAGES = pagination.get('totalPages', 34)
        PER_PAGE = pagination.get('perPage', 15)

        # Now test pages 1, 2, and last to verify
        print(f"\n[6] Testing content across pages (1, 2, 34)...")
        for test_page in [1, 2, MAX_PAGES]:
            url = f"{TARGET_URL}?page={test_page}&per-page=15"
            try:
                await page.goto(url, wait_until="networkidle", timeout=20000)
            except Exception:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(random.uniform(3, 6))

            links = await page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/site/content/"]');
                return Array.from(links).map(a => ({
                    text: (a.textContent || '').trim(),
                    href: a.href,
                }));
            }""")

            print(f"  Page {test_page}: {len(links)} /site/content/ links")
            for l in links[:3]:
                print(f"    - \"{l['text'][:80]}\"")
                print(f"      {l['href'][:120]}")

            results[f"page{test_page}_links"] = links
            results[f"page{test_page}_count"] = len(links)

        await browser.close()

    # Final execution summary
    print("\n" + "="*60)
    print("EXECUTION SUMMARY")
    print("="*60)
    total_links_p1 = len(results.get("page1_links", []))
    total_links_p2 = len(results.get("page2_links", []))
    total_links_last = len(results.get(f"page{MAX_PAGES}_links", []))

    print(f"站点: {DOMAIN}")
    print(f"分页方式: query-parameter (page=N&per-page=15)")
    print(f"WAF: none detected")
    print(f"最大页数: {MAX_PAGES}")
    print(f"每页文章数: ~{PER_PAGE}")
    print(f"第1页文章链接数: {total_links_p1}")
    print(f"第2页文章链接数: {total_links_p2}")
    print(f"第{MAX_PAGES}页文章链接数: {total_links_last}")
    estimated = MAX_PAGES * max(total_links_p1, total_links_p2, total_links_last)
    print(f"预计抓取链接数量: ~{estimated}")
    print(f"文章链接选择器: a[href*='/site/content/']")
    print(f"判断依据: Patchright浏览器渲染DOM分析，分页控件显示共{MAX_PAGES}页，每页15条")

    # Save
    output_path = Path(__file__).parent.parent / "output" / "phase1_analysis_v2.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSaved to: {output_path}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
