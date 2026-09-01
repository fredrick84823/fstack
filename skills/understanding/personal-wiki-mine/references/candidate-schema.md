# Candidate Schema

Use this exact structure for each candidate:

```markdown
## #N. [pattern-type] Claim title

**證據**:
1. [source: ...] ...
2. [source: ...] ...
3. [source: ...] ...

**假說**: ...

**反駁路徑**: ...

**Filter 自評**:
- 三點以上 pattern: _
- 指向使用者本人: _
- 可被反駁: _
- 有 generative 後果: _
- 創造新詞/視角: _
- 跨脈絡機制抽象: _

**自評總分**: _ /30

**所以下一步可能是**: ...

---

[使用者區]

**使用者打分** (1-5 each):
- Surprise（讓你注意到沒注意過的）: _
- Specificity（證據具體準確）: _
- Generativity（暗示真的下一步）: _

**平均**: _
**通過**（avg >= 4.0）: yes / no
**註記**: _
```

Rules:

- `證據` must contain at least 3 items.
- Evidence should span at least 2 source types.
- `假說` must state a mechanism, not just similarity.
- `反駁路徑` must be testable.
- `所以下一步可能是` must imply an operation, not a vague reframe.
