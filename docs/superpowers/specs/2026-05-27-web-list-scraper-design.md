# Web List Scraper Skill Design

## Goal

Create a skill that triggers when a user asks to scrape a site such as "为我爬取example.com". The skill should guide the model through a two-phase workflow:

1. Analyze the site, identify the article list region internally, and estimate the maximum page count.
2. Use the estimated link count and other findings internally without pausing for user confirmation.
3. Crawl only article-list links from all list pages.
4. Validate that the exported link count matches the actual article-list count observed on the pages.
5. If counts do not match, analyze the page structure and crawling logic, fix the issue, and crawl again.
6. Write the final results to a JSON file named with the domain and timestamp.

## Scope

The skill is designed for article-list discovery and link export, not for full article content extraction.

It should:

- Work from a user-provided domain or list page URL.
- Inspect the page structure and find a stable internal rule that isolates article-list items.
- Infer the pagination pattern and maximum page count when possible.
- Estimate the expected link count before batch extraction and use it internally.
- Validate the final extracted link count against the actual article-list count observed on the site.
- Automatically diagnose and retry if the counts do not match.
- Export a JSON array with `url`, `isOutLink`, `isFileLink`, and `isWechatLink`.

It should not:

- Crawl unrelated site sections.
- Include navigation, footer, ad, recommendation, or pagination links in the exported data.
- Continue automatically when the expected link count, internal list detection, or page count is uncertain.

## Workflow

### Phase 1: Analyze

The skill should instruct the model to:

- Open the site entry page or list page.
- Prefer Playwright as the primary execution strategy when the site is JavaScript-heavy, click-driven, or strongly anti-bot protected.
- Use available browsing or request tools to inspect the rendered DOM and page source.
- Handle ordinary anti-bot friction by preferring realistic browsing behavior and rendered-page inspection over brittle single-request assumptions.
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

### Phase 3: Export

After analysis, the skill should:

- Traverse only the internally confirmed article-list region across all pages.
- Extract and deduplicate links.
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
    "isOutLink": false,
    "isFileLink": false,
    "isWechatLink": false
  }
]
```

## Classification Rules

- `isOutLink`: `true` when the normalized URL host is outside the current site's effective domain scope.
- `isFileLink`: `true` when the URL clearly points to a downloadable file, such as `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.zip`, `.rar`, `.7z`, `.ppt`, `.pptx`, `.csv`, `.txt`, or similar extensions, or when the URL pattern clearly indicates a file download.
- `isWechatLink`: `true` when the normalized URL host is exactly `mp.weixin.qq.com`.

## Error Handling

If the model cannot reliably determine the expected link count or max page count, it should stop before crawling and explain the uncertainty instead of guessing.

If repeated validation attempts still fail to reconcile the exported count with the actual article-list count, the model should explain what it tried, where the mismatch remains, and why the site structure may require manual intervention.

If the site is strongly protected and direct requests are unreliable, the model should explicitly favor a Playwright-first browser strategy for both inspection and crawling.

## Testing Notes

Useful test prompts:

- "为我爬取example.com"
- "帮我分析 news.example.com 的文章列表并导出所有文章链接"
- "请先估算这个站会抓到多少条文章链接，然后直接导出"
- "导出完成后自动验证链接数量，不一致就分析并修复后重新爬取"
