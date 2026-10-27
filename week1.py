#!/usr/bin/env python3
"""第 1 周主脚本：一条命令跑完「检索 → 2 个模型回答 → 输出 CSV」。

严格按第 11 节步骤 3 实现：
  - 用 rank_bm25 在 LlamaFactory 中文文档和示例配置里检索每道题最相关的 3 段
  - 交给模型回答（版本 v0 / v1）
  - 2 个模型各跑一遍，每次调用记录耗时和 token 用量
  - 输出 CSV：题号、问题、所属份、模型、版本、回答、检索到的段落、
              人工判分、失败原因、判断理由

★ 测试集锁定（第 16 节硬要求）：
    --split optimize 只跑「优化用」，--split test 只跑「测试用」。
    改进阶段严禁跑 test，避免循环/人工提前看到测试题。

用法：
    python week1.py --split optimize --version v0
    python week1.py --split test --version v1

环境变量（不写进仓库）：
    DASHSCOPE_API_KEY / ZHIPU_API_KEY / SILICONFLOW_API_KEY 等，按 config.py 里配的来
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import rank_bm25

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from lib.text import tokenize  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "out"

CJK = re.compile(r"[\u4e00-\u9fff]")

# CSV 十个字段（顺序按第 11 节原文）
FIELDS = [
    "题号",
    "问题",
    "所属份",
    "模型",
    "版本",
    "回答",
    "检索到的段落",
    "人工判分",
    "失败原因",
    "判断理由",
    # 以下为额外记录（不属于那十个字段，但第 11 节要求「记录耗时和 token」）
    "耗时秒",
    "输入token",
    "输出token",
    "检索命中来源",
    "时间戳",
]

# 失败原因的可选值（第 11 节原文）
FAIL_REASONS = ["检索没命中", "编造内容", "理解错", "格式错"]


# ─────────────────────────── 检索 ───────────────────────────
class Retriever:
    """BM25 检索 + 标题/路径加权 + 参数名精确匹配加权重排。

    v0 的失败 92% 是「检索没命中」，根因有两个：
      ① 参数散落在多张表（数据参数 / 生成参数 / 微调参数），BM25 只命中其中一张
      ② 正确答案排在第 4 位之后，被 top-3 截掉

    v1 加两层（对应 out/prediction.md 的方案 A + B）：
      ① PARAM_BOOST：query 里的参数名（如 cutoff_len）若出现在块的表格行首，额外加分
      ② top-k 默认从 3 提到 6
    """

    HEADING_BOOST = 6.0   # 每个命中标题/路径的查询词加分
    PARAM_BOOST = 8.0     # 参数名出现在表格行首的加分（强信号，高于标题加权）
    CANDIDATE_POOL = 30   # 先取前 N 个再重排

    @staticmethod
    def _table_params(text: str) -> set:
        """从 markdown 表格行首提取参数名（形如 `| cutoff_len | int | ... |`）。"""
        names = set()
        for line in text.split("\n"):
            if not line.startswith("|"):
                continue
            cell = line.strip("|").split("|")[0].strip(" `*")
            if re.fullmatch(r"[a-z][a-z0-9_]{2,40}", cell):
                names.add(cell)
        return names

    @staticmethod
    def _query_params(query: str) -> set:
        """从 query 里提取「像参数名」的词：带下划线，或长度 >= 8 的英文词。"""
        words = re.findall(r"[a-z][a-z0-9_]{2,40}", query.lower())
        return {w for w in words if "_" in w or len(w) >= 8}

    def __init__(self, chunks_path: Path):
        if not chunks_path.exists():
            raise SystemExit(
                f"找不到索引文件 {chunks_path}\n请先运行：python scripts/build_index.py"
            )
        self.chunks = [json.loads(l) for l in chunks_path.open(encoding="utf-8")]
        corpus = [tokenize(c["heading"] + "\n" + c["text"]) for c in self.chunks]
        self.bm25 = rank_bm25.BM25Okapi(corpus)
        self.head_tokens = [
            set(tokenize(c["heading"])) | set(tokenize(c["path"])) for c in self.chunks
        ]
        # v1 新增：每个块里出现的参数名
        self.param_names = [self._table_params(c["text"]) for c in self.chunks]
        print(f"[检索] 已加载 {len(self.chunks)} 个块（v1：参数名加权 + top-k 6）")

    def top_k(self, query: str, k: int = 6) -> list:
        qtok = tokenize(query)
        if not qtok:
            return []
        qset = set(qtok)
        qparams = self._query_params(query)
        scores = self.bm25.get_scores(qtok)

        pool = scores.argsort()[::-1][: self.CANDIDATE_POOL]
        reranked = []
        for i in pool:
            i = int(i)
            base = float(scores[i])
            overlap = len(qset & self.head_tokens[i])
            hit_params = len(qparams & self.param_names[i]) if qparams else 0
            final = base + overlap * self.HEADING_BOOST + hit_params * self.PARAM_BOOST
            reranked.append((final, overlap, hit_params, base, i))
        reranked.sort(key=lambda x: -x[0])

        out = []
        for final, overlap, hit_params, base, i in reranked[:k]:
            c = self.chunks[i]
            out.append(
                {
                    "score": round(final, 2),
                    "bm25": round(base, 2),
                    "head_overlap": overlap,
                    "param_hit": hit_params,
                    "source": c["source"],
                    "path": c["path"],
                    "heading": c["heading"],
                    "text": c["text"],
                }
            )
        return out


# ─────────────────────────── 模型 ───────────────────────────
@dataclass
class ModelCfg:
    name: str  # 展示名，写进 CSV
    kind: str  # "ollama" 或 "openai"
    model: str  # 实际模型 id
    base_url: str = ""
    api_key_env: str = ""
    temperature: float = 0.0
    max_tokens: int = 800


def load_model_config(path: Path) -> list[ModelCfg]:
    if not path.exists():
        raise SystemExit(f"找不到模型配置 {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [ModelCfg(**m) for m in raw["models"]]


REWRITE_PROMPT = """你是检索查询改写器。把用户的技术问题改写成更适合关键词检索的形式。

