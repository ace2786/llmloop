# 前端任务：接上「单题删除」和「题目搜索」

> 给负责前端的人。你已经写完了三页，这次只加两个功能，**不要重写、不要重构已有代码**。
> 接口契约由后端那份文档定义，这里只写你要做的部分。

---

## 一、前置：后端会新增什么

后端正在改，改完这两个能力才可用：

```
① DELETE /apps/{app_id}/questions/{question_id}
   → { "deleted": 123, "splits": {optimize,valid,test,total} }

② GET /apps/{app_id}/questions?split=&q=&limit=&offset=
   → { total, splits, matched, items }      ← matched 是新字段
```

**`matched` = 当前 split + 关键词过滤后的条数。** `total` 和 `splits` 语义不变（仍是全量统计）。

---

## 二、改动 1：删除单题

### 位置

`src/pages/QuestionsPage.tsx` 的题目列表行（`.q-row`）。

### 交互

1. 每行末尾加一个「删除」按钮（小号、幽灵样式、红色文字，不要抢视觉）
2. 点击 → 弹 `ConfirmDialog`（复用你已有的组件），标题「删除这道题」，
   正文显示题目内容前 40 字 + 「此操作不可撤销」
3. 确认 → 调 `DELETE`，**用返回的 `splits` 直接更新统计卡**，不要额外再发一次 `/stats`
4. 成功后：如果当前页变空（删掉最后一条），复用你已有的越界回退逻辑自动回上一页
5. 失败 → `Banner kind="error"` 显示 `errorMessage(err)`，列表保持不变

### 代码骨架

```ts
// src/api/types.ts
export interface DeleteQuestionResult {
  deleted: number
  splits: SplitCounts
}

// src/api/index.ts —— questionsApi 里新增
remove: (appId: number, questionId: number) =>
  request<DeleteQuestionResult>(`/apps/${appId}/questions/${questionId}`, {
    method: 'DELETE',
  }),
```

---

## 三、改动 2：题目搜索

### 位置

`QuestionsPage.tsx` 的「题目列表」卡片头部，和分页下拉并排。

### 交互

1. 加一个搜索框，占位符「搜索题目或出处」
2. **输入防抖 300ms** 后发请求，不要每敲一个字就请求
3. 搜索参数通过 `q` 传给后端，**和 `split`、`limit`、`offset` 叠加**
4. **搜索词变化时必须把 `page` 重置为 0**（否则会停在越界页）
5. 有搜索词时，在列表上方显示一行「搜索「xxx」，命中 N 条」，N 来自 `matched`
6. 搜索无结果 → 用 `EmptyBlock`，文案「没有匹配的题目」，带「清除搜索」按钮

### ★★ 最关键的一条：不许本地过滤

**绝对不要**这么写：

```ts
// ❌ 禁止：这只搜当前页，而且数据不是来自后端
const filtered = data.items.filter(q => q.content.includes(keyword))
```

必须走 `?q=` 参数。理由：
- 本地过滤只能搜到当前页的 10 条，用户以为搜了全部
- 指导老师硬性要求「页面上的每个数字都必须由后端从真实数据实时算出」

### 分页要改用 `matched`

你现在分页用的是 `splitTotalOf(data.splits, split)`。加了搜索之后这个数就不对了——
`splits` 是全量统计，不随 `q` 变化。

```ts
// ❌ 改之前
const currentTotal = data ? splitTotalOf(data.splits, split) : 0

// ✅ 改之后：优先用 matched，没有则回退（兼容后端未升级的情况）
const currentTotal = data ? (data.matched ?? splitTotalOf(data.splits, split)) : 0
```

`src/api/types.ts` 里加：

```ts
export interface QuestionPage {
  total: number
  splits: SplitCounts
  /** 当前 split + 关键词过滤后的条数；后端未升级时为 undefined */
  matched?: number
  items: Question[]
}
```

### 后端没升级时要能降级（不能假装搜到了）

如果 `matched` 是 `undefined`，说明后端还没改，`q` 参数会被忽略、返回全量结果。
这时候如果照常显示，用户会以为「搜到了 200 条」——**这是假数据**。

```ts
const searchReady = data !== undefined && typeof data.matched === 'number'
```

- `searchReady === false` → 搜索框 `disabled`，旁边显示「后端未支持搜索」
- `searchReady === true` → 正常可用

---

## 四、验收标准

改完自己验，五条都要过：

| # | 验收 | 怎么验 |
|---|---|---|
| 1 | 删除后计数立刻变 | 删一条，统计卡数字减 1，列表少一行，**不刷新页面** |
| 2 | 删最后一条能自动回上一页 | 翻到末页删光，自动跳回前一页，不能停在空白页 |
| 3 | 搜索只发一次请求 | 敲「lora」4 个字母，Network 面板里只应有 1 次 `?q=lora` 请求 |
| 4 | 搜索能跨页 | 搜一个在第二页才出现的词，能搜到（证明不是本地过滤） |
| 5 | 后端停掉不显示假数据 | 停后端，点搜索/删除，必须报错，不能显示旧结果 |

第 4 条是**专门用来抓「本地过滤」的**。如果搜不到第二页的内容，说明你用了 `items.filter`。

---

## 五、不要做的事

| ❌ 不要 | 原因 |
|---|---|
| 用 `items.filter()` 本地搜索 | 只搜当前页 + 违反铁律 |
| 重写现有三页 | 已经验收通过，别动 |
| 加前端缓存 / 本地状态持久化题目 | 每个数字必须来自当次请求 |
| 删除后调 `/stats` 再查一次 | 删除接口已经返回最新 `splits`，多余请求 |
| 把「发起评测」等未接入按钮打开 | 后端还没有，必须保持置灰 |

---

## 六、改完怎么交付

1. 在 `D:\llmloop\web` 里改，`npm run build` 必须零错误
2. 把上面五条验收的实际结果贴回来（第 4 条要说明「搜到了第二页的内容」）
3. 契约有疑问先问，别自己改字段名
