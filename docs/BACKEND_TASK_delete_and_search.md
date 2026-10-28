# 后端任务：补两个接口（单题删除 + 题目搜索）

> 给负责后端的人。改动很小，但**契约必须严格照这份文档**——前端已按这个契约在写，任何字段名或语义变动都会导致联调失败。

---

## 一、背景

项目：大模型应用自动调优平台。后端在 `~/llmloop/server/`，FastAPI + SQLite，
已有 12 个接口（认证 / 应用 / 题目导入与查询），**全部已测通，不要动它们的行为**。

现在前端已经做完了「登录 / 应用接入 / 测试集管理」三页。但题库要从 60 道扩到 200 道，
两个能力缺失会很难受：

1. **不能删单题** —— 现在只能按 split 整组清空，一条题写错就要清空整组重导
2. **不能搜索** —— 200 道题分页翻找，效率极低

**你只需要补这两个，别的都不要碰。**

---

## 二、改动 1：删除单题

### 接口

```
DELETE /apps/{app_id}/questions/{question_id}
Authorization: Bearer <token>
```

### 返回（200）

```json
{
  "deleted": 123,
  "splits": { "optimize": 120, "valid": 40, "test": 40, "total": 200 }
}
```

**`splits` 必须返回删除后的最新计数**——前端拿到就能直接刷新统计卡，不用再发一次请求。

### 错误

| 情况 | 状态码 | detail |
|---|---|---|
| 未登录 / token 失效 | 401 | 沿用现有 `current_user` 依赖 |
| 应用不存在，或不属于当前用户 | 404 | `"app not found"` |
| 题目不存在，或不属于该应用 | 404 | `"question not found"` |

**注意**：必须同时校验「应用属于该用户」和「题目属于该应用」。
不能只查 question_id，否则 A 用户能删 B 用户的题（越权）。

### 实现位置

`server/questions.py`，在 `clear_questions` 附近新增一个路由。

```python
@router.delete("/{question_id}")
def delete_question(app_id: int, question_id: int, user: dict = Depends(current_user)):
    _app_or_404(app_id, user["id"])
    if not execute(
        "SELECT 1 FROM questions WHERE id=? AND app_id=?", (question_id, app_id), True
    ):
        raise HTTPException(404, "question not found")
    execute("DELETE FROM questions WHERE id=?", (question_id,))
    return {"deleted": question_id, "splits": _counts(app_id)}
```

⚠️ **路由顺序有坑**：`@router.get("")` 和 `@router.delete("")` 已经存在，
新增的 `@router.delete("/{question_id}")` 要放在它们**之后**，
且注意 `/{question_id}` 不能和 `/stats`、`/import` 冲突（这两个是 GET/POST，不冲突）。

---

## 三、改动 2：题目搜索

### 接口

```
GET /apps/{app_id}/questions?split=&q=&limit=50&offset=0
```

新增可选参数 `q`：**关键词**，对 `content` 和 `reference` 两个字段做
**不区分大小写的子串匹配**。

### 返回（200）—— 注意新增字段

```json
{
  "total": 200,                                   // 【语义不变】该应用全部题数，不受 split 和 q 影响
  "splits": {"optimize":120,"valid":40,"test":40,"total":200},   // 【语义不变】全量分类计数
  "matched": 7,                                   // 【新增】当前 split + q 过滤后的条数
  "items": [ ... ]
}
```

**`matched` 是这次唯一新增的字段，前端分页要用它。**

为什么不能复用 `total`：`total` 现在的语义是「这个应用一共多少题」，统计卡要用它；
如果搜索时把它改成「搜到几条」，统计卡就会显示错误数字。所以**新增一个字段，不动老的**。

### 过滤逻辑

```sql
WHERE app_id = ?
  AND (? = '' OR split = ?)                     -- split 为空表示不过滤
  AND (? = '' OR lower(content) LIKE ? ESCAPE '\'
              OR lower(reference) LIKE ? ESCAPE '\')
```

⚠️ **必须转义 `%` 和 `_`**，否则用户搜 `%` 会匹配全部、搜 `_` 会匹配任意单字：

```python
def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

kw = f"%{_escape_like(q.strip().lower())}%"
```

`limit` / `offset` 的行为不变（`limit` 1–200，`offset` ≥ 0），`q` 和 `split` 可以叠加。

---

## 四、验收标准（我会按这个检查）

改完自己跑一遍，四条都要过：

```bash
cd ~/llmloop
.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8020
```

**① 删单题 + 计数正确**

```bash
TOKEN=$(curl -s -X POST localhost:8020/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"tester@llmloop.dev","password":"pw12345678"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# 先看有哪些题
curl -s "localhost:8020/apps/1/questions?limit=3" -H "Authorization: Bearer $TOKEN"

# 删掉第一条（把 <id> 换成上面返回的真实 id）
curl -s -X DELETE "localhost:8020/apps/1/questions/<id>" -H "Authorization: Bearer $TOKEN"
# 期望：{"deleted":<id>,"splits":{...}}，total 比删之前少 1
```

**② 越权必须挡住**

用 `other@llmloop.dev`（密码同上）的 token 去删 `tester` 应用下的题，**必须 404**，不能删成功。

**③ 搜索正确**

```bash
curl -s "localhost:8020/apps/1/questions?q=lora" -H "Authorization: Bearer $TOKEN"
# 期望：matched <= total，items 里每条都含 lora（content 或 reference）
```

**④ 老接口没被改坏**

```bash
curl -s "localhost:8020/apps/1/questions" -H "Authorization: Bearer $TOKEN"
# 期望：仍然返回 total / splits / items，且 total 等于全部题数
```

---

## 五、不要做的事

| ❌ 不要 | 原因 |
|---|---|
| 改 `total` 或 `splits` 的语义 | 前端统计卡和已有 12 个接口都依赖它们 |
| 删接口只按 question_id 查、不校验 app_id 和 user_id | 越权漏洞 |
| 搜索用 `LIKE` 不转义 `%` `_` | 搜 `%` 会返回全部 |
| 顺手「优化」别的接口 | 已经测过了，改动风险大于收益 |
| 加缓存 | 页面上每个数字必须来自当次请求（指导老师硬要求） |

---

## 六、改完怎么交付

1. 在 `~/llmloop` 里提交，commit message 写清楚改了什么
2. 把上面「四、验收标准」四条的实际输出贴回来
3. 如果哪条做不到或想改契约，**先说，别自己改**——前端按这份文档在写
