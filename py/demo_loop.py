#!/usr/bin/env python3
"""demo_loop.py — 模拟 dsh agent 自愈闭环（不依赖 dsh 即可本地演示）。

流程模拟模型的行为：
  1. list_math_templates 发现能力
  2. render_math_scene 按模板渲染
  3. 若失败 → 将错误回喂 → 修正参数重试（最多 N 轮）

用法：
  python3 py/demo_loop.py
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manim_runner as mr  # noqa: E402

OUTDIR = str(Path(__file__).resolve().parent.parent / "out")


def call_render(template: str, params: dict, quality: str = "low") -> dict:
    """等价于 TS 侧 render_math_scene 工具调用。"""
    args = type("A", (), {"template": template, "params": json.dumps(params), "quality": quality, "outdir": OUTDIR})()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mr.cmd_render(args)
    result = json.loads(buf.getvalue())
    result["_rc"] = rc
    return result


def main() -> int:
    print("=" * 72)
    print("dshmath-manim 闭环演示（模拟 agent 工具调用）")
    print("=" * 72)

    # 1) 发现能力
    print("\n[1] list_math_templates →")
    templates = mr._load_templates()
    print("    可用模板:", ", ".join(sorted(templates)))

    # 2) 首次渲染（故意给一个非法参数触发参数校验错误）
    print("\n[2] render_math_scene(template=derivative_tangent, params={func, point: '1.5'(字符串), title})")
    r1 = call_render("derivative_tangent", {"func": "np.sin(x)", "point": "1.5"})
    print(f"    -> ok={r1.get('ok')} error={r1.get('error')!r}")

    # 3) 自愈：模型看到错误后修正参数重试
    print("\n[3] 模型修正参数后重试：point 改为数值 1.5")
    r2 = call_render("derivative_tangent", {"func": "np.sin(x)", "point": 1.5, "title": r"f(x)=\sin x"})
    print(f"    -> ok={r2.get('ok')} video={r2.get('video')}")

    # 4) 渲染更多模板
    print("\n[4] 渲染其余模板")
    cases = [
        ("function_plot", {"functions": ["np.sin(x)", "x**2"], "title": r"y=\sin(x),\ y=x^2"}),
        ("definite_integral", {"func": "np.sin(x)", "a": 0, "b": 3.14, "title": r"\int_0^{\pi}\sin x\,dx"}),
        ("geometry", {"shape": "triangle", "label": r"\triangle ABC", "color": "blue"}),
        ("polar_plot", {"expr": "1+np.cos(t)", "title": r"r=1+\cos\theta"}),
        ("surface_3d", {"expr": "np.sin(np.hypot(x, y))"}),
    ]
    for name, params in cases:
        r = call_render(name, params)
        print(f"    {name:20s} ok={r.get('ok')}  video={(r.get('video') or 'NONE').split('/')[-1]}")

    # 5) 安全校验演示
    print("\n[5] validate_math_code(含 os.system 的恶意代码)")
    ok, violations = mr._validate_code("import os\nos.system('rm -rf /')\n")
    print(f"    -> ok={ok} violations={violations}")

    print("\n" + "=" * 72)
    print("演示完成：模板渲染 ✓  自愈重试 ✓  安全拦截 ✓")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
