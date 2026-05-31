"""
Phase 1: Analyze site structure using Patchright.
Target: https://www.cers.org.cn/site/term/9253f1.html
"""
import asyncio
import json
import random
import sys
from datetime import datetime
from pathlib import Path

from patchright.async_api import async_playwright

TARGET_URL = "https://www.cers.org.cn/site/term/9253f1.html"
HOMEPAGE = "https://www.cers.org.cn"
DOMAIN = "www.cers.org.cn"


async def random_viewport():
    return {
        "width": random.randint(1280, 1440),
        "height": random.randint(720, 900),
    }


async def main():
    results = {
        "target_url": TARGET_URL,
        "domain": DOMAIN,
        "phase": "analysis",
        "pages_analyzed": [],
        "findings": {},
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Create context with randomized fingerprint
        context = await browser.new_context(
            viewport=await random_viewport(),
            device_scale_factor=random.choice([1, 1.25, 1.5, 2]),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )

        page = await context.new_page()

        print("=== Phase 1: Site Analysis ===")
        print(f"Target: {TARGET_URL}")

        # Step 1: Warm up on homepage
        print("\n[1] Warming up on homepage...")
        try:
            await page.goto(HOMEPAGE, wait_until="domcontentloaded", timeout=30000)
            print(f"  Homepage loaded: {page.url}")
            await asyncio.sleep(random.uniform(5, 10))
            # Natural scroll
            await page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(random.uniform(1, 3))
            await page.evaluate("window.scrollBy(0, 600)")
            await asyncio.sleep(random.uniform(1, 3))
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(random.uniform(1, 2))
            homepage_title = await page.title()
            print(f"  Homepage title: {homepage_title}")
        except Exception as e:
            print(f"  Homepage warmup issue: {e}")
            print("  Continuing to target URL directly...")

        # Step 2: Navigate to target URL
        print(f"\n[2] Navigating to target list page...")
        try:
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
        except Exception:
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)

        await asyncio.sleep(random.uniform(5, 10))
        # Scroll to trigger lazy content
        await page.evaluate("window.scrollBy(0, 300)")
        await asyncio.sleep(random.uniform(1, 3))
        await page.evaluate("window.scrollBy(0, 600)")
        await asyncio.sleep(random.uniform(1, 3))
        await page.evaluate("window.scrollBy(0, 900)")
        await asyncio.sleep(random.uniform(2, 4))
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(2)

        page_title = await page.title()
        current_url = page.url
        print(f"  Page title: {page_title}")
        print(f"  Current URL: {current_url}")

        # Check response headers for WAF signs
        print("\n[3] Checking for CDN/WAF signs...")

        # Inspect the rendered DOM
        print("\n[4] Inspecting DOM structure...")

        # Get the full page HTML structure
        html_snippet = await page.evaluate("""() => {
            const main = document.querySelector('main, article, .main, .content, .container, #main, #content');
            if (main) {
                return {
                    tag: main.tagName,
                    id: main.id,
                    className: main.className,
                    childCount: main.children.length
                };
            }
            return {tag: 'body', id: '', className: '', childCount: document.body.children.length};
        }""")
        print(f"  Main container: {json.dumps(html_snippet, ensure_ascii=False)}")

        # Find list-like structures
        list_info = await page.evaluate("""() => {
            const results = [];

            // Check for common list patterns
            const listContainers = document.querySelectorAll('ul, ol, .list, .article-list, .news-list, .post-list, [class*="list"], [class*="article"], [class*="news"]');
            const seen = new Set();

            for (const el of listContainers) {
                if (seen.has(el)) continue;
                seen.add(el);

                const anchors = el.querySelectorAll('a[href]');
                if (anchors.length >= 3) {
                    // Get some sample links
                    const sampleLinks = [];
                    for (let i = 0; i < Math.min(10, anchors.length); i++) {
                        const a = anchors[i];
                        const rect = a.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            sampleLinks.push({
                                href: a.href,
                                text: a.textContent.trim().substring(0, 100),
                                className: a.className,
                            });
                        }
                    }

                    if (sampleLinks.length >= 2) {
                        const rect = el.getBoundingClientRect();
                        results.push({
                            tag: el.tagName,
                            id: el.id || '',
                            className: (el.className || '').substring(0, 100),
                            anchorCount: anchors.length,
                            visible: rect.width > 0 && rect.height > 0,
                            height: Math.round(rect.height),
                            top: Math.round(rect.top),
                            sampleLinks: sampleLinks.slice(0, 5),
                        });
                    }
                }
            }
            return results;
        }""")

        print(f"  Found {len(list_info)} list-like regions:")
        for i, region in enumerate(list_info):
            print(f"\n  Region {i+1}:")
            print(f"    Tag: {region['tag']}#{region['id']}.{region['className']}")
            print(f"    Anchors: {region['anchorCount']}, Visible: {region['visible']}, Height: {region['height']}px, Top: {region['top']}px")
            for j, link in enumerate(region['sampleLinks'][:5]):
                print(f"    [{j+1}] {link['text'][:80]}")
                print(f"        href: {link['href'][:120]}")

        results["list_regions"] = list_info

        # Step 5: Determine pagination
        print("\n[5] Analyzing pagination...")
        pagination_info = await page.evaluate("""() => {
            const info = {
                style: 'unknown',
                controls: [],
                maxPage: null,
                nextExists: false,
            };

            // Look for pagination elements
            const paginationSelectors = [
                '.pagination', '.pager', '.page-nav', '.pages',
                '#pagination', '#pager',
                '[class*="paginat"]', '[class*="page-n"]', '[class*="pager"]',
                '.fenye', '#fenye',
            ];

            for (const sel of paginationSelectors) {
                const el = document.querySelector(sel);
                if (el) {
                    const links = el.querySelectorAll('a[href]');
                    const spans = el.querySelectorAll('span');
                    const all = el.textContent.trim().substring(0, 300);

                    info.controls.push({
                        selector: sel,
                        text: all,
                        anchorCount: links.length,
                        sampleHrefs: Array.from(links).slice(0, 5).map(a => a.href),
                    });

                    // Check for "next" link
                    for (const a of links) {
                        const t = (a.textContent || '').trim();
                        if (/下一页|next|下页|»|›|>/.test(t)) {
                            info.nextExists = true;
                            info.nextHref = a.href;
                        }
                    }

                    // Look for max page number
                    const nums = [];
                    for (const a of links) {
                        const t = (a.textContent || '').trim();
                        const n = parseInt(t, 10);
                        if (!isNaN(n) && n > 0) {
                            nums.push(n);
                        }
                    }
                    for (const s of spans) {
                        const t = (s.textContent || '').trim();
                        const n = parseInt(t, 10);
                        if (!isNaN(n) && n > 0) {
                            nums.push(n);
                        }
                    }
                    if (nums.length > 0) {
                        info.maxPage = Math.max(...nums);
                    }
                }
            }

            // Also search for any "next page" or "下一页" text on the page
            const bodyText = document.body.textContent || '';
            const nextMatch = bodyText.match(/下一页|下页|next page/i);
            if (nextMatch) {
                info.hasNextText = true;
            }

            // Check URL structure for page parameter
            if (window.location.search.includes('page=') || window.location.search.includes('p=')) {
                info.style = 'query-parameter';
            } else if (window.location.pathname.includes('/page/')) {
                info.style = 'path-based';
            }

            return info;
        }""")

        print(f"  Pagination style: {pagination_info['style']}")
        print(f"  Max page from pagination: {pagination_info['maxPage']}")
        print(f"  Next page exists: {pagination_info['nextExists']}")
        if pagination_info.get('nextHref'):
            print(f"  Next page href: {pagination_info['nextHref']}")
        for ctrl in pagination_info.get('controls', []):
            print(f"  Control: {ctrl['selector']} - {ctrl['text'][:100]}")

        results["pagination"] = pagination_info

        # Step 6: Check for WAF response headers (we already fetched)
        # Check using page evaluate for cf-ray etc via meta tags
        waf_check = await page.evaluate("""() => {
            const meta = document.querySelectorAll('meta');
            const wafHints = [];
            for (const m of meta) {
                const name = (m.name || m.getAttribute('http-equiv') || '').toLowerCase();
                if (name.includes('cf') || name.includes('cloud') || name.includes('waf')) {
                    wafHints.push({name: m.name, content: m.content});
                }
            }
            return {
                metaHints: wafHints,
                hasCFScript: !!document.querySelector('script[src*="cloudflare"]'),
                hasTurnstile: !!document.querySelector('[src*="challenges.cloudflare"]'),
                bodyTextStart: (document.body.textContent || '').substring(0, 200),
            };
        }""")
        print(f"\n[6] WAF check: meta hints={waf_check['metaHints']}, CF script={waf_check['hasCFScript']}")

        results["waf_check"] = waf_check

        # Step 7: Count actual article links on this page
        # We need to find the best article-list region first
        print("\n[7] Counting article links on page 1...")

        # Try to get all article links from the best candidate region
        article_links = await page.evaluate("""() => {
            const results = [];

            // Strategy: find all 'a' tags that look like article links
            // Common patterns for article/list pages
            const allLinks = document.querySelectorAll('a[href]');

            for (const a of allLinks) {
                const href = a.href;
                const text = (a.textContent || '').trim();

                // Skip obvious non-article links
                if (!text || text.length < 2) continue;
                if (/首页|登录|注册|搜索|关于|联系|设为首页|收藏|RSS|English|中文|导航/.test(text)) continue;

                const rect = a.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;

                // Check if this anchor is in a likely content area (not nav/footer)
                let parent = a.parentElement;
                let inBadZone = false;
                let depth = 0;
                while (parent && depth < 10) {
                    const tag = parent.tagName.toLowerCase();
                    const cls = (parent.className || '').toLowerCase();
                    const id = (parent.id || '').toLowerCase();
                    if (tag === 'nav' || tag === 'footer' || tag === 'header' ||
                        cls.includes('nav') || cls.includes('footer') || cls.includes('header') ||
                        cls.includes('sidebar') || cls.includes('menu') ||
                        id.includes('nav') || id.includes('footer') || id.includes('header')) {
                        inBadZone = true;
                        break;
                    }
                    parent = parent.parentElement;
                    depth++;
                }

                if (!inBadZone) {
                    results.push({
                        href: href,
                        text: text.substring(0, 150),
                    });
                }
            }

            return results;
        }""")

        print(f"  Candidate article links on page 1: {len(article_links)}")
        for i, link in enumerate(article_links[:15]):
            print(f"  [{i+1}] {link['text'][:80]}")
            print(f"      {link['href'][:120]}")

        results["page1_candidate_links"] = len(article_links)
        results["page1_sample_links"] = article_links[:20]

        # Step 8: Try to navigate to page 2 if pagination exists
        print("\n[8] Testing pagination - navigating to page 2...")
        page2_url = None
        page2_links_count = 0

        if pagination_info.get('nextHref'):
            page2_url = pagination_info['nextHref']
            print(f"  Using next page href: {page2_url}")

        # Also try common pagination patterns
        if not page2_url:
            # Try query parameter
            test_urls = [
                TARGET_URL.replace('.html', '_2.html'),
                TARGET_URL.replace('.html', '?page=2'),
                TARGET_URL + '?page=2',
                TARGET_URL.replace('.html', '&page=2') if '?' in TARGET_URL else TARGET_URL + '?page=2',
            ]
            for u in test_urls:
                try:
                    resp = await page.goto(u, wait_until="domcontentloaded", timeout=15000)
                    if resp and resp.ok:
                        page2_url = u
                        print(f"  Found working page 2 URL: {u}")
                        break
                except Exception:
                    continue

        if page2_url:
            await asyncio.sleep(random.uniform(3, 8))
            # Natural scroll
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(2)

            page2_links = await page.evaluate("""() => {
                const links = document.querySelectorAll('a[href]');
                return Array.from(links).filter(a => {
                    const text = (a.textContent || '').trim();
                    return text.length >= 4 &&
                           a.getBoundingClientRect().width > 0 &&
                           !/首页|登录|注册|搜索/.test(text);
                }).length;
            }""")
            page2_links_count = page2_links
            print(f"  Candidate links on page 2: {page2_links_count}")
            results["page2_url"] = page2_url
            results["page2_candidate_links"] = page2_links_count

        # Navigate back and try to go beyond known max to find the real end
        # Check if there's a last-page indicator
        if pagination_info['maxPage']:
            print(f"\n[9] Testing max page (pagination suggests {pagination_info['maxPage']})...")
            # Try accessing the max page
            max_page_url = TARGET_URL.replace('.html', f'_{pagination_info["maxPage"]}.html')
            try:
                await page.goto(max_page_url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(random.uniform(3, 5))
                max_page_links = await page.evaluate("""() => {
                    return document.querySelectorAll('a[href]').length;
                }""")
                print(f"  Max page ({pagination_info['maxPage']}) seems valid: {max_page_links} total links")
                results["max_page_test"] = {"page": pagination_info['maxPage'], "totalLinks": max_page_links, "url": max_page_url}
            except Exception as e:
                print(f"  Max page test failed: {e}")

        # Save results
        results["timestamp"] = datetime.now().isoformat()
        output_path = Path(__file__).parent.parent / "output" / "phase1_analysis.json"
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n[10] Analysis saved to: {output_path}")

        # Print execution summary
        print("\n" + "="*60)
        print("EXECUTION SUMMARY")
        print("="*60)
        print(f"站点: {DOMAIN}")
        print(f"页面标题: {page_title}")
        print(f"分页方式: {pagination_info['style']}")
        print(f"WAF: {'Cloudflare detected' if waf_check['hasCFScript'] else 'none detected'}")
        print(f"最大页数: {pagination_info['maxPage'] or 'unknown'}")
        print(f"第1页候选链接数: {len(article_links)}")
        if page2_links_count:
            print(f"第2页候选链接数: {page2_links_count}")
        if pagination_info['maxPage'] and page2_links_count:
            est = pagination_info['maxPage'] * len(article_links)
            print(f"预计抓取链接数量: ~{est}")
        print(f"判断依据: 基于Patchright浏览器渲染的DOM分析")

        await browser.close()

    return results


if __name__ == "__main__":
    asyncio.run(main())
