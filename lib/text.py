"""共享分词模块：索引和查询必须用完全相同的分词，否则 BM25 分数没有意义。"""
from __future__ import annotations

import re

import jieba

CJK = re.compile(r"[\u4e00-\u9fff]")

# 英文停用词（不参与检索）
EN_STOP = {
    "the", "and", "for", "with", "that", "this", "you", "your", "are", "was", "were",
    "have", "has", "had", "not", "but", "can", "could", "would", "should", "will",
    "how", "what", "which", "when", "where", "why", "who", "does", "did", "doing",
    "use", "using", "used", "set", "get", "put", "any", "all", "some", "one", "two",
    "there", "their", "them", "then", "than", "from", "into", "out", "about", "after",
    "before", "more", "most", "much", "many", "very", "just", "also", "only", "like",
    "want", "need", "make", "made", "way", "now", "new", "old", "see", "say", "said",
    "my", "me", "we", "our", "it", "its", "is", "be", "been", "being", "do", "done",
    "on", "in", "at", "to", "of", "or", "as", "by", "if", "so", "no", "up", "an",
    "support", "question", "help", "please", "thanks", "thank", "issue", "problem",
}

# 中文停用词
ZH_STOP = {
    "怎么", "如何", "什么", "哪些", "哪个", "是否", "能否", "可以", "能不能", "有没有",
    "请问", "请教", "求助", "一下", "这个", "那个", "现在", "还是", "但是", "因为",
    "所以", "如果", "已经", "可能", "需要", "应该", "我们", "你们", "他们", "自己",
    "时候", "问题", "情况", "地方", "东西", "方法", "方式", "步骤", "使用", "进行",
    "支持", "参数", "配置", "设置", "默认", "区别", "含义", "作用", "用法",
}

EN_TOKEN = re.compile(r"[a-z_][a-z0-9_.\-]{1,30}")


def tokenize(text: str) -> list[str]:
    """中英混合分词。

    - 英文：长度 >= 3，去停用词；但含下划线/点的技术标识（save_steps、fsdp_config）保留
    - 中文：jieba 切分，长度 >= 2，去停用词
    """
    text = text.lower()
    out: list[str] = []

    for tok in EN_TOKEN.findall(text):
        if "_" in tok or "." in tok:  # 技术标识，一定保留
            out.append(tok)
        elif len(tok) >= 3 and tok not in EN_STOP:
            out.append(tok)

    for w in jieba.cut(text):
        if CJK.search(w) and len(w) >= 2 and w not in ZH_STOP:
            out.append(w)

    return out
