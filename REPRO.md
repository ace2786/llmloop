# REPRO.md — 可行性五关与本机配置

> 按老师第 9 节要求：写在开头。所有配置数字均为本机实测，不是估计值。

---

## 一、可行性五关

### 关卡 1｜起点：基础好，这个方向正好接着上一个项目往下做

**评级：优**

- 上一个项目已经做过 GUI / CLI / MCP 共用内核、观测面板和本地大模型调用，提交过程清楚，可直接复用到评测平台；
- 三个复现都有现成代码和数据：GEPA 有 DSPy 官方教程，tinyBenchmarks 有教程和数据，LettuceDetect 有训练和评测脚本。第一步都是「下载 → 运行 → 和论文对比」；
- 本机已具备可用 GPU 环境（见第三节），不需要从零配环境。

**风险**：无。

---

### 关卡 2｜数据：复现数据充足，场景数据靠自己做

**评级：中（这是全项目工作量最大的部分）**

| 数据 | 规模 | 状态 |
|---|---|---|
| LlamaFactory 中文文档 | 37 个 md / 94 KB + README_zh 69 KB | ✅ 已下载 |
| 示例配置 | 97 个 yaml | ✅ 已下载 |
| LlamaFactory Issues | 已拉 2000 条（2023-06 ~ 2026-10） | ✅ 已下载 |
| 第 1 周 60 道题 | 候选 120 条已筛出，待人工核对 | 🟡 |
| 阶段 2：测试集 500 道 + 配置任务 100 个 | — | ⬜ |
| 阶段 2：幻觉标注 600 条（含 100 条他人复标） | — | ⬜ |

**已验证的问题**：
- GitHub Issues 接口未登录限额 60 次/小时，单次查询最多返回 1000 条（第 11 页起返回 422）。已通过 `since` 参数分窗口拉到 2000 条；
- 从 Issues 里筛「用法类提问」且「答案能在文档里找到」的比例约为 **30-50%**（2000 条 → 264 条通过初筛 → 120 条进入人工核对）。这意味着凑 60 道可用题需要扫 150-250 条候选；
- BM25 只能测词面重合，**无法自动判断「这段文档是否回答了问题」**，这一步必须人工，对应第 8.1 ⑤「人工确认答案能在文档或示例配置里找到」。

---

### 关卡 3｜参考项目

**评级：良**

- 课程案例：多智能体 + FastAPI 骨架、调用追踪，需要时可向王老师索取；
- 公开可参考的开源评测平台（都是「评测」，不含自动优化闭环，这正是本项目的差异点）：
  - promptfoo（断言类型 / LLM-as-Judge / 矩阵视图 / CI 集成）
  - Agenta（prompt playground + 评测 + 观测一体）
  - lm-evaluation-harness、HELM（评测框架规范）
  - PromptPex（微软，软件工程方法自动测试 prompt）
- 三个复现的一手资料：DSPy GEPA 教程、tinyBenchmarks 仓库 tutorial、LettuceDetect 仓库与模型卡。

---

### 关卡 4｜硬件

**评级：够用（有明确边界）**

- RTX 5060 Laptop，8 GB 显存。F3 训练、本机开源模型都在本机跑；F2 只要 CPU；被测助手和 F1 调免费大模型接口或本机模型；
- **不用租卡，不花钱**；
- 16 GB 内存同时跑本机大模型和训练会比较紧，两者错开运行；
- 已知边界：8B 模型 Q4 量化 + 8k 上下文会塞满 8 GB 显存，超了就退到 CPU 推理，速度会掉一个数量级。第 1 周先用 4B 级模型。

**已实测的关键约束**：
- Ollama 在本机启动后 GPU 占用 5148 MiB / 8151 MiB，利用率 81%，4B 模型生成速度约 71 token/s；
- 下载源速度差异极大（见第二节「踩过的坑」），已确认 ModelScope 可用。

---

### 关卡 5｜许可

**评级：合规**

| 组件 | 许可 |
|---|---|
| GEPA | MIT |
| DSPy | MIT |
| tinyBenchmarks | MIT |
| LettuceDetect | MIT |
| RAGTruth | MIT |
| LlamaFactory | Apache-2.0 |
| PUPA | 按数据集说明（论文研究用途） |
| Qwen3-4B | Apache-2.0 |

已在 README 中逐个写明。

---

## 二、踩过的坑（已解决，记录下来避免重犯）

### 1. GitHub 连通性：不是完全不通，是首次握手慢

- `github.com` 首次 TLS 握手约 **4.2 秒**，用 8 秒超时测会误判为不通；
- `git clone` 实测**可用**；
- **`raw.githubusercontent.com` 确实不通**（000），只影响「直接 curl raw 文件」，不影响 git 操作；
- 备选：`codeload.github.com` 可下 tarball，`ghproxy.net` 可代理 raw。

### 2. 模型下载源速度差 24 倍

