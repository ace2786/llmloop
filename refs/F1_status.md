# F1 复现进度：GEPA + PUPA（链路已通，尚未跑出提升）

> 时间：2026-10-28 18:38–19:10
> 脚本：`scripts/f1_gepa.py`，启动器 `~/f1/run_f1.sh`
> 数据：`~/f1/data/PUPA_New.csv`（664 条，hf-mirror 下载）

---

## 一、当前状态

| 环节 | 状态 |
|---|---|
| 环境（dspy 3.4.1 + GEPA） | ✅ |
| PUPA 数据下载与解析 | ✅ 664 条，`pii_units` 用 `||` 分隔 |
| 三个模型接通（本地/不可信/反思） | ✅ 全部免费来源 |
| PAPILLON 程序 | ✅ 跑通 |
| LLM 判分 + 泄漏检测指标 | ✅ |
| GEPA 优化 | ⚠️ **跑通但候选被拒，分数无提升** |
| 论文对比 | ⬜ 待正式跑 |

---

## 二、冒烟测试结果（4 train / 2 dev / 4 test）

```
未优化 overall : 0.6375  (quality 0.7750, leakage 0.5000)
GEPA 后 overall: 0.6375  (完全一致)
提升           : +0.00 个百分点
耗时           : 18 分 58 秒
```

**baseline 的 leakage 是 0.50——一半隐私单元原样留在了脱敏请求里。** 这正是 GEPA 该修的地方，方向没错。

---

## 三、GEPA 为什么没提升（已定位）

```
Iteration 0: Base program full valset score: 0.775
Iteration 1: Proposed new text for craft_redacted_request.predict:
             你是一个隐私保护型请求改写器…输出必须是合法 JSON，只包含 reasoning 和 llm_request 两个字段
Iteration 1: New subsample score 1.7 is not better than old score 2.25, skipping
```

**根因：反思模型提出的 prompt 要求「输出合法 JSON」，而 dspy 的 Signature 本身已经把输出包装成 JSON 结构。**
两层套娃导致解析失败，候选分数从 2.25 掉到 1.7，被 GEPA 正确拒绝。

**这不是 bug，是 GEPA 的验证机制在正常工作**——它拒绝了一个坏候选。但说明当前配置下反思模型不知道 dspy 的输出格式约束。

### 三个待调项

| 问题 | 应对 |
|---|---|
| 反思模型不知道 dspy 输出格式 | 在 Signature 的 docstring 里显式写「不要自行要求 JSON 格式」，或换更强的本地模型 |
| dev 只有 2 条，噪声极大（1 条翻转 = 0.5 分） | dev 至少 20 条，train 至少 30 条 |
| 响应被截断（日志多次 `LM response was truncated`） | max_tokens 800 → 1200，PUPA 的 target 长达 3600 字符 |

---

## 四、模型配置（全部免费，无 OpenAI key）

| 角色 | 模型 | 来源 |
|---|---|---|
| 本地（PAPILLON 主程序） | glm-4-flash | 智谱 |
| 不可信大模型 | Qwen2.5-72B-Instruct | 硅基流动 |
| 反思模型（GEPA） | DeepSeek-V4.1-Flash | 硅基流动 |
| 判分 | glm-4-plus | 智谱 |

> **与原教程的关键差异**：教程用 gpt-4.1-nano / mini / 4.1 三档 OpenAI 模型，
> 我们换成了国产免费模型。**因此最终成绩不能直接和论文的 80.82 / 91.85 比较**，
> 只能比较「提升幅度」这个相对量。

---

## 五、成本估算（重要，决定能跑多大）

冒烟 10 条样本（4+2+4）用了 **19 分钟**。按线性外推：

| 规模 | 预计耗时 |
|---|---|
| 30 train / 20 dev / 40 test | 约 1.5–2 小时 |
| 60 train / 30 dev / 60 test | 约 4–6 小时 |

**主要瓶颈是 Qwen2.5-72B 生成长回复（每条 20–50 秒）。**
若要提速：换 glm-4-flash 当不可信模型（快 10 倍，但「大模型」这个设定就没了），
或把 PUPA 的 target_response 截断到 1000 字符。

---

## 六、下一步

1. 修 Signature docstring，避免反思模型提「输出 JSON」这类和 dspy 冲突的指令
2. max_tokens 提到 1200
3. 用 30/20/40 跑一次正式小预算，看 GEPA 能否带来正提升
4. 若仍无提升，检查 `dspy.GEPA` 的 `max_full_evals` 是否需要配合 `auto` 参数
