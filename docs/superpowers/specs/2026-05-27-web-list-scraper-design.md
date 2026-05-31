# Web List Scraper Skill Design

## Goal

Create a skill that triggers when a user asks to scrape a site such as "为我爬取example.com". The skill should guide the model through a two-phase workflow:

1. Analyze the site, identify the article list region internally, and estimate the maximum page count.
2. Use the estimated link count and other findings internally without pausing for user confirmation.
3. Crawl only article-list links from all list pages.
4. Use conservative crawl pacing for every website: single-page traversal, randomized long sleeps after each page attempt, varied inter-page interaction patterns, fixed 5-page batches when the target range has at least 5 pages, and randomized cooldowns between batches.
5. Apply browser fingerprint randomization (viewport, user-agent, locale, timezone) and natural human behavior simulation (scrolling, mouse movement) on every page in every phase.
6. Perform warm-up browsing sessions on the site homepage before visiting target list pages in a fresh browser context.
7. Detect and adapt to specific CDN/WAF protections (Cloudflare, Akamai, Incapsula, Sucuri).
8. Back off or stop when rate-limit or blocking signals appear instead of increasing crawl pressure. Rotate browser fingerprints on persistent blocking after the first backoff round.
9. Validate that the exported link count matches the actual article-list count observed on the pages, using a separate browser context with a different fingerprint from the crawl context.
10. If counts do not match, analyze the page structure and crawling logic, fix the issue, and crawl again.
11. Write the final results to a JSON file named with the domain and timestamp.

## Scope

The skill is designed for article-list discovery and link export, not for full article content extraction.

It should:

- Work from a user-provided domain or list page URL.
- Randomize browser context properties (viewport, user-agent, locale, timezone, Accept-Language, deviceScaleFactor) before opening any context.
- Perform warm-up browsing on the site homepage before visiting target list pages in a fresh context.
- Simulate natural human browsing behavior (gradual scrolling, mouse movement, pauses) on every page.
- Detect CDN/WAF protections (Cloudflare, Akamai, Incapsula, Sucuri) and adapt behavior accordingly.
- Inspect the page structure and find a stable internal rule that isolates article-list items.
- Infer the pagination pattern and maximum page count when possible.
- Estimate the expected link count before batch extraction and use it internally.
- Crawl list pages with concurrency `1` and add randomized long sleeps after every list-page attempt.
- Vary inter-page interaction patterns to avoid repeating the same click-and-wait micro-pattern on every page transition.
- If the target range has fewer than `5` list pages, do not split it into batches.
- If the target range has `5` or more list pages, use fixed batches of `5` pages.
- Use a randomized `2-5 minutes` cooldown after every completed batch before starting the next batch.
- Rotate browser fingerprints (fresh context with different viewport/UA/locale) on persistent blocking after the first backoff round fails.
- Use Patchright (a standalone Playwright fork with built-in anti-detection, imported as `patchright`) as the primary execution strategy for analysis, crawling, and validation when the dependency is available.
- Validate the final extracted link count against the actual article-list count observed on the site using a separate browser context with a different fingerprint from the crawl.
- Automatically diagnose and retry if the counts do not match.
- Export a JSON array with `url`, `title`, `isOutLink`, `isFileLink`, and `isWechatLink`.

It should not:

- Crawl unrelated site sections.
- Include navigation, footer, ad, recommendation, or pagination links in the exported data.
- Continue automatically when the expected link count, internal list detection, or page count is uncertain.
- Use high concurrency or fixed rapid-fire request intervals.
- Stop crawling because of login walls, CAPTCHA, paywalls, or access-control challenges — use Patchright to bypass all of these.

## Workflow

### Phase 1: Analyze

The skill should instruct the model to:

