#!/usr/bin/env python3
"""题库核对页的自测：用假 DOM 在 node 里跑一遍，验证按钮真能翻页。

为什么需要：用户反馈「点了没反应」。语法检查过了但运行时崩了，
所以必须真的模拟一次点击，看到底能不能翻页。

做法：把页面里的 <script> 抽出来，前面套一层最小 DOM stub，
后面接一段「点『对』看序号变不变」的断言，整个丢给 node 执行。

用法：
    python scripts/selftest_qbank.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "out" / "qbank.html"

STUB = r"""
const els = {};
function mk(id){
  if(!els[id]) els[id] = {id, textContent:"", value:"", innerHTML:"", href:"", style:{}, dataset:{},
    classList:{toggle(){},add(){},remove(){}}, focus(){}, select(){}, addEventListener(){}};
  return els[id];
}
const buttons = ["对","改","砍"].map(v=>({dataset:{v}, classList:{toggle(){}}, onclick:null}));
global.document = {
  getElementById: mk,
  querySelectorAll: (s)=> s===".verdict button" ? buttons : [],
  addEventListener(){}, createElement:()=>mk("tmp"),
  body:{appendChild(){},removeChild(){}}
};
global.window = { addEventListener(){} };
const store = {};
global.localStorage = {
  getItem:k=>(k in store?store[k]:null),
  setItem:(k,v)=>{store[k]=v},
  removeItem:k=>{delete store[k]}
};
global.confirm = ()=>false;
global.setTimeout = ()=>0;
global.URL = {createObjectURL:()=>"blob:x", revokeObjectURL(){}};
global.Blob = function(){};
"""

TEST = r"""
function fail(msg){ console.log("  ✗ " + msg); process.exitCode = 1; }

const seq0 = els["seq"].textContent;
const total = els["total"].textContent;
console.log("  初始序号: " + seq0 + "   总数: " + total);

if (!buttons[0].onclick) { fail("按钮没绑上 onclick"); }
else {
  buttons[0].onclick();
  const seq1 = els["seq"].textContent;
  console.log("  点「对」后: " + seq1 + "   已完成: " + els["done"].textContent);
  if (seq0 === seq1) fail("点了没翻页");
  else console.log("  ✓ 点「对」能翻页");
}

if (buttons[2].onclick) {
  buttons[2].onclick();
  console.log("  点「砍」后: " + els["seq"].textContent);
  console.log("  ✓ 点「砍」无异常");
}

if (els["export"] && els["export"].onclick) {
  try { els["export"].onclick(); console.log("  ✓ 导出无异常"); }
  catch (e) { fail("导出报错: " + e.message); }
}

if (typeof store !== "undefined") {
  console.log("  存档: " + (Object.keys(store).length ? "有存档" : "无存档"));
}
"""


SANDBOX_STUB = r"""
// 模拟沙箱环境：localStorage 一碰就抛异常（预览面板常见）
const els = {};
function mk(id){
  if(!els[id]) els[id] = {id, textContent:"", value:"", innerHTML:"", href:"", style:{}, dataset:{},
    classList:{toggle(){},add(){},remove(){}}, focus(){}, select(){}, addEventListener(){}};
  return els[id];
}
const buttons = ["对","改","砍"].map(v=>({dataset:{v}, classList:{toggle(){}}, onclick:null}));
global.document = {
  getElementById: mk,
  querySelectorAll: (s)=> s===".verdict button" ? buttons : [],
  addEventListener(){}, createElement:()=>mk("tmp"),
  body:{appendChild(){},removeChild(){}}
};
global.window = { addEventListener(){} };
global.localStorage = {
  getItem(){ throw new Error("SecurityError: localStorage blocked"); },
  setItem(){ throw new Error("SecurityError: localStorage blocked"); },
  removeItem(){ throw new Error("SecurityError: localStorage blocked"); }
};
global.confirm = ()=>false;
global.setTimeout = ()=>0;
global.URL = {createObjectURL:()=>"blob:x", revokeObjectURL(){}};
global.Blob = function(){};
"""


def main() -> int:
    ap_args = sys.argv[1:]
    sandbox = "--sandbox" in ap_args

    if not HTML.exists():
        print(f"找不到 {HTML}，先跑 python scripts/qbank_aid.py make")
        return 1

    html = HTML.read_text(encoding="utf-8")
    m = re.search(r"<script>(.*?)</script>", html, re.S)
    if not m:
        print("页面里没有 <script>")
        return 1
    script = m.group(1)

    stub = SANDBOX_STUB if sandbox else STUB
    program = stub + script + TEST

    mode = "沙箱模式（localStorage 抛异常）" if sandbox else "正常模式"
    print(f"自测 {HTML.name} — {mode}")
    r = subprocess.run(["node"], input=program, capture_output=True, text=True, timeout=120)
    print(r.stdout.rstrip())
    if r.stderr.strip():
        print("--- node stderr ---")
        print(r.stderr.strip()[:1200])
    if r.returncode != 0:
        print("✗ 自测失败")
        return 1
    print("✓ 自测通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
