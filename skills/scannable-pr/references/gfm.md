# GFM for PR bodies — edge cases

## Alert rules

| Rule | Detail |
|------|--------|
| Line break after type | `> [!NOTE]` then next line `> body` |
| Every content line needs `>` | standard blockquote |
| No indent | indented alerts do not render |
| No nest | alerts cannot nest in other elements |
| ≤2 per body | avoid consecutive alerts |
| Old syntax dead | `> **Note**` no longer works |

Types: `NOTE` · `TIP` · `IMPORTANT` · `WARNING` · `CAUTION`

## details

```html
<details>
<summary>label</summary>

fenced code needs a blank line after summary

</details>
```

Default open: `<details open>`.

## Pitfalls

| Symptom | Cause |
|---------|-------|
| Alert blank | indent / same-line body / old `**Note**` |
| Code missing in details | no blank line after `</summary>` |
| Permalink not a card | pasted in `.md` file or cross-repo |
| Color swatch missing | not in issue/PR/discussion, or spaces in backticks |
| `*` in PR title italicizes | titles do not escape Markdown |

## Also supported in PR body

- Color: `` `#0969DA` `` → swatch
- Math: `$...$` / `$$...$$`
- Footnotes: `[^1]` (not in wikis)
- Hide draft: `<!-- comment -->`
- Mentions: `@user` / `@org/team`
- Auto-close keywords: close(s/d) · fix(es/ed) · resolve(s/d)

## PR template paths

| Path | Role |
|------|------|
| `.github/pull_request_template.md` | default |
| `docs/pull_request_template.md` | default |
| `.github/PULL_REQUEST_TEMPLATE/*.md` | multi + `?template=` |

## Official docs

- https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts
- https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting
