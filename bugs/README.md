# Bug 数据库

> 目标不是「记下这个 bug 怎么修的」，而是**让同类 bug 下次在合并前被拦住**。

---

## 一条 bug 的完整链路

老师给的标准链路，本目录就是按它组织的：

```
bug 出现
  → 留 trace（输入、每步工具调用、输出）      ← 靠当时的日志/命令，别事后编
  → 读 trace 找「最早哪一步开始歪」
  → 抽出最小复现（只留必要输入）              ← minimal_repro 字段
  → 写成一条 eval case（含负样本）            ← eval_case + negative_case 字段
  → 进回归套件                               ← scripts/bug.py export
  → CI 闸门（不过不许合并）                   ← precommit_check.py --strict
  → 下次同类 bug 在合并前被拦住
```

**关键在最后两步**：只记录不拦，等于没记。

---

## 目录结构

```
bugs/
  README.md       本文件
  index.jsonl     一条 bug 一行 JSON，用 scripts/bug.py 读写
```

## 字段说明

| 字段 | 含义 | 写不好的后果 |
|---|---|---|
| `id` | `B001` 递增 | — |
| `date` | 第一次出现日期 | 算不了「多久没再犯」 |
| `area` | 子系统（F1/F2/F3/工具链/仓库…） | 没法按模块统计 |
| `title` | 一句话说清是什么错 | 三个月后自己看不懂 |
| `symptom` | **当时看到的现象**（报错原文优先） | 无法检索 |
| `root_cause` | 真正的根因，不是表面原因 | 修了还会再犯 |
| `fix` | 怎么解决的 | — |
| `minimal_repro` | 最少几步能复现 | 没法验证是否真修好 |
| `eval_case` | 以后怎么自动检查「这类错还在不在」 | **没有这条，这条 bug 就白记了** |
| `negative_case` | 什么情况**不该**报错 | 没有负样本的 eval 会误杀 |
| `tags` | 标签，用于筛选 | — |
| `seen_days` | 出现过的日期列表，**长度 ≥ 2 说明重复犯错** | 看不出哪些是真问题 |

---

## 最该看的一个指标：`seen_days` 长度

```bash
python scripts/bug.py stats
```

会列出所有「同一条教训在不同日子出现过」的 bug。

- 长度 1 → 偶发，记录即可
- **长度 2 → 危险信号**，说明第一次没吸取教训
- **长度 3 → 必须升级成硬规则**（写进 `LESSONS.md` 并加进 CI 闸门）

第 14 节的规则原文：「同一条教训在 3 个不同的日子出现就升级成硬规则」。
本库里 **B002/B003 已经是 2 次**——再犯一次就必须机械化拦截。

---

## 日常用法

```bash
# 今天复盘：列出最近 3 天的 bug
python scripts/bug.py list --days 3

# 按模块看
python scripts/bug.py list --area F3

# 统计 + 找重复犯错
python scripts/bug.py stats

# 检查数据格式有没有写坏
python scripts/bug.py check

# 导出成回归套件（给 CI 用）
python scripts/bug.py export > tests/regression_cases.json
```

新增一条：直接在 `index.jsonl` 末尾追加一行 JSON，或

```bash
python scripts/bug.py add --json '{"id":"B009", ...}'
```

---

## 和 CI 闸门怎么接

`scripts/precommit_check.py --strict` 已经有「有 ERROR 返回非 0」的能力。
把 `python scripts/bug.py check` 加进去，格式写坏就拦下来：

```bash
# .git/hooks/pre-commit 里加一行
python scripts/bug.py check || exit 1
python scripts/precommit_check.py --strict || exit 1
```

**注意**：现在的 `check` 只校验格式，还不能自动跑 `eval_case`。
真正的「同类 bug 在合并前被拦住」需要把 `eval_case` 写成可执行断言，
那是下一步（见 `LESSONS.md` 末尾的待办）。
