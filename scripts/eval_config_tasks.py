"""配置生成任务评测：给一句需求，让被测助手写 LlamaFactory 训练配置，比对关键参数。

任务书阶段 2 要求「配置生成任务 100 个」，这是第一批 6 个样板（data/config_tasks.json）。

判分只看 key_params（必须正确的几项），不要求整份 yaml 逐字一致——
batch_size、save_steps 这类参数本来就该按显存和习惯调，不该算错。

用法：
    python scripts/eval_config_tasks.py                  # 跑全部
    python scripts/eval_config_tasks.py --limit 2        # 只跑前 2 个
    python scripts/eval_config_tasks.py --model glm-4-flash
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.llm import ask  # noqa: E402

DATA = ROOT / "data"

_index = None


def get_index():
    """BM25 索引，只建一次。"""
    global _index
    if _index is None:
        from rank_bm25 import BM25Okapi

        from lib.text import tokenize

        chunks = [json.loads(l) for l in
                  (DATA / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        _index = (chunks, BM25Okapi([tokenize(c["text"]) for c in chunks]))
    return _index


def retrieve(requirement: str, k: int = 4) -> str:
    """按需求检索文档块，拼成上下文。

    query 里额外加了「template 模板」——实测纯需求检索时，模板对应关系排不进前 3，
    而 template 恰好是模型最容易答错的一项。
    """
    from lib.text import tokenize

    chunks, bm25 = get_index()
    scores = bm25.get_scores(tokenize(requirement + " template 模板 对应关系"))
    top = sorted(range(len(scores)), key=lambda j: -scores[j])[:k]
    return "\n\n".join(f"[文档{i + 1}] {chunks[j]['text'][:700]}" for i, j in enumerate(top))

PROMPT = """/no_think
你是 LlamaFactory 配置助手。根据用户需求，写一份完整的训练配置（yaml 格式）。

**必须使用下面示例里的参数名**，不要自己发明（比如不要写 train_type / lora_r / train_data）。

【参数名示例（LoRA 指令微调）】
model_name_or_path: meta-llama/Meta-Llama-3-8B-Instruct
trust_remote_code: true
stage: sft
do_train: true
finetuning_type: lora
lora_rank: 8
lora_target: all
dataset: identity,alpaca_en_demo
template: llama3
cutoff_len: 2048
output_dir: saves/llama3-8b/lora/sft
per_device_train_batch_size: 1
gradient_accumulation_steps: 8
learning_rate: 1.0e-4
num_train_epochs: 3.0
lr_scheduler_type: cosine
warmup_ratio: 0.1
bf16: true

【补充：不同训练阶段的差异】
- 全参微调：finetuning_type 写 full，learning_rate 用 1.0e-5
- DPO：stage 写 dpo，额外加 pref_beta: 0.1、pref_loss: sigmoid
- 奖励模型：stage 写 rm
- KTO：stage 写 kto
- 量化模型：model_name_or_path 直接写量化模型名，其余同 LoRA

要求：
1. 只输出 yaml 内容，不要解释、不要 markdown 代码块
2. 需求里提到的模型、数据集、训练方式都要体现在配置里
{extra}
用户需求：{requirement}

yaml 配置："""

RAG_HINT = """3. 优先采用【相关文档】里写的参数名和取值
4. template 要按文档里的模型与模板对应关系来填

【相关文档】
{ctx}
"""


def strip_fence(s: str) -> str:
    """去掉模型可能加的 ```yaml 代码块标记。"""
    s = s.strip()
    s = re.sub(r"^```(?:yaml|yml)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def parse_yaml_loose(text: str) -> dict[str, str]:
    """宽松解析 yaml：只抓 `key: value` 行，不依赖 yaml 库（模型输出常常不规范）。"""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        # 去掉行尾注释
        v = re.split(r"\s+#", v, maxsplit=1)[0].strip()
        v = v.strip("'\"")
        out[k] = v
    return out


def norm(v: str) -> str:
    """比对用的归一化：小写、去空格、数字统一、数据集顺序无关。"""
    v = str(v).strip().strip("'\"").lower().replace(" ", "")
    # 1.0e-5 / 1e-5 / 0.00001 视为同一个数
    try:
        f = float(v)
        return f"{f:.10g}"
    except ValueError:
        pass
    if "," in v:
        return ",".join(sorted(x for x in v.split(",") if x))
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="qwen3-4b-local")
    ap.add_argument("--num-predict", type=int, default=900)
    ap.add_argument("--show", action="store_true", help="打印生成的 yaml")
    ap.add_argument("--rag", action="store_true", help="先检索文档再生成（对比纯模型记忆）")
    a = ap.parse_args()

    tasks = json.loads((DATA / "config_tasks.json").read_text(encoding="utf-8"))["tasks"]
    if a.limit:
        tasks = tasks[: a.limit]

    print(f"配置任务 {len(tasks)} 个，模型 {a.model}，"
          f"{'检索增强' if a.rag else '纯模型记忆'}")
    print()

    total_hit = total_key = 0
    passed = 0
    rows = []

    for t in tasks:
        t0 = time.time()
        try:
            extra = ""
            if a.rag:
                extra = RAG_HINT.format(ctx=retrieve(t["requirement"]))
            raw, _ = ask(a.model, PROMPT.format(requirement=t["requirement"], extra=extra),
                         num_predict=a.num_predict)
        except Exception as e:  # noqa: BLE001
            print(f"[{t['id']}] 调用失败 {type(e).__name__}: {e}")
            rows.append({"id": t["id"], "score": 0.0, "error": str(e)[:100]})
            continue
        dt = time.time() - t0

        yaml_text = strip_fence(raw)
        got = parse_yaml_loose(yaml_text)
        want = t["key_params"]

        hit, miss = [], []
        for k, v in want.items():
            if k in got and norm(got[k]) == norm(v):
                hit.append(k)
            else:
                miss.append(f"{k}={got.get(k, '(缺)')}≠{v}")

        score = len(hit) / len(want)
        total_hit += len(hit)
        total_key += len(want)
        if score == 1.0:
            passed += 1

        mark = "✓" if score == 1.0 else ("~" if score >= 0.6 else "✗")
        print(f"{mark} [{t['id']}] {t['title']:<14} {len(hit)}/{len(want)}  ({dt:.1f}s)")
        if miss:
            print(f"     缺：{'；'.join(miss[:3])}")
        if a.show:
            print("     " + yaml_text.replace("\n", "\n     ")[:600])
        rows.append({"id": t["id"], "score": score, "hit": hit, "miss": miss})

    print()
    print("=" * 56)
    print(f"全对 {passed}/{len(tasks)}　参数命中 {total_hit}/{total_key} = "
          f"{total_hit / total_key:.1%}" if total_key else "无数据")
    print("=" * 56)

    out = ROOT / "out" / f"config_tasks_{time.strftime('%m%d_%H%M')}.json"
    out.write_text(json.dumps({"model": a.model, "rows": rows}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"已写出：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
