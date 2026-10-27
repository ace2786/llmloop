# F2 复现计划：tinyBenchmarks

> 任务书要求：跑通 tinyBenchmarks 教程，复算 MMLU 上 100 道代表题的估计误差，和论文对比。
> 开始时间：2026-10-27 18:00
> 论文：Maia Polo et al., "tinyBenchmarks: evaluating LLMs with fewer examples" (arXiv:2402.14992)

---

## 一、论文基线（要对比的数字）

| 方法 | MMLU 平均估计误差 |
|---|---|
| IRT | **2.4%**（标准差 1.7%） |
| p-IRT | **1.6%**（标准差 1.5%） |
| gp-IRT | **1.6%**（标准差 1.5%） |

**复现目标：用 100 道代表题，估计误差接近上述数字。**

---

## 二、核心原理（一句话）

用项目反应理论（IRT）挑出 100 道"代表题"，只用这 100 题的成绩，
就能估计出模型在完整测试集（14000+ 题）上的成绩。

**这让「每一轮评测」的成本降低两个数量级。**

---

## 三、执行步骤

### ① 安装包

```bash
# 官方方式（需要 GitHub，国内不通）
pip install git+https://github.com/felipemaiapolo/tinyBenchmarks

# 实际用的方式（API 下载 zip → 本地安装）
# 见下方「踩坑记录」第 1 条
uv pip install --python .venv/bin/python /tmp/tb/felipemaiapolo-tinyBenchmarks-xxxx
```

### ② 准备数据文件

```bash
# 官方方式：evaluate() 会自动从 raw.githubusercontent.com 下载
# 实际方式：pkl 已在源码包里，复制到工作目录即可
cp /tmp/tb/*/tinyBenchmarks/tinyBenchmarks.pkl ~/llmloop/
```

### ③ 核心调用

```python
import numpy as np
import tinyBenchmarks as tb

y = np.array([...])  # 100 个 0/1，表示模型在 100 道代表题上的对错
print(tb.evaluate(y, "mmlu"))
# {'mmlu': {'irt': 0.xxx, 'pirt': 0.xxx, 'gpirt': 0.xxx}}
```

### ④ 复算误差

```
误差 = |估计成绩 - 真实全量成绩|
对多个模型各算一次，取平均值和标准差
```

**需要的数据**：一批模型在 MMLU 100 道代表题上的对错向量（y），
以及它们在完整 MMLU 上的真实成绩。

**数据来源**：`huggingface.co/tinyBenchmarks/tinyMMLU`（用 hf-mirror.com 镜像下载）

---

## 四、踩坑记录（网络受限环境）

### 坑 1：GitHub 直连不通

```
症状：git clone 报 GnuTLS recv error (-110)
原因：github.com:443 被阻断（api.github.com 通）
解决：用 GitHub API 下载 zipball
```

```powershell
# PowerShell 里执行（WSL 取不到 gh token）
$token = gh auth token
Invoke-WebRequest -Uri "https://api.github.com/repos/felipemaiapolo/tinyBenchmarks/zipball/main" `
  -Headers @{ Authorization = "Bearer $token"; "User-Agent" = "gh-cli" } `
  -OutFile "D:\llmloop\tb.zip"
```

### 坑 2：仓库名拼错

```
错误：felixjoseph/tinyBenchmarks（404）
正确：felipemaiapolo/tinyBenchmarks
```

### 坑 3：evaluate() 自动下载被墙

```
症状：ConnectionResetError(104)
原因：从 raw.githubusercontent.com 下载 tinyBenchmarks.pkl
解决：pkl 就在源码包里（5MB），复制到工作目录即可跳过下载
```

### 坑 4：HuggingFace 直连不通

```
症状：curl https://huggingface.co 无响应
解决：用镜像 https://hf-mirror.com（实测通）
```

### 坑 5：读 parquet 要装大包，网络慢

```
pyarrow：51MB，下载 4 分钟未完成
duckdb：23MB，仍在下载
备选：polars（约 30MB）
```

---

## 五、当前进度

| 步骤 | 状态 |
|---|---|
| 源码包下载 | ✅ 21 MB |
| 包安装 | ✅ tinybenchmarks 1.0.0 |
| pkl 数据文件 | ✅ 5 MB（从源码包复制） |
| 核心函数跑通 | ✅ 随机数据测试成功 |
| MMLU 数据集下载 | ✅ test 174KB / dev 201KB |
| 读取 parquet | ⏳ 等 duckdb 装完 |
| 复算误差 | ⬜ 待数据可读 |

---

## 六、下一步

1. 装好 duckdb（或 pyarrow），读出 tinyMMLU 的列结构
2. 找到「各模型在 100 道代表题上的对错」这一列
3. 对每个模型调用 `tb.evaluate()`，得到估计成绩
4. 和真实成绩对比，算误差
5. 汇总：平均误差 + 标准差，和论文的 2.4% / 1.6% / 1.6% 对比
