---
name: web-list-scraper
description: Analyze and crawl article-list pages from a website when the user asks to scrape a site, a full URL, or a specific path under a site, estimate how many article links will be captured, estimate the maximum page count, and export article links. Use this whenever the user asks things like "为我爬取example.com", "为我爬取http://www.example.xxx/xxx下的所有文章链接", wants article-list links from a site or栏目 path, asks to export all article links under a specific URL path, or wants a site-wide or section-level list-page link export before content scraping.
---

# Web List Scraper

Use this skill when the user wants article-list links from a website rather than full article content.

This skill is intentionally split into analysis, crawl, and validation phases so the model does not over-crawl the wrong part of the site:

1. Discover the article-list region internally and estimate the pagination range.
2. Crawl the full article list and export links without pausing for user confirmation.
3. Validate that the final exported link count matches the actual article-list count on the crawled pages, preferring a `playwright-stealth` rendered verification pass when available.
4. If the counts do not match, inspect the page and fix the crawling logic, then crawl again.

## What this skill should produce

The final deliverable is a JSON file named:

`<domain>_<YYYYMMDD_HHMMSS>.json`

Each item in the JSON array must have this structure:

```json
{
  "url": "https://example.com/article/123",
  "title": "Example article title",
  "isOutLink": false,
  "isFileLink": false,
  "isWechatLink": false
}
```

Read [references/output-format.md](./references/output-format.md) before exporting results.

The task is only complete when the exported link count matches the actual article-list count found on the crawled pages.

## High-level behavior

- Focus only on article-list pages and article links.
- Ignore navigation, banners, footers, ads, sidebars, tag pages, recommendation modules, and pagination controls.
- Prefer rendered-page inspection and realistic browsing behavior when the site is dynamic or mildly protected.
- Prefer Playwright as the primary execution strategy when the site is dynamically rendered, relies on click-driven pagination, uses load-more interactions, or shows strong anti-bot behavior.
- For every website, use low-pressure crawling by default: single-page traversal, no parallel page fetching, and a randomized long sleep after every list page attempt.
- When the crawl scope is large or the network is unstable, use batched crawling and resumable progress tracking rather than trying to finish everything in one pass.
- Do not guess when the expected link count or maximum page count is uncertain.
- If the crawl scope is too uncertain to execute reliably, stop and explain the uncertainty instead of pausing for confirmation.
- After extraction, self-verify the exported link count against the actual article-list count.
- If the counts do not match, diagnose the issue, adjust the crawling logic, and retry.
- Do not report completion while there are unfinished pages, unresolved failed pages, or validation mismatches.

## Default crawl pacing

Use conservative crawl pacing for every target site, even if the site does not appear protected.

Required pacing rules:

- Crawl list pages with concurrency `1`.
- Add a randomized long sleep after every list page attempt, including successful pages, failed pages, and pages with no extracted links.
- Use a default per-page sleep range of `15-60 seconds` unless the user explicitly asks for a slower range.
- If the target range has fewer than `5` list pages, do not split it into batches.
- If the target range has `5` or more list pages, split it into batches of `5` pages each.
- After every completed batch, wait through a randomized cooldown of `2-5 minutes` before starting the next batch.
- Randomize wait durations and avoid fixed request intervals.
- Persist progress before long sleeps and batch cooldowns so the crawl can resume safely if interrupted.
- Do not open article-detail pages when the requested output only needs article-list links.

If the site shows rate-limit or blocking signals, stop increasing pressure and switch to backoff:

- Treat `403`, `429`, CAPTCHA/challenge pages, repeated empty list pages, unexpected login redirects, connection resets, or repeated timeouts as blocking or throttling signals.
- Use exponential backoff with a longer randomized wait before retrying, such as `2-5 minutes`, then `10-30 minutes`.
- Limit retries for the same page.
- If the page remains blocked after limited retries, record it in the failed-page queue or stop with a clear explanation.
- Do not attempt to bypass login walls, CAPTCHA, paywalls, or access-control challenges.

## Preferred protected-site strategy: Playwright

When the target site has strong anti-scraping behavior, default to Playwright-first execution instead of plain HTTP requests.

Use Playwright to:

- open the actual page in a browser context
- wait for client-side rendering to complete
- inspect the rendered DOM rather than relying only on raw HTML
- click numbered pagination, next-page controls, or load-more buttons when needed
- preserve the same browser context across pages so cookies and session state remain consistent
- observe the real network behavior when article lists are loaded through XHR or fetch requests