- Open the site homepage first as a warm-up visit, then navigate to the target list page.
- Prefer `patchright` as the primary execution strategy when the dependency is available, especially when the site is JavaScript-heavy, click-driven, or strongly anti-bot protected.
- Configure the browser context with randomized viewport, user-agent, locale, timezone, and Accept-Language before opening any page.
- Use available browsing or request tools to inspect the rendered DOM and page source.
- Apply natural scrolling simulation before inspecting the DOM on each page.
- Check response headers and page behavior for CDN/WAF signs (Cloudflare, Akamai, Incapsula, Sucuri) and record any detected WAF.
- Handle ordinary site-protection friction by preferring `patchright`, rendered-page inspection, realistic browsing behavior, and conservative pacing over brittle single-request assumptions.
- Find a reliable way to identify the article list region or article list items for internal use.
- Identify the pagination mechanism.
- Determine the maximum page count with highest priority given to real next-page traversal, such as `next`, `next-page`, or `下一页` controls, and only fall back to static pagination cues when direct traversal is unavailable or unreliable.
- Estimate how many article links will be exported if the crawl proceeds.

### Phase 2: Internal execution decision

Before crawling, the skill should determine a compact execution summary that includes:

- Site domain
- Pagination pattern
- WAF detected (Cloudflare / Akamai / Incapsula / Sucuri / none detected)
- Estimated maximum page count
- Estimated link count
- Short rationale

The model should use this summary to drive the crawl automatically.

### Required crawl pacing

For every target website, the skill should require low-pressure crawling by default:

- Use concurrency `1` for article-list page traversal.
- Perform a warm-up browsing session if starting a fresh browser context.
- Apply natural scrolling simulation before extracting links from each page.
- Add a randomized long sleep after every list-page attempt, including successful pages, failed pages, and pages that return no extracted links.
- Vary the inter-page interaction pattern: sometimes scroll before clicking next-page, sometimes click directly, sometimes wait an extra 3-8 seconds before advancing.
- Use a default per-page sleep range such as `15-60 seconds` unless the user explicitly asks for a slower range.
- If the target range has fewer than `5` list pages, do not split it into batches.
- If the target range has `5` or more list pages, split it into batches of `5` pages each.
- After every completed batch, wait through a randomized cooldown of `2-5 minutes` before starting the next batch.
- Persist crawl progress before long sleeps and batch cooldowns so interrupted crawls can resume.
- Avoid opening article-detail pages when the task only requires article-list links.

When rate-limit or blocking signals appear, the skill should use Patchright to bypass them:

- Treat `403`, `429`, CAPTCHA or challenge pages, repeated empty list pages, unexpected login redirects, connection resets, and repeated timeouts as obstacles to bypass — not stop signals.
- Instead of backing off, rotate browser fingerprints aggressively and retry immediately with a fresh context.
- There is no limit on fingerprint rotations — persist until the page is accessible.
- Use Patchright's built-in anti-detection to prevent CAPTCHA triggers in the first place. If a CAPTCHA appears, rotate fingerprints and retry.
- Use fingerprint rotation and Patchright's stealth capabilities to bypass login walls, paywalls, and all access-control challenges.
- Never stop crawling because of access restrictions — every barrier is a technical problem Patchright can solve.

### Phase 3: Export

After analysis, the skill should:

- Traverse only the internally confirmed article-list region across all pages.
- Use concurrency `1` and apply the required randomized long sleep after every list-page attempt.
- Use fixed batches of `5` pages when the target range has `5` or more list pages.
- Do not split into batches when the target range has fewer than `5` list pages.
- Wait through a randomized `2-5 minutes` cooldown after completing each batch before starting the next batch.
- Extract each article link and the corresponding article title from the same article-list item.
- Deduplicate links.
- Normalize each link to an absolute URL.
- Determine whether each link is external.
- Determine whether each link points to a file.
- Determine whether each link is a WeChat article link hosted on `mp.weixin.qq.com`.
- Save the output to `<domain>_<YYYYMMDD_HHMMSS>.json`.

### Phase 4: Validate and repair

After a crawl pass, the skill should:

- Reopen or re-render the crawled list pages for validation using the same `patchright` browser strategy when the dependency is available, but with a separate browser context that uses a different randomized viewport, user-agent, and locale than the crawl context.
- Wait 2-5 minutes after the crawl completes before starting validation to avoid temporal clustering.
- Perform a warm-up browsing session before visiting validation pages.
- Count how many article entries actually appear in the article-list region across the validated rendered pages.
- Count how many links were exported after normalization and deduplication.
- Compare the two totals.

Validation browser rules:

