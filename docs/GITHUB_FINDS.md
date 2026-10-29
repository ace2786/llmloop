# GitHub 资源清单（按任务书需求排序）

> 收集时间：2026-10-29
> 原则：**先服务任务书，再谈有意思**。每条都标注「对应任务书哪一条」，对不上的放最后。
> 标注说明：✅ 已实际打开核实；🔍 仅搜索结果，未逐条核实，用前自己看一眼。

---

## 一、直接能用的（对应任务书硬性要求）

### 1. `gepa-ai/gepa` ✅ 已核实

- **地址**：https://github.com/gepa-ai/gepa
- **规模**：7.2k star，MIT，931 commits
- **对应**：第 8 节 F1（复现 GEPA）

**为什么对你有用**：我们现在用的是 `dspy.GEPA`，但官方仓库有**独立 API** 和**一批现成 Adapter**，其中两个跟你的项目直接相关：

| Adapter | 对你的意义 |
|---|---|
| **Generic RAG** | 向量库无关的 RAG 优化（Chroma/Weaviate/Qdrant/Pinecone）。**你的项目本质就是优化一个 RAG 助手**，阶段 2 可能不用自己造轮子 |
| **MCP Adapter** | 优化 MCP 工具描述与系统提示词。老师要求系统提供 MCP 接口，这个能参考 |
| **DSPy Full Program** | 进化整个 DSPy 程序（MATH 上 67% → 93%） |

**一条重要的纠错**：**MIPROv2 不在这个仓库里**。它是 DSPy 的另一套优化器，GEPA 仓库只在用例里拿它当对比基线。
阶段 2 要补 MIPROv2 对照，得去 `stanfordnlp/dspy` 里找，别在这找。

**安装**：`pip install gepa`

---

### 2. `hiyouga/LLaMA-Factory` 🔍

- **地址**：https://github.com/hiyouga/LLaMA-Factory
- **对应**：第 8 节「场景用你自己的 LlamaFactory 测试集」

**为什么必须看**：你要出 **500 道答案可核对的题**（参数名和默认值、某种微调方法要写哪几项配置、模型对应哪个对话模板）+ **100 个配置生成任务**。这些题的「标准答案」必须来自它的文档和真实配置，翻仓库比翻网页快。

**顺手能拿的**：`examples/` 目录下的 YAML 就是配置生成任务的标准答案来源。

---

### 3. `eribean/girth` 🔍

- **地址**：https://github.com/eribean/girth
- **对应**：第 8 节 F2（IRT）、阶段 2「在 LlamaFactory 对错矩阵上训 IRT」

**为什么对你有用**：纯 Python 的 IRT 参数估计包，支持合成数据生成。
你现在用的是 tinyBenchmarks 打包好的预训练参数，**阶段 2 要自己训**（用你积累的「各版本 × 各题对错」数据），到时候需要这个。

**顺带**：它能生成合成 IRT 数据——可以用来验证你的 IRT 实现对不对，不用等真实数据攒够。

---

## 二、阶段 2/3 会用上的

### 4. `promptfoo/promptfoo` 🔍

- **地址**：https://github.com/promptfoo/promptfoo
- **规模**：21.4k star（2026-03 被 OpenAI 收购，仍开源独立运营）
- **对应**：第 9 节「评测框架」、第 5 节「版本对比页」

**为什么值得看**：它就是「提示词/模型的 A/B 对比 + 断言 + CI 集成」这套东西的成熟实现。
你的「版本对比页」和「回归套件」不用从零设计——看它怎么组织 case、怎么定义断言、怎么出对比报告。

**但别直接接**：你的评测口径是自定义的（RUBRIC.md 那套人工判分），硬套会打架。**只借设计，不借代码。**

---

### 5. `explodinggradients/ragas` / `confident-ai/deepeval` 🔍

- **地址**：https://github.com/explodinggradients/ragas ｜ https://github.com/confident-ai/deepeval
- **对应**：第 8 节 F3（幻觉检测）、阶段 2「幻觉率低于 5% 的守门」

**为什么值得看**：你的 F3 用的是 LettuceDetect（编码器逐词分类），这两个是**用 LLM 当裁判**的路子（faithfulness / hallucination 指标）。

**对你的真实价值**：**做一个对照**。
论文里 LettuceDetect 就是拿 LLM 裁判当基线的。你阶段 2 接进循环做守门时，可以顺手对比「149M 编码器 vs LLM 裁判」的成本和准确率——**这是个现成的、能写进报告的小实验**。

---

### 6. `zou-group/textgrad` 🔍

- **地址**：https://github.com/zou-group/textgrad
- **对应**：第 8 节「你自己设计的组合方式作为第四种」

**为什么有意思**：斯坦福的「文本梯度」——把 LLM 的文字反馈当梯度反传，优化复合系统。
它和 GEPA 是同一时期、同一批人脉圈子的两条路（GEPA 反思提示词，TextGrad 反传文本梯度）。

**对你的意义**：如果阶段 3 要设计「第四种组合模式」，这是现成的第二个参照系。不用实现，但**知道有这条路，写报告时能显得你不是只读了一篇论文**。

---

## 三、有意思但跟项目没直接关系的

### 7. GEPA 的生产落地数据 ✅（来自官方 README）

不是仓库，是几个数字，但对你写报告有用：

- **90x 更便宜**：开源模型 + GEPA 在 Databricks 上超过 Claude Opus 4.1
- **比 RL 快 35x**：100–500 次评估 vs GRPO 的 5,000–25,000+
- **50+ 生产用例**：Shopify、Databricks、Dropbox、OpenAI、Pydantic、MLflow

**为什么有用**：你的 F1 复现只跑了 50 次 rollout 就被说「预算差 48 倍」。这些数字能支撑一个论点——**GEPA 的设计目标本来就是「少次数出效果」**，50 次不是敷衍，是它的适用区间。写报告时可以用。

> Tobi Lutke（Shopify CEO）原话："Both DSPy and (especially) GEPA are currently severely under hyped"

---

## 四、明确不要碰的

| 东西 | 为什么不要碰 |
|---|---|
| 各种「一键优化 Prompt」的 SaaS | 老师要「页面每个数字来自后端实时算出」，接外部服务等于把核心逻辑外包 |
| Agent 框架（LangChain/LangGraph 全家桶） | 你的循环是自己设计的，套框架反而讲不清原理 |
| 任何「自动刷分」工具 | 跟「真实数据」铁律直接冲突 |

---

## 五、我建议的动作顺序

| 优先级 | 做什么 | 什么时候 |
|---|---|---|
| **P0** | 翻 `hiyouga/LLaMA-Factory` 的 `examples/`，把配置生成任务的标准答案找出来 | **本周**（题库要用） |
| P1 | 读 `gepa-ai/gepa` 的 Generic RAG adapter | 阶段 2 开始前 |
| P2 | 看 promptfoo 的 case 组织方式，改你的回归套件设计 | 阶段 2 中期 |
| P3 | TextGrad、Ragas/DeepEval 对照实验 | 阶段 3 |

**注意**：除了第 1 条，其余都别现在动。**题库还没做完。**

---

## 六、核实状态说明

- ✅ **已实际打开核实**：`gepa-ai/gepa`（含 star 数、Adapter 列表、安装方式、与 DSPy 的关系）
- 🔍 **仅搜索结果**：其余仓库的 star 数和细节来自搜索摘要，**用之前自己打开看一眼**，别拿我这行字当事实
- 所有链接均为公开仓库，无付费/闭源内容