Prefer Playwright over direct requests when you see signs such as:

- the page content is injected by JavaScript
- list data appears only after page interaction
- pagination depends on clicking rather than simple URL changes
- the site uses dynamic tokens, short-lived parameters, or request signatures
- direct requests return incomplete, empty, or misleading HTML

When Playwright is in use:

- follow the page's natural interaction flow instead of guessing hidden endpoints first
- extract from the rendered DOM when that is the most reliable source
- if useful, inspect the browser's real network responses to understand where list data is coming from
- keep the crawl scoped to the user-requested domain or path even if the page loads auxiliary assets from elsewhere
- keep one browser context for the crawl where practical so normal cookies and session state persist
- still apply the default per-page randomized long sleep and batch cooldown rules

Do not fall back to direct request scraping unless it is clearly sufficient and more reliable for the current target.

## Large-crawl and unstable-network strategy

When the target scope is large, the page count is high, or the network is unreliable, do not rely on a single uninterrupted crawl.

Instead:

- split the crawl into fixed batches of `5` list pages when the target range has `5` or more pages
- do not split into batches when the target range has fewer than `5` pages
- persist progress after each batch
- keep a retry queue for failed pages
- resume from the last unfinished point instead of restarting from zero

Prefer this strategy when:

- the total page count is high
- the article count is large
- the site is slow or intermittently reachable
- SSL, timeout, or transient network errors appear during the crawl

## Batched crawling

When using batched crawling:

1. If the target page range has fewer than `5` list pages, crawl it as a single unbatched range.
2. If the target page range has `5` or more list pages, divide it into batches of `5` pages each.
3. Crawl one batch at a time.
4. Apply the required randomized long sleep after each page attempt.
5. After each batch, persist intermediate progress and accumulated results.
6. Wait through a randomized `2-5 minutes` batch cooldown before continuing unless the crawl is stopping.
7. Continue with the next unfinished batch.

Each batch should track:

- covered page range
- pages completed successfully
- pages that failed and need retry
- current accumulated link count

Do not treat a partially completed batch as final completion.

## Resumable progress tracking

During long crawls, maintain resumable state so the crawl can continue after interruption.

At minimum, track:

- the current page or current batch range
- the set of normalized links already collected
- the list of failed pages
- which page ranges are complete and which are still pending
- the current output filename or run timestamp

If the crawl is interrupted, resume from the unfinished pages or failed-page queue instead of restarting the entire job unless the stored state is clearly invalid.

## SSL and network failure handling

If SSL or network-related errors occur, do not immediately treat the crawl as permanently failed.

Use this recovery order:

1. Retry the same page a limited number of times.
2. Increase wait time or timeout if the failure appears transient.
3. Apply a longer randomized backoff before retrying.
4. Prefer Playwright-driven page access if direct requests are failing.
5. If direct requests return incomplete content but the browser can render the page, trust the rendered browser result.
6. Record the page in a failed-page queue if it still cannot be completed in the current pass.

Examples of recoverable problems include:

- SSL connection errors
- handshake failures
- read timeouts
- connection resets
- intermittent empty or partial responses

Treat these as retryable unless repeated attempts show the page is consistently unreachable.

## Phase 1: Analyze the site

When the user gives a domain, a full URL, or a section path URL:

1. Open the homepage or the most likely article-list entry page.
   - If the user gives a full path such as `http://www.example.xxx/xxx`, start from that exact URL instead of backing up to the homepage unless the path is clearly unusable.
2. Inspect the rendered page structure, not just raw HTML, when dynamic content is present.
3. Identify the DOM region that consistently contains article-list items.
4. Derive a stable internal rule for the list container or the list items.
5. Determine the pagination style:
   - query parameter pagination
   - path-based pagination
   - next-page links
   - numbered pagination
   - load-more style pagination
6. Determine the maximum page count using this priority order:
   - first, look for a `next`, `next-page`, `下一页`, or equivalent next-page control and advance through the actual pagination flow to determine where the list truly ends
   - if a real next-page flow is unavailable or unreliable, fall back to numbered pagination, last-page links, or other strong pagination evidence
   - for load-more flows, keep triggering the loading interaction until no new article entries appear
7. Estimate how many article-detail links will be exported if the crawl proceeds.

Use ordinary anti-bot-aware tactics that stay within the user's request and your available tools, such as:

- preferring Playwright as the first choice for strong anti-bot or JavaScript-heavy sites
- preferring a browser-rendered view when content is injected client-side
- checking multiple adjacent pages to verify internal list-detection stability
- preferring actual next-page traversal over static page-count guessing whenever a usable next-page control exists
- comparing DOM patterns rather than relying on one fragile page snapshot

Do not treat the internal list-detection rule as reliable unless it survives that basic cross-check.

Respect the user's scope literally:

- If they ask for the whole site, search for the relevant site-wide article list entry.
- If they ask for a specific section, channel, or path under a domain, keep the crawl limited to that section unless they later broaden it.
- If the supplied URL is already a list page or a section landing page, treat it as the primary crawl scope.

## Maximum page-count rule

Do not treat the maximum page count as a static guess when a real next-page control is available.

Use this priority order:

1. First choice: find a usable `next`, `next-page`, `下一页`, or equivalent control and move through the real pagination flow until the list no longer advances.
2. Second choice: if a next-page control is missing, broken, or misleading, use numbered pagination or a visible last-page link.
3. Third choice: if the site uses load-more behavior, keep loading until no new article entries appear.
4. Final fallback: infer from other strong evidence only when direct traversal is not possible.

When using the first-choice strategy:

- verify that the list actually changes after each next-page action
- track visited pages or page states so loops or repeated pages are detected
- stop when the next-page control disappears, becomes disabled, or no longer changes the list content
- use the number of successfully advanced list pages as the authoritative max-page result

If pagination controls behave inconsistently, prefer observed traversal results over static page labels.

## Phase 1 output: Execution summary

Before crawling, determine the crawl scope with an internal summary in this shape:

```text
站点: <domain>
分页方式: <query/path/next-button/load-more/other>
最大页数: <number or uncertainty note>
预计抓取链接数量: <number or uncertainty note>
判断依据: <short rationale>
```

Do not stop to ask the user to confirm these values. Use them to drive the crawl automatically.

If the expected link count or max page count is too uncertain to support reliable crawling, stop and explain the uncertainty.

## Phase 2: Crawl automatically

After the analysis completes:

1. Traverse all list pages within the determined page range.
   - Use Playwright by default when the site is dynamic, click-driven, or strongly protected.
   - If the target range has `5` or more list pages, process it in batches of `5` pages and persist progress after each batch.
   - If the target range has fewer than `5` list pages, do not split it into batches.
   - Always crawl with concurrency `1` and apply the default randomized long sleep after every list page attempt.
2. Restrict extraction to anchors inside the internally confirmed article-list region.
3. Extract the article title that corresponds to each exported link.
4. Normalize every extracted link to an absolute URL.
5. Deduplicate links after normalization.
6. Classify each link as `isOutLink`, `isFileLink`, and `isWechatLink`.
7. Write the JSON file using the required filename pattern.
8. Validate the exported link count against the actual article-list count observed across the crawled pages, using the validation rules below.
9. If the counts do not match, analyze the page structure and the crawling logic, fix the issue, and crawl again.
10. Only report completion when the counts match.
11. Tell the user where the file was written and how many links were exported.

## Self-validation loop

After each crawl pass:

1. Check whether every intended page in the target range has been completed or recovered from the failed-page queue.
2. Reopen or re-render the crawled list pages for validation, preferring a `playwright-stealth` browser context when the dependency is available.
3. Count the actual number of article entries in the internally confirmed article-list region across the validated rendered pages.
4. Count the number of exported links after normalization and deduplication.
5. Compare the two totals.

Validation browser rules:

- Prefer `playwright-stealth` for the post-crawl validation pass so the count is based on a fully rendered browser view.
- Use the same target scope, same article-list region rule, same low-pressure pacing, and same batch/cooldown rules during validation.
- Use `playwright-stealth` only to validate public article-list rendering and counts.
- Do not use `playwright-stealth` to bypass login walls, CAPTCHA, paywalls, or access-control challenges.
- If `playwright-stealth` is unavailable in the environment, fall back to ordinary Playwright rendered validation and mention the fallback in the final report.
- If stealth validation and ordinary Playwright validation disagree, reinspect the rendered DOM and explain which rendered view appears authoritative before retrying or reporting a blocker.

If all target pages are complete and the counts are equal:

- treat the crawl as successful
- report completion

If any target pages remain unfinished, or if the counts are not equal:

1. Reinspect the rendered page and extraction scope.
2. Check for common logic errors, including:
   - wrong list-region detection
   - missing or partial pagination coverage
   - choosing the wrong anchor inside a list item
   - over-filtering valid article links
   - under-filtering unrelated links
   - duplicate handling that collapses distinct article URLs incorrectly
   - direct-request scraping missing content that is visible in the browser
   - failing to click through load-more or interactive pagination states
   - interrupted batches that were not resumed
   - SSL or network failures that prevented some pages from completing
3. Fix the crawling logic.
4. Retry failed pages and unfinished batches.
5. Crawl again.
6. Repeat the validation.

Do not claim success while the exported count and actual article-list count still differ, or while unfinished pages remain.

## Extraction rules

Only export links that belong to article-list entries.

Do not export:

- site navigation links
- home or section landing links
- breadcrumb links
- previous or next page controls
- page number links
- recommendation or related-content modules outside the confirmed list region
- login, share, print, search, or attachment controls unless they are the article link itself

If a list item contains multiple links, prefer the primary article-detail link.

For each exported link, include the corresponding article title:

- Add a `title` string field to every output item.
- Prefer the visible text of the primary article-detail link.
- If the primary link text is empty or generic, use the nearest title element inside the same article-list item, such as a heading, title span, or title attribute.
- Normalize title whitespace by trimming leading/trailing whitespace and collapsing repeated internal whitespace.
- Keep the title tied to the same list item as the exported URL.
- Do not open article-detail pages solely to fill or improve titles.

## Classification rules

Follow the exact rules in [references/output-format.md](./references/output-format.md).

In short:

- `isOutLink` is `true` when the link host falls outside the target site's domain scope.
- `isFileLink` is `true` when the link points to a downloadable document or archive, or clearly behaves like a file download URL.
- `isWechatLink` is `true` when the normalized URL host is exactly `mp.weixin.qq.com`.

## Filename rule

Use the target domain plus a timestamp:

`example.com_20260527_143015.json`

If the user provides a subdomain, keep that subdomain in the filename unless the user asks otherwise.

## Safety and ambiguity handling

- If there is no clear article-list page, stop and explain what you found.
- If the site appears to require login, paid access, or a challenge you cannot complete, explain that and stop.
- If strong anti-bot behavior blocks direct requests, switch to Playwright-first crawling rather than persisting with brittle request-only extraction.
- If SSL or network errors interrupt the crawl, switch into retry-and-resume mode rather than treating the first failure as final.
- If pagination is ambiguous, do not invent a maximum page count. Present the uncertainty in the execution summary.
- If the expected link count is ambiguous, do not invent a confident total. Present the uncertainty in the execution summary.
- If multiple candidate list regions exist, show the best candidate first and briefly mention the ambiguity.
- If repeated repair attempts still leave a count mismatch, explain the remaining discrepancy and what appears to be causing it.
- If repeated retries still leave unfinished pages because of persistent SSL, network, login, or access failures, report exactly which pages or ranges remain incomplete and why they could not be recovered.

## Examples

### Example 1

User:

`为我爬取example.com`

Expected behavior:

- estimate how many article links will likely be exported
- estimate max pages
- proceed to crawl automatically
- validate counts before reporting completion

### Example 2

User:

`帮我分析 https://news.example.com/list/1.html 预计会抓到多少条文章链接和最大页数，然后直接导出全部链接`

Expected behavior:

- analyze that list page directly
- verify pagination pattern
- proceed without a confirmation pause
- validate counts before finishing

### Example 3

User:

`为我爬取 http://www.example.xxx/xxx 下的所有文章链接`

Expected behavior:

- treat the provided path as the crawl scope
- identify article-list pages within that section only
- estimate the expected link count and max pages
- export automatically within that scope

### Example 4

User:

`爬完后自己验证一下，抓到的链接数量要和网页文章列表里的实际文章数量一致，不一致就检查并修复后重爬`

Expected behavior:

- perform the crawl
- compare exported link count with actual article-list count
- if mismatched, diagnose and retry
- only finish when the counts match or a clear blocking reason remains

### Example 5

User:

`如果内容太多就分批爬，网络不好或者 SSL 报错就断点续爬和重试，没爬完不要结束`

Expected behavior:

- split the crawl into batches of `5` pages when the target range has at least `5` pages
- do not split into batches when the target range has fewer than `5` pages
- persist progress between batches
- wait through a randomized interval after completing each batch before starting the next batch
- retry SSL or transient network failures
- resume unfinished pages instead of restarting blindly
- only finish when all target pages are complete and the final counts validate
