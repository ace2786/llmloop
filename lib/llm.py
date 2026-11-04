"""统一调用层：所有模型调用都从这里出去。

为什么要单独一层（任务书第 5 节架构图里的「统一调用层」）：
  - 限速：免费接口有并发/频率限制，集中管一处
  - 重试：偶发 429 / 连接失败，退避重试
  - 记录耗时：每次调用返回用时，便于统计「每题多久」
  - 统一入口：脚本、接口、优化循环都用同一份，不各写一套

当前支持两种后端：
  - 本地 Ollama（模型名不以 glm 开头）
  - 智谱云端（模型名以 glm 开头，需要 .env 里的 ZHIPU_API_KEY）
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLLAMA = "http://127.0.0.1:11434/api/generate"
ZHIPU = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

THINK = re.compile(r"<think>.*?</think>", re.S)

# 限速：两次调用之间至少间隔这么多秒（云端免费额度有限，本地不受影响）
MIN_INTERVAL = 0.0
_last_call = 0.0


def load_env() -> None:
    """读 .env 里的 key（不覆盖已有环境变量）。"""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _throttle() -> None:
    global _last_call
    if MIN_INTERVAL <= 0:
        return
    gap = time.time() - _last_call
    if gap < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - gap)
    _last_call = time.time()


def _post(url: str, body: dict, headers: dict, timeout: int) -> dict:
    """带退避重试的 POST。429 / 5xx / 连接错误都重试。"""
    data = json.dumps(body).encode()
    last_err: Exception | None = None
    for attempt in range(3):
        _throttle()
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            if e.code >= 500:
                time.sleep(2)
                continue
            raise  # 4xx（除 429）是请求本身的问题，重试没用
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2)
    raise last_err if last_err else RuntimeError("调用失败")


def ask_glm(prompt: str, model: str, num_predict: int = 220) -> tuple[str, float]:
    """调智谱免费模型。被测助手用云端免费模型是任务书第 7 节允许的。"""
    load_env()
    key = os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        raise RuntimeError("ZHIPU_API_KEY 未设置，无法调用 " + model)
    t0 = time.time()
    d = _post(
        ZHIPU,
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": num_predict,
        },
        {"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        timeout=120,
    )
    ans = THINK.sub("", d["choices"][0]["message"]["content"]).strip()
    return ans, time.time() - t0


def ask(model: str, prompt: str, num_predict: int = 220) -> tuple[str, float]:
    """统一的提问入口，返回 (回答, 耗时秒)。"""
    if model.startswith("glm"):
        return ask_glm(prompt, model, num_predict)

    t0 = time.time()
    d = _post(
        OLLAMA,
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": num_predict, "temperature": 0, "top_p": 0.9},
        },
        {"Content-Type": "application/json"},
        timeout=180,
    )
    ans = THINK.sub("", d.get("response", "")).strip()
    return ans, time.time() - t0


def build_prompt(question: str, contexts: list[str]) -> str:
    """把检索到的文档块和问题拼成提示词。脚本和接口共用，保证问法一致。"""
    prompt = "/no_think\n"
    if contexts:
        ctx = "\n\n".join(f"[文档{i+1}] {t[:900]}" for i, t in enumerate(contexts))
        prompt += f"根据下面的文档回答问题，只答文档里明确写的内容，不要编造。\n\n{ctx}\n\n"
    prompt += f"问题：{question}\n回答："
    return prompt