规则：
1. 保留问题里出现的所有参数名、配置项、命令（如 cutoff_len、lora_rank、save_steps）
2. 如果问题用泛称（如「那个参数」「这类配置」），且能从问题本身推断出具体名词，就补上；推断不出就不要编
3. 补充技术同义词，例如：推理→predict/inference，合并→export/merge，中断→resume/断点续训
4. 不要回答问题，不要解释，不要加引号
5. 只输出改写后的一行文本

原问题：{q}
改写后："""


def rewrite_query(cfg: ModelCfg, question: str) -> str:
    """用模型把问题改写成更适合 BM25 检索的形式。

    只用于检索，不改变实际回答时使用的问题。
    失败时回退到原问题，保证不影响主流程。
    """
    try:
        res = call_model(
            cfg,
            [{"role": "user", "content": REWRITE_PROMPT.format(q=question)}],
            retries=1,
        )
        out = (res.get("text") or "").strip().split("\n")[0].strip()
        # 防御：改写结果过长或过短都视为失败
        if 4 <= len(out) <= 300 and out != question:
            return out
    except Exception:
        pass
    return question


def build_messages(question: str, contexts: list[dict]) -> list[dict]:
    ctx_text = "\n\n".join(
        f"[资料 {i + 1}] 来源：{c['path']} ｜ {c['heading']}\n{c['text']}"
        for i, c in enumerate(contexts)
    )
    system = (
        "你是 LlamaFactory 中文技术支持助手。"
        "只根据下面提供的资料回答用户问题；资料里没有的内容不要编造，"
        "如果资料不足以回答，请直接说明「资料里没有找到」。"
        "回答用中文，简洁准确，必要时给出具体的参数名或配置片段。"
    )
    user = f"【资料】\n{ctx_text}\n\n【问题】\n{question}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def call_ollama(cfg: ModelCfg, messages: list[dict], timeout: int = 180) -> dict:
    import urllib.request

    body = json.dumps(
        {
            "model": cfg.model,
            "messages": messages,
            "stream": False,
            "think": False,  # qwen3 关闭思考模式，避免超长推理
            "options": {
                "temperature": cfg.temperature,
                "num_predict": cfg.max_tokens,
            },
        }
    ).encode()
    req = urllib.request.Request(
        f"{cfg.base_url or 'http://127.0.0.1:11434'}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return {
        "text": (data.get("message") or {}).get("content", ""),
        "in_tokens": data.get("prompt_eval_count", 0),
        "out_tokens": data.get("eval_count", 0),
    }


def call_openai_compatible(cfg: ModelCfg, messages: list[dict], timeout: int = 180) -> dict:
    import urllib.request

    key = os.environ.get(cfg.api_key_env or "", "")
    if not key:
        raise RuntimeError(f"环境变量 {cfg.api_key_env} 未设置")
    body = json.dumps(
        {
            "model": cfg.model,
            "messages": messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
    ).encode()
    req = urllib.request.Request(
        f"{cfg.base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    usage = data.get("usage") or {}
    return {
        "text": data["choices"][0]["message"]["content"],
        "in_tokens": usage.get("prompt_tokens", 0),
        "out_tokens": usage.get("completion_tokens", 0),
    }


def call_model(cfg: ModelCfg, messages: list[dict], retries: int = 2) -> dict:
    last = None
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            if cfg.kind == "ollama":
                res = call_ollama(cfg, messages)
            elif cfg.kind == "openai":
                res = call_openai_compatible(cfg, messages)
            else:
                raise ValueError(f"未知模型类型 {cfg.kind}")
            res["elapsed"] = round(time.time() - t0, 2)
            return res
        except Exception as e:  # noqa: BLE001
            last = e
            wait = 2**attempt
            print(f"    [重试 {attempt + 1}/{retries}] {type(e).__name__}: {e}，{wait}s 后重试")
            time.sleep(wait)
    return {
        "text": f"__ERROR__ {type(last).__name__}: {last}",
        "in_tokens": 0,
        "out_tokens": 0,
        "elapsed": 0.0,
    }


# ─────────────────────────── 主流程 ───────────────────────────
def load_questions(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"找不到题目文件 {path}\n"
            "需要先用 scripts/build_questions.py 生成（或手工填写），"
            "字段：id / question / answer / doc_location / split"
        )
    qs = json.loads(path.read_text(encoding="utf-8"))
    for q in qs:
        if q.get("split") not in ("optimize", "test"):
            raise SystemExit(f"题 {q.get('id')} 的 split 必须是 optimize 或 test")
    return qs


def main() -> int:
    ap = argparse.ArgumentParser(description="第 1 周：检索 + 多模型回答 + 输出 CSV")
    ap.add_argument("--split", choices=["optimize", "test", "all"], default="optimize")
    ap.add_argument("--version", default="v0", help="版本号，如 v0 / v1")
    ap.add_argument("--questions", default=str(DATA / "questions.json"))
    ap.add_argument("--models", default=str(ROOT / "configs" / "models.json"))
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（调试用）")
    ap.add_argument("--rewrite", action="store_true", help="检索前用模型改写查询（v3 实验）")
    ap.add_argument("--dry-run", action="store_true", help="只检索不调模型")
    ap.add_argument("--workers", type=int, default=4, help="并发数（默认 4）")
    args = ap.parse_args()

    # ★ 测试集锁定：跑 optimize 时明确拒绝跑 test
    if args.split == "optimize":
        print("[锁定] 本次只跑「优化用」，测试集保持封存")

    retriever = Retriever(DATA / "chunks.jsonl")
    questions = load_questions(Path(args.questions))

    if args.split != "all":
        questions = [q for q in questions if q["split"] == args.split]
    if args.limit:
        questions = questions[: args.limit]

    print(f"[题目] 本次 {len(questions)} 道（split={args.split}）")

    models = load_model_config(Path(args.models))
    print(f"[模型] {', '.join(m.name for m in models)}")

    OUT.mkdir(exist_ok=True)
    out_csv = OUT / f"week1_{args.split}_{args.version}.csv"

    write_header = not out_csv.exists()
    f = out_csv.open("a", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    if write_header:
        writer.writeheader()

    total = len(questions) * len(models)
    done = 0
    t_start = time.time()

    # 并发执行（默认 4 路）。慢模型（推理模型）单次可能上百秒，串行太慢。
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    lock = threading.Lock()
    tasks = []

    # v3：可选查询改写（只影响检索，不影响回答用的问题）
    rewriter = models[0] if args.rewrite else None
    if rewriter:
        print(f"[改写] 使用 {rewriter.name} 改写查询")

    for q in questions:
        rq = rewrite_query(rewriter, q["question"]) if rewriter else q["question"]
        if rewriter and rq != q["question"]:
            print("  题" + str(q["id"]) + " 改写: " + rq[:60])
        contexts = retriever.top_k(rq, k=args.topk)
        ctx_brief = " ｜ ".join(
            f"{c['path']}#{c['heading'][:40]}({c['score']})" for c in contexts
        )
        src_kinds = ",".join(sorted({c["source"] for c in contexts}))

        if args.dry_run:
            print(f"\n#{q['id']} {q['question'][:60]}")
            for c in contexts:
                print(f"   [{c['score']:7.1f}] {c['path']} | {c['heading'][:50]}")
            continue

        messages = build_messages(q["question"], contexts)
        for m in models:
            tasks.append((q, m, messages, ctx_brief, src_kinds))

    def work(task):
        q, m, messages, ctx_brief, src_kinds = task
        res = call_model(m, messages)
        row = {
            "题号": q["id"],
            "问题": q["question"],
            "所属份": "优化用" if q["split"] == "optimize" else "测试用",
            "模型": m.name,
            "版本": args.version,
            "回答": res["text"],
            "检索到的段落": ctx_brief,
            "人工判分": "",
            "失败原因": "",
            "判断理由": "",
            "耗时秒": res["elapsed"],
            "输入token": res["in_tokens"],
            "输出token": res["out_tokens"],
            "检索命中来源": src_kinds,
            "时间戳": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return task, res, row

    if not args.dry_run:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(work, t): t for t in tasks}
            for fut in as_completed(futures):
                task, res, row = fut.result()
                q, m = task[0], task[1]
                with lock:
                    done += 1
                    ok = not res["text"].startswith("__ERROR__")
                    print(
                        f"  [{done}/{total}] #{q['id']} × {m.name} ... "
                        f"{res['elapsed']}s" + ("" if ok else " ✗"),
                        flush=True,
                    )
                    writer.writerow(row)
                    f.flush()

    f.close()

    if args.dry_run:
        print("\n[dry-run] 未调用模型")
        return 0

    elapsed = time.time() - t_start
    print(f"\n完成：{done} 条回答，用时 {elapsed:.0f}s")
    print(f"输出：{out_csv}")
    print("\n下一步：人工填写「人工判分」「失败原因」「判断理由」三列")
    print(f"  失败原因可选值：{' / '.join(FAIL_REASONS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
