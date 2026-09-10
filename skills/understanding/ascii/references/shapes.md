# 五種圖型

挑選看你要讓讀者看見什麼關係。錯的圖型比歪的框線更傷 —— 用流程圖表達比較，讀者得自己重建那張表。

| 要表達 | 圖型 | 判準 |
|---|---|---|
| A 之後發生 B | flow | 有方向、有分支 |
| A 底下有 B | hierarchy | 有從屬、無方向 |
| A 與 B 差在哪 | comparison | 同一組維度、多個對象 |
| 現在在哪一格 | state | 節點互斥，邊是事件 |
| 誰對誰說了什麼 | sequence | 參與者固定，時間往下 |

## flow

分支用縮排表達，不要拉斜線 —— 斜線在等寬字型裡永遠對不準。

```
merge to main
      │
      ├─ 有 deploy.yaml ──→ 比對上次成功的 commit
      │                         │
      │                         ├─ 有變動 ──→ 重部這台
      │                         └─ 無變動 ──→ skip
      │
      └─ 無 deploy.yaml ──→ 不歸 CI 管
```

## hierarchy

樹用 `├─` 與 `└─`，最後一個分支才是 `└─`。子層的續接線是 `│` 加三個空格。

```
service-monorepo
├── services/
│   ├── docs-api/          production 5/5
│   └── sheets-api/        staging only
├── infra/terraform/envs/
│   ├── staging/
│   └── production/
└── docs/workflows/ci-cd.md
```

## comparison

兩三個對象用 markdown 表格就好，ASCII 表格只在**需要對齊數字欄**或**表格要進 code block** 時才划算。

```
                     staging              production
──────────────────────────────────────────────────────────
觸發               merge to main        GitHub Release
範圍               有變動的那幾台        同左
image tag          :<short-sha>         :<short-sha>
誰能發              CI                   任何人，owner 決定時機
```

分隔線用 `─` 拉滿欄寬，不要用 `-`（混用兩套字元）。

## state

節點互斥時才用。邊上寫事件，不寫條件。

```
        ┌─────────┐  ready-for-agent   ┌─────────┐
        │ 待開始  │ ─────────────────→ │ 進行中  │
        └─────────┘                    └─────────┘
                                            │
                          ┌─────────────────┴──────────────┐
                    PR merged                        阻塞超過 14 天
                          │                                │
                          ↓                                ↓
                     ┌─────────┐                      ┌─────────┐
                     │  完成   │                      │  暫停   │
                     └─────────┘                      └─────────┘
```

## sequence

參與者一行排開，各自往下拉 `│`。訊息用 `──→` 橫跨，回應用 `←──`。

```
  developer          GitHub Actions         Cloud Run
      │                    │                    │
      │  push prod-tag     │                    │
      │───────────────────→│                    │
      │                    │  plan（不部署）     │
      │←───────────────────│                    │
      │  取消 pre-release   │                    │
      │───────────────────→│                    │
      │                    │  deploy :sha       │
      │                    │───────────────────→│
      │                    │                    │
```

參與者超過四個就別畫 —— 橫向寬度會爆掉，改用編號清單。
