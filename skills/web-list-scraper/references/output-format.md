# Output Format And Link Classification

## JSON output

Write a JSON array. Each item must contain:

- `url`: normalized absolute URL
- `isOutLink`: boolean
- `isFileLink`: boolean
- `isWechatLink`: boolean

Example:

```json
[
  {
    "url": "https://example.com/article/123",
    "isOutLink": false,
    "isFileLink": false,
    "isWechatLink": false
  },
  {
    "url": "https://cdn.example.net/report.pdf",
    "isOutLink": true,
    "isFileLink": true,
    "isWechatLink": false
  },
  {
    "url": "https://mp.weixin.qq.com/s/abc123",
    "isOutLink": true,
    "isFileLink": false,
    "isWechatLink": true
  }
]
```

## Filename

Use:

`<domain>_<YYYYMMDD_HHMMSS>.json`

Examples:

- `example.com_20260527_143015.json`
- `news.example.com_20260527_143015.json`

## URL normalization

Before deduplication and classification:

1. Resolve relative URLs against the current page.
2. Prefer `https` when the resolved page is `https`.
3. Remove obvious duplicate fragments when they do not change the target resource.
4. Keep query parameters when they appear to identify the resource.

## `isOutLink` rule

Mark `isOutLink` as `true` when the normalized URL host is outside the target site's domain scope.

Examples for target domain `example.com`:

- `https://example.com/a/1` -> `false`
- `https://www.example.com/a/1` -> `false`
- `https://news.example.com/a/1` -> `false`
- `https://other-site.com/a/1` -> `true`

If the site uses a clearly separate content CDN or document host and the link still represents an article-detail destination chosen from the list, mark the value based on host reality rather than guessing intent.

## `isFileLink` rule

Mark `isFileLink` as `true` when the URL clearly points to a file or a download endpoint.

Common file extensions include:

- `.pdf`
- `.doc`
- `.docx`
- `.xls`
- `.xlsx`
- `.csv`
- `.ppt`
- `.pptx`
- `.zip`
- `.rar`
- `.7z`
- `.txt`
- `.rtf`

Also treat URLs as file links when they include strong download cues, such as:

- `/download/`
- `download=`
- `attachment`
- `file=`

When in doubt, prefer a conservative judgment and keep the reasoning consistent across all exported links.

## `isWechatLink` rule

Mark `isWechatLink` as `true` when the normalized URL host is exactly:

- `mp.weixin.qq.com`

Examples:

- `https://mp.weixin.qq.com/s/abc123` -> `true`
- `https://example.com/article/1` -> `false`
- `https://weixin.qq.com/` -> `false`

`isWechatLink` is independent from the other fields. In most cases, a WeChat article URL will also be an external link and not a file link.
