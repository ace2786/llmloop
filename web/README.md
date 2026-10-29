# LLMLoop 前端（web）

大模型应用自动调优平台的前端。技术栈 **Vite + React 18 + TypeScript**，无第三方 UI 库、无 CDN 依赖。

当前只实现了交接书里的 **A 区接口**能支撑的三个页面，B 区功能按钮一律置灰并标注「功能未接入」。

---

## 跑起来

```bash
cd web
npm install
npm run dev
# → http://127.0.0.1:5173
```

后端默认按 `http://127.0.0.1:8020` 联调。要换地址，在 `web/` 下建 `.env.local`：

```
VITE_API_BASE=http://127.0.0.1:8020
```

其它脚本：

| 命令 | 作用 |
|---|---|
| `npm run dev` | 本地开发服务器 |
| `npm run build` | 类型检查 + 生产构建到 `dist/` |
| `npm run typecheck` | 只跑 `tsc --noEmit` |
| `npm run preview` | 预览 `dist/` |

联调账号：`tester@llmloop.dev` / `pw12345678`

---

## 三个页面

### 1. 登录 / 注册
`#/login` —— 调 `/auth/login`、`/auth/register`。

- token 存 `localStorage`，键名 `llmloop.token`
- 启动时用 `GET /auth/me` 校验 token，不拿过期 token 冒充已登录
- 任意请求返回 `401` → 清 token → 自动回登录页并提示「登录已失效」
- 错误码映射：`400` 密码不足 8 位 / `409` 邮箱已注册 / `401` 邮箱或密码不正确

### 2. 应用接入
`#/apps` —— 调 `GET /apps`、`POST /apps`、`DELETE /apps/{id}`。

- 列表里每个应用展示 `optimize / valid / test / total` 四个计数，全部来自 `GET /apps`
- `app_key` 默认打码，可「显示」和「复制」（复制失败会回退到 `execCommand`）
- 新建表单：`name`（必填，≤64 字）/ `base_url` / `model` / `description`
- 删除带二次确认，弹窗里写明会级联删掉多少道题
- 「发起评测」「优化循环」置灰 + `功能未接入`

### 3. 测试集管理
`#/apps/:id/questions` —— 调 `/apps/{id}/questions*` 全部 4 个接口。

- **粘贴导入**：一行一道题，同一行用 `Tab` 隔开的第二段当作 `reference`。
  前端解析成 `items: [{content, reference}]` 提交（后端 `raw_text` 只按换行切、不认 Tab，所以这层解析放在前端）
- 导入后展示后端返回的 `{imported, seed, splits}`，并用堆叠条显示实际切分比例
- `seed` 可填可不填，留空由后端生成；返回的 seed 会显示出来，便于复现同一种切分
- `replace` 默认勾选（后端默认就是 `true`，会覆盖原有题目），UI 上有明确警告
- 分类标签页：全部 / 优化集 / 验证集 / 测试集，计数取 `splits[split]`
- 分页：`limit`（10/20/50）+ `offset`，直接透传给后端
- 按分类清空：`DELETE /apps/{id}/questions?split=xxx`，二次确认里写明要删几道
- **删单题**：每行末尾「删除」→ 二次确认 → `DELETE /apps/{id}/questions/{qid}`。
  统计卡直接用接口返回的 `splits` 刷新，**不再多发一次 `/stats`**；删掉本页最后一条会自动回上一页
- **搜索**：输入框防抖 300ms，走 `?q=` 交给后端过滤，和 `split`/`limit`/`offset` 叠加；
  列表上方显示「搜索「x」，命中 N 条」，N 取 `matched`
- 「回答检查」置灰 + `功能未接入`

---

## 关于「不许造假」这条

页面上的每一个数字都来自当次 HTTP 请求，没有 Mock、没有硬编码、没有本地缓存。

- 请求中 → 骨架屏
- 请求失败 → 错误块 + 重试按钮，同时把已有数据置空（不会残留上一次的数字）
- 数量为 0 → 空状态，而不是显示一排 0 装作正常

唯一的客户端计算是切分比例的百分比（`12 / 20 → 60%`），分子分母都是后端返回的 `splits`，
不是写死的常量。

**验证方式**：把后端停掉，列表页会显示「拿不到应用列表」并提示连不上 8020；
整页刷新会停在「连不上后端」的全屏状态；直接打开深链也一样。页面上不会剩下任何数字。

---

## 目录

```
web/
├── index.html
├── vite.config.ts
├── tsconfig.json
└── src/
    ├── main.tsx
    ├── App.tsx              # 外壳：顶栏 + hash 路由分发 + 全屏状态
    ├── auth.tsx             # token / me / 登录注册登出
    ├── router.ts            # 30 行 hash 路由，没引 react-router
    ├── styles.css           # 全部样式，含 1920 与 390 两个断点
    ├── api/
    │   ├── client.ts        # fetch 封装：NetworkError / ApiError / 401 广播
    │   ├── index.ts         # 语义化接口（authApi / appsApi / questionsApi）
    │   └── types.ts         # 与 openapi.json 逐字段核对过的类型
    ├── components/
    │   ├── ConfirmDialog.tsx
    │   └── Feedback.tsx     # 骨架屏 / 错误块 / 空状态 / 提示条
    └── pages/
        ├── LoginPage.tsx
        ├── AppsPage.tsx
        └── QuestionsPage.tsx
```

---

## 已联调验证的接口行为

按 `http://127.0.0.1:8020/openapi.json` 和真实响应核对过，几个和文档表述容易踩坑的点：

1. `GET /apps/{id}/questions` 返回的 `total` 是**全量题数**，不随 `split` 和 `q` 过滤。
   某一分类的题数要看 `splits[split]`，分页总数要用 `matched`。
2. `limit` 合法区间是 `1~200`，越界返回 `422`。
3. `POST .../import` 的 `replace` 默认 `true`（覆盖），`seed` 不传则后端随机生成。
4. `raw_text` 只按换行切分并去空行，**不解析 Tab 分隔的出处**；`items` 形式才支持 `{content, reference}`。
5. `DELETE .../questions` 不带 `split` 时清空全部。
6. 越权访问别人的应用返回 `404`（不是 403）。
7. `DELETE .../questions/{qid}` 返回 `{deleted, splits}`，`splits` 是删除后的最新计数；
   重复删同一题返回 `404 question not found`。
8. `q` 对 `content` 和 `reference` 做**不区分大小写**的子串匹配，`%` / `_` 已在后端转义。

### 搜索的降级

`matched` 是后端新增字段。如果响应里**没有** `matched`（后端未升级），说明 `q` 会被忽略、
返回的是全量结果 —— 此时搜索框会被禁用并提示「后端未支持搜索」，绝不会拿 `total` 冒充命中数。

## 没做的（B 区，后端未排期）

评测、优化循环、回答检查、版本对比。对应按钮已置灰标注「功能未接入」，没有用假数据占位。