| 源 | 实测速度 | 结论 |
|---|---|---|
| **ModelScope** `modelscope.cn` | **8.9 MB/s（峰值 19.2 MB/s）** | ✅ 首选 |
| hf-mirror.com | 370-500 KB/s | 慢 |
| registry.ollama.ai（Ollama 官方） | 卡在 2.38 GB 反复重试，100 秒零增长 | ❌ 不可用 |

**结论**：下模型一律走 ModelScope：
`https://modelscope.cn/models/{org}/{repo}/resolve/master/{file}`

### 3. PyPI 镜像

| 源 | 实测 |
|---|---|
| pypi.org | 12 秒（仅索引页） |
| **阿里云** `mirrors.aliyun.com/pypi/simple/` | **4.3 秒** ✅ |
| 清华 | 根路径 403（`/simple/` 可用） |

### 4. 系统 Python 是 3.14，不能用

Ubuntu 26.04 自带 `python3 = 3.14.4`，transformers / dspy 在 3.14 上多数包没有 wheel。
**必须 `uv venv --python 3.12`**（uv 已缓存 cpython-3.12.14）。

### 5. F3 阶段要钉 `transformers<5`

`lettucedect-210m-eurobert-cn-v1` 模型卡明确写：EuroBERT remote code 与 transformers 5.x 不兼容，需 `transformers>=4.48.3,<5`。
实测该约束可解析到 **transformers 4.57.6**。
**F3 必须独立 venv**，与 F1 的 dspy 环境隔离。

### 6. BM25 索引容易被长文档污染

初版收录全部 `docs/zh`，结果 `multi-backend/npu/index.md`（NPU 安装文档）给几乎所有查询打分；示例配置里的 `fsdp_config_multiple_nodes.yaml` 同样污染。
**改法**：白名单只收「用法文档」+ 标题/路径命中加权重排。

---

## 三、本机配置（实测）

### 硬件

| 项目 | 实测值 |
|---|---|
| 物理硬盘 | YMTC YMSS2ED08D25MC，SSD / NVMe，953.9 GB（C/D/E 为同一块盘的三个分区） |
| 磁盘可用 | C: 98.7 GB / D: 193.8 GB / E: 49.3 GB |
| CPU 内存 | 15.8 GB 物理 |
| GPU | NVIDIA GeForce RTX 5060 Laptop GPU，8151 MiB 显存 |
| 驱动 | Windows 侧 32.0.15.7324；WSL 内 nvidia-smi 573.24，CUDA 12.8 |
| 计算能力 | sm_120（Blackwell，capability 12.0） |

### 系统与运行时

| 项目 | 实测值 |
|---|---|
| 系统 | Windows 10.0.26100（WSL 内 Ubuntu 26.04.1 LTS） |
| WSL | 版本 2.7.13.0，内核 6.18.33.2-2，WSLg 1.0.73.2 |
| WSL 磁盘位置 | `D:\WSL\Ubuntu\ext4.vhdx`，41.58 GB（已从 C 盘迁出） |
| WSL 资源 | `.wslconfig`：memory=12GB，processors=10，swap=8GB，sparseVhd=true |
| 系统 Python | 3.14.4（**不用**） |
| uv | 0.12.18 |
| uv Python | cpython-3.12.14（`~/.local/share/uv/python/`） |
| git | 2.53.0 |
| Ollama | 0.34.4，用户进程方式启动（`nohup ollama serve`） |
| 本地模型 | `qwen3-4b-local:latest` = Qwen3-4B-Q4_K_M，2.5 GB |

### PyTorch 状态

| 项目 | 实测值 |
|---|---|
| 位置 | `~/comfyvenv`（ComfyUI 环境） |
| 版本 | torch 2.11.0+cu128 |
| CUDA | 12.8，`torch.cuda.is_available() = True` |
| 设备识别 | RTX 5060 Laptop GPU，capability (12, 0) |

> 注意：系统 Python 和各项目 `.venv` 里**没有** torch，只有 `~/comfyvenv` 有。F3 阶段需要单独建环境装 torch。

---

## 四、第 1 周的环境验证结果

| 验证项 | 结果 |
|---|---|
| uv 建 Python 3.12 venv | ✅ 3.12.14 |
| `rank_bm25` + `jieba` 安装 | ✅ jieba 0.42.1 |
| Ollama 服务 + GPU 识别 | ✅ CUDA0 / compute 12.0 / 8 GiB |
| 本地模型推理 | ✅ 71 token/s，0.26s 出答案 |
| 模型抗编造 | ✅ 资料里没有时回答「资料里没有找到」 |
| `week1.py` 端到端 | ✅ 3 题 × 1 模型，CSV 15 列 |
| 测试集锁定 | ✅ `--split optimize` 时不读 test |
| 文档索引 | ✅ 187 块（112 文档 + 75 示例配置） |
| 真实提问抓取 | ✅ 2000 条 Issue |