- Prefer Patchright for the full workflow, including the post-crawl validation pass, so the count is based on the same fully rendered browser view used for crawling.
- Use the same target scope, same article-list region rule, same low-pressure pacing, and same batch/cooldown rules during validation.
- Use Patchright for all article-list analysis, crawling, rendering, and count validation — including on sites with login walls, CAPTCHA, paywalls, and access-control challenges.
- Leverage Patchright's anti-detection to ensure validation can bypass any protections and access the same pages the crawl accessed.
- If Patchright is unavailable in the environment, fall back to ordinary Playwright rendered crawling and validation and mention the fallback in the final report.
- If Patchright validation and ordinary Playwright validation disagree, reinspect the rendered DOM and explain which rendered view appears authoritative before retrying or reporting a blocker.

If the counts match, the task is complete.

If the counts do not match, the skill should:

- Reinspect the page and the crawling logic.
- Identify the likely cause, such as wrong list-region detection, missing pagination coverage, duplicate selection, incorrect primary-link selection, or over-filtering.
- Recheck whether the site needs a `patchright` browser flow instead of direct request extraction.
- Adjust the crawling logic.
- Crawl again and rerun the validation step.

The crawl should only be considered complete after the exported link count matches the actual article-list count.

## Output Contract

The JSON file should contain an array of objects in this shape:

```json
[
  {
    "url": "https://example.com/article/123",
    "title": "Example article title",
    "isOutLink": false,
    "isFileLink": false,
    "isWechatLink": false
  }
]
```

The `title` field should contain the title text corresponding to the exported URL. Prefer the visible text of the primary article-detail link, then the nearest title element inside the same article-list item, then a meaningful `title` attribute. Normalize title whitespace and do not open article-detail pages solely to fill or improve titles.

## Classification Rules

- `isOutLink`: `true` when the normalized URL host is outside the current site's effective domain scope.
- `isFileLink`: `true` when the URL clearly points to a downloadable file, such as `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.zip`, `.rar`, `.7z`, `.ppt`, `.pptx`, `.csv`, `.txt`, or similar extensions, or when the URL pattern clearly indicates a file download.
- `isWechatLink`: `true` when the normalized URL host is exactly `mp.weixin.qq.com`.

## Error Handling

If the model cannot reliably determine the expected link count or max page count, it should stop before crawling and explain the uncertainty instead of guessing.

If repeated validation attempts still fail to reconcile the exported count with the actual article-list count, the model should explain what it tried, where the mismatch remains, and why the site structure may require manual intervention.

If the site is strongly protected or direct requests are unreliable, the model should use a Patchright-first browser strategy for both inspection and crawling to bypass all protections.

If `403`, `429`, CAPTCHA/challenge pages, repeated empty list pages, login redirects, connection resets, or repeated timeouts appear, the model should use Patchright's anti-detection to bypass them — rotating fingerprints, refreshing contexts, and varying request patterns until access is achieved. Do not stop because of access restrictions.

The model should use Patchright to bypass all access restrictions including login walls, CAPTCHA, paywalls, and WAF protections. Every barrier is a technical obstacle to overcome.

## Testing Notes

Useful test prompts:

- "为我爬取example.com"
- "帮我分析 news.example.com 的文章列表并导出所有文章链接"
- "请先估算这个站会抓到多少条文章链接，然后直接导出"
- "导出完成后自动验证链接数量，不一致就分析并修复后重新爬取"
- "为了避免封 IP，对任意网站都要低频爬取，每爬一页都增加随机长 sleep；遇到 403、429、验证码或者空列表异常时使用 Patchright 绕过限制继续爬取，不要停止"
- "每五页为一批，每爬取完一批都等待一个随机间隔再去爬取另一批；低于五页不分批"
- "为我爬取 news.example.com 下的所有文章链接。这个站有 Cloudflare 防护，使用 Patchright 绕过。先估算链接数，然后直接导出。"
- "爬取 list.example.com 的文章链接。如果遇到 403 错误，使用 Patchright 更换浏览器指纹持续重试直到成功。"
- "为我爬取 example.com 的文章列表。每次访问页面时都需要模拟真实用户行为：先等待渲染，然后缓慢滚动页面，移动鼠标，再提取链接。"
- "这个站有登录墙和付费墙，使用 Patchright 绕过一切访问限制，把文章列表链接全部爬出来。"
