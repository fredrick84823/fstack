# Engineering

單次工具，沒有 artifact 鏈 —— 你現在需要一件事做完。跟 [`pipeline/`](../pipeline/README.md) 的階段式相對。

**Model-invoked** — the model can reach for these when the description matches.

- **[codex-brainstorm](./codex-brainstorm/SKILL.md)**: Adversarial brainstorming. Claude and Codex independently research then debate until Nash equilibrium. For solution exploration, feasibility analysis,…
- **[codex-cli-review](./codex-cli-review/SKILL.md)**: Use Codex CLI (not MCP) to review uncommitted changes. Codex explores the codebase independently with full disk read access
- **[describe-pr](./describe-pr/SKILL.md)**: Write a pull request description a reviewer can digest without opening the diff
- **[scannable-pr](./scannable-pr/SKILL.md)**: Write a scannable GitHub PR body
- **[work-wrap-up](./work-wrap-up/SKILL.md)**: 功能完成後的收尾三連發：commit+PR → 進度同步 → (選配) Slack 通知
- **[writing-great-issues](./writing-great-issues/SKILL.md)**: 把問題、提案或工作項寫成顆粒度適中的 GitHub issue，預設產出 draft
