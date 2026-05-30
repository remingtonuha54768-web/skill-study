# Web List Scraper Skill Design

## Goal

Create a skill that triggers when a user asks to scrape a site such as "为我爬取example.com". The skill should guide the model through a two-phase workflow:

1. Analyze the site, identify the article list region internally, and estimate the maximum page count.
2. Use the estimated link count and other findings internally without pausing for user confirmation.
3. Crawl only article-list links from all list pages.
4. Use conservative crawl pacing for every website: single-page traversal, randomized long sleeps after each page attempt, fixed 5-page batches when the target range has at least 5 pages, and randomized cooldowns between batches.
5. Back off or stop when rate-limit or blocking signals appear instead of increasing crawl pressure.
6. Validate that the exported link count matches the actual article-list count observed on the pages.
7. If counts do not match, analyze the page structure and crawling logic, fix the issue, and crawl again.
8. Write the final results to a JSON file named with the domain and timestamp.

## Scope

The skill is designed for article-list discovery and link export, not for full article content extraction.

It should:

- Work from a user-provided domain or list page URL.
- Inspect the page structure and find a stable internal rule that isolates article-list items.
- Infer the pagination pattern and maximum page count when possible.
- Estimate the expected link count before batch extraction and use it internally.
- Crawl list pages with concurrency `1` and add randomized long sleeps after every list-page attempt.
- If the target range has fewer than `5` list pages, do not split it into batches.
- If the target range has `5` or more list pages, use fixed batches of `5` pages.
- Use a longer randomized cooldown after every completed batch before starting the next batch.
- Validate the final extracted link count against the actual article-list count observed on the site.
- Automatically diagnose and retry if the counts do not match.
- Export a JSON array with `url`, `title`, `isOutLink`, `isFileLink`, and `isWechatLink`.

It should not:

- Crawl unrelated site sections.
- Include navigation, footer, ad, recommendation, or pagination links in the exported data.
- Continue automatically when the expected link count, internal list detection, or page count is uncertain.
- Use high concurrency or fixed rapid-fire request intervals.
- Attempt to bypass login walls, CAPTCHA, paywalls, or access-control challenges.

## Workflow

### Phase 1: Analyze

The skill should instruct the model to:

- Open the site entry page or list page.
- Prefer Playwright as the primary execution strategy when the site is JavaScript-heavy, click-driven, or strongly anti-bot protected.
- Use available browsing or request tools to inspect the rendered DOM and page source.
- Handle ordinary site-protection friction by preferring realistic browsing behavior, rendered-page inspection, and conservative pacing over brittle single-request assumptions.
- Find a reliable way to identify the article list region or article list items for internal use.
- Identify the pagination mechanism.
- Determine the maximum page count with highest priority given to real next-page traversal, such as `next`, `next-page`, or `下一页` controls, and only fall back to static pagination cues when direct traversal is unavailable or unreliable.
- Estimate how many article links will be exported if the crawl proceeds.

### Phase 2: Internal execution decision

Before crawling, the skill should determine a compact execution summary that includes:

- Site domain
- Pagination pattern
- Estimated maximum page count
- Estimated link count
- Short rationale

The model should use this summary to drive the crawl automatically.

### Required crawl pacing

For every target website, the skill should require low-pressure crawling by default:

- Use concurrency `1` for article-list page traversal.
- Add a randomized long sleep after every list-page attempt, including successful pages, failed pages, and pages that return no extracted links.
- Use a default per-page sleep range such as `15-60 seconds` unless the user explicitly asks for a slower range.
- If the target range has fewer than `5` list pages, do not split it into batches.
- If the target range has `5` or more list pages, split it into batches of `5` pages each.
- After every completed batch, wait through a longer randomized cooldown, such as `3-10 minutes`, before starting the next batch.
- Persist crawl progress before long sleeps and batch cooldowns so interrupted crawls can resume.
- Avoid opening article-detail pages when the task only requires article-list links.

When rate-limit or blocking signals appear, the skill should stop increasing pressure and back off:

- Treat `403`, `429`, CAPTCHA or challenge pages, repeated empty list pages, unexpected login redirects, connection resets, and repeated timeouts as blocking or throttling signals.
- Use longer randomized backoff before retrying, such as `2-5 minutes`, then `10-30 minutes`.
- Limit retries for the same page.
- If the page remains blocked after limited retries, record it in the failed-page queue or stop with a clear explanation.
- Do not attempt to bypass login, CAPTCHA, paywall, or access-control challenges.

### Phase 3: Export

After analysis, the skill should:

- Traverse only the internally confirmed article-list region across all pages.
- Use concurrency `1` and apply the required randomized long sleep after every list-page attempt.
- Use fixed batches of `5` pages when the target range has `5` or more list pages.
- Do not split into batches when the target range has fewer than `5` list pages.
- Wait through a randomized cooldown after completing each batch before starting the next batch.
- Extract each article link and the corresponding article title from the same article-list item.
- Deduplicate links.
- Normalize each link to an absolute URL.
- Determine whether each link is external.
- Determine whether each link points to a file.
- Determine whether each link is a WeChat article link hosted on `mp.weixin.qq.com`.
- Save the output to `<domain>_<YYYYMMDD_HHMMSS>.json`.

### Phase 4: Validate and repair

After a crawl pass, the skill should:

- Count how many article entries actually appear in the article-list region across the crawled pages.
- Count how many links were exported after normalization and deduplication.
- Compare the two totals.

If the counts match, the task is complete.

If the counts do not match, the skill should:

- Reinspect the page and the crawling logic.
- Identify the likely cause, such as wrong list-region detection, missing pagination coverage, duplicate selection, incorrect primary-link selection, or over-filtering.
- Recheck whether the site needs a Playwright-driven browser flow instead of direct request extraction.
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

If the site is strongly protected and direct requests are unreliable, the model should explicitly favor a Playwright-first browser strategy for both inspection and crawling.

If `403`, `429`, CAPTCHA/challenge pages, repeated empty list pages, login redirects, connection resets, or repeated timeouts appear, the model should back off with longer randomized waits, retry only a limited number of times, then record the page as failed or stop with a clear explanation.

The model should not attempt to bypass login walls, CAPTCHA, paywalls, or access-control challenges.

## Testing Notes

Useful test prompts:

- "为我爬取example.com"
- "帮我分析 news.example.com 的文章列表并导出所有文章链接"
- "请先估算这个站会抓到多少条文章链接，然后直接导出"
- "导出完成后自动验证链接数量，不一致就分析并修复后重新爬取"
- "为了避免封 IP，对任意网站都要低频爬取，每爬一页都增加随机长 sleep；遇到 403、429、验证码或者空列表异常时要退避或停止说明"
- "每五页为一批，每爬取完一批都等待一个随机间隔再去爬取另一批；低于五页不分批"
