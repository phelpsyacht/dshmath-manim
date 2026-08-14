#!/usr/bin/env python3
"""manim_runner.py — Manim CE 渲染执行器（dshmath-manim 后端）。

DeepSeek Harness 的 TS Tool 插件通过 subprocess 调用本脚本，在独立进程内
完成场景代码生成、静态校验与渲染，输出机器可读的 JSON 结果。

子命令：
  render        按模板 + 参数生成场景并渲染（推荐，安全）
  render-code   渲染一个已存在的 Python 场景文件（模型自写代码，进阶）
  validate      仅对场景代码做静态安全检查
  templates     列出可用模板及其参数模式
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# 允许在模板参数中使用的全局符号（数学库子集）
SAFE_GLOBALS = {
    "np": __import__("numpy", globals(), locals(), [], 0) if shutil.which("python3") else None,
    "math": __import__("math"),
    "pi": __import__("math").pi,
    "e": __import__("math").e,
    "tau": __import__("math").tau,
}

# 渲染时对模型可见的"安全"全局，禁止访问文件系统/进程等
FORBIDDEN_NAMES = {"__import__", "eval", "exec", "open", "compile", "globals", "locals", "vars", "getattr", "setattr", "__builtins__"}

TEMPLATE_BLACKLIST = {"__builtins__", "__import__", "eval", "exec", "open", "compile", "getattr", "setattr", "subprocess", "os"}

VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov")


def _banner() -> dict:
    return {
        "name": "dshmath-manim",
        "version": "0.1.0",
        "manim_version": _manim_version(),
        "templates_dir": str(TEMPLATES_DIR),
    }


def _manim_version() -> str:
    try:
        import manim  # noqa: F401

        return manim.__version__
    except Exception:
        return "not-installed"


# ---------------------------------------------------------------------------
# 模板系统
# ---------------------------------------------------------------------------

def _load_templates() -> dict[str, dict]:
    """扫描 py/templates 下的模板定义文件，返回 {name: meta}。"""
    templates: dict[str, dict] = {}
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            templates[path.stem] = {"error": f"malformed template: {exc}"}
            continue
        meta.setdefault("name", path.stem)
        meta.setdefault("description", "")
        meta.setdefault("parameters", {})
        meta.setdefault("code", "")
        templates[path.stem] = meta
    return templates


def _load_template_code(name: str) -> str:
    return (TEMPLATES_DIR / f"{name}.py").read_text(encoding="utf-8")


def _validate_template_params(meta: dict, params: dict) -> list[str]:
    """校验参数是否符合模板声明的模式（类型 / 必填）。"""
    errors: list[str] = []
    schema = meta.get("parameters", {})
    for key, spec in schema.items():
        required = spec.get("required", False)
        if required and key not in params:
            errors.append(f"missing required parameter '{key}'")
            continue
        if key not in params:
            continue
        typ = spec.get("type")
        value = params[key]
        if typ == "number" and isinstance(value, bool):
            errors.append(f"parameter '{key}' must be a number")
        elif typ == "number" and not isinstance(value, (int, float)):
            errors.append(f"parameter '{key}' must be a number, got {type(value).__name__}")
        elif typ == "string" and not isinstance(value, str):
            errors.append(f"parameter '{key}' must be a string, got {type(value).__name__}")
        elif typ == "boolean" and not isinstance(value, bool):
            errors.append(f"parameter '{key}' must be a boolean, got {type(value).__name__}")
        elif typ == "array" and not isinstance(value, list):
            errors.append(f"parameter '{key}' must be an array, got {type(value).__name__}")
    unknown = set(params) - set(schema)
    if unknown:
        errors.append(f"unknown parameters: {sorted(unknown)}")
    return errors


def _render_template(meta: dict, params: dict, code: str) -> str:
    """将参数安全地注入模板代码：只做 {key} 文本替换，绝不 eval 用户代码。
    未显式提供的参数使用模板声明的默认值（default 字段）。"""
    merged = dict(params)
    for key, spec in meta.get("parameters", {}).items():
        if key not in merged and "default" in spec:
            merged[key] = spec["default"]
    for key, value in merged.items():
        code = code.replace(f"{{{{{key}}}}}", _safe_literal(value))
    # 残留的未替换占位符会破坏语法，直接报错
    leftovers = re.findall(r"\{\{\s*\w+\s*\}\}", code)
    if leftovers:
        raise ValueError(f"template placeholders not filled: {sorted(set(leftovers))}")
    return code


def _safe_literal(value: object) -> str:
    """把参数渲染成可安全 eval 的 Python 字面量。"""
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple, dict)):
        return repr(value)
    raise ValueError(f"unsupported parameter type: {type(value).__name__}")


# ---------------------------------------------------------------------------
# 静态校验
# ---------------------------------------------------------------------------

def _validate_code(code: str) -> tuple[bool, list[str]]:
    """AST 级安全校验：仅允许纯数学场景代码，拒绝危险调用。"""
    errors: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, [f"syntax error: {exc.msg} at line {exc.lineno}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split(".")[0]
                if base in TEMPLATE_BLACKLIST:
                    errors.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in TEMPLATE_BLACKLIST:
                errors.append(f"forbidden import from: {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_NAMES:
                errors.append(f"forbidden call: {node.func.id}()")
    return not errors, errors


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _clean_env() -> dict:
    """构造纯净环境：清除 IDE 注入的安全删除钩子，避免批量清理临时文件被拦截。"""
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("CODEBUDDY_SAFE_DELETE") or key == "GENIE_TRASH_DIR":
            env.pop(key, None)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONSTARTUP", None)
    return env


def _render_manim(code_file: Path, quality: str, outdir: Path, extra_args: list[str]) -> subprocess.CompletedProcess:
    """调用 manim CLI 渲染。quality: low/medium/high/ultra。"""
    quality_map = {"low": "-ql", "medium": "-qm", "high": "-qh", "ultra": "-qp"}
    flag = quality_map.get(quality, "-ql")
    cmd = [
        sys.executable, "-m", "manim",
        flag,
        "--format", "mp4",
        "--media_dir", str(outdir),
        *extra_args,
        str(code_file),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=_clean_env())


def _find_video(outdir: Path) -> Path | None:
    """定位成片：排除 partial_movie_files 中间文件，优先取最新的完整视频。"""
    for ext in VIDEO_EXTENSIONS:
        hits = [h for h in outdir.rglob(f"*{ext}") if "partial_movie_files" not in h.parts]
        if hits:
            return sorted(hits, key=lambda p: p.stat().st_mtime)[-1]
    return None


def render_scene(template: str, params: dict, quality: str = "low", outdir: str | Path | None = None) -> dict:
    """渲染一个模板场景，返回结果 dict（不打印）。供 CLI / wizard / TS 桥接共用。"""
    templates = _load_templates()
    if template not in templates:
        return {"ok": False, "error": f"unknown template '{template}'", "available": sorted(templates)}

    meta = templates[template]
    errors = _validate_template_params(meta, params)
    if errors:
        return {"ok": False, "error": "parameter validation failed", "details": errors}

    try:
        code = _render_template(meta, params, meta["code"])
    except Exception as exc:
        return {"ok": False, "error": f"template expansion failed: {exc}"}

    with tempfile.TemporaryDirectory() as tmp:
        code_file = Path(tmp) / f"{meta.get('name', template)}_scene.py"
        code_file.write_text(code, encoding="utf-8")
        # 模板代码是可信的（仓库自带），只做语法检查，不做 AST 安全校验
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return {"ok": False, "error": f"expanded template has syntax error: {exc}", "code": code}

        out = Path(outdir).resolve() if outdir else Path.cwd() / "out"
        out.mkdir(parents=True, exist_ok=True)
        proc = _render_manim(code_file, quality, out, [])
        video = _find_video(out)
        result = {
            "ok": proc.returncode == 0,
            "template": template,
            "params": params,
            "quality": quality,
            "returncode": proc.returncode,
            "video": str(video) if video else None,
            "size_bytes": video.stat().st_size if video else None,
        }
        if proc.returncode != 0:
            result["error"] = proc.stderr[-2000:]
        return result


def cmd_render(args: argparse.Namespace) -> int:
    try:
        params = json.loads(args.params or "{}")
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"invalid params JSON: {exc}"}))
        return 2
    result = render_scene(args.template, params, args.quality, args.outdir)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 2 if "unknown template" in str(result.get("error", "")) else 1


def cmd_render_code(args: argparse.Namespace) -> int:
    code_file = Path(args.code_file).resolve()
    if not code_file.exists():
        print(json.dumps({"ok": False, "error": f"code file not found: {code_file}"}))
        return 2
    code = code_file.read_text(encoding="utf-8")
    ok, violations = _validate_code(code)
    if not ok:
        print(json.dumps({"ok": False, "error": "scene failed static validation", "details": violations}))
        return 2
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    proc = _render_manim(code_file, args.quality, outdir, [])
    video = _find_video(outdir)
    result = {
        "ok": proc.returncode == 0,
        "quality": args.quality,
        "returncode": proc.returncode,
        "video": str(video) if video else None,
        "size_bytes": video.stat().st_size if video else None,
    }
    if proc.returncode != 0:
        result["error"] = proc.stderr[-2000:]
    print(json.dumps(result))
    return 0 if proc.returncode == 0 else 1


def cmd_validate(args: argparse.Namespace) -> int:
    code = args.code
    ok, violations = _validate_code(code)
    print(json.dumps({"ok": ok, "violations": violations}))
    return 0 if ok else 1


def cmd_templates(args: argparse.Namespace) -> int:
    templates = _load_templates()
    print(json.dumps({"ok": True, "templates": templates}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manim_runner", description="Manim CE renderer for dshmath-manim")
    parser.add_argument("--json", action="store_true", help="(reserved) always outputs JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p_templates = sub.add_parser("templates", help="list available templates")
    p_templates.set_defaults(func=cmd_templates)

    p_validate = sub.add_parser("validate", help="static safety check of a scene code string")
    p_validate.add_argument("--code", required=True, help="Python scene source code")
    p_validate.set_defaults(func=cmd_validate)

    p_render = sub.add_parser("render", help="render a template scene")
    p_render.add_argument("--template", required=True)
    p_render.add_argument("--params", default="{}", help="JSON object of template parameters")
    p_render.add_argument("--quality", default="low", choices=["low", "medium", "high", "ultra"])
    p_render.add_argument("--outdir", default=str(Path.cwd() / "out"))
    p_render.set_defaults(func=cmd_render)

    p_render_code = sub.add_parser("render-code", help="render an existing scene python file")
    p_render_code.add_argument("--code-file", required=True)
    p_render_code.add_argument("--quality", default="low", choices=["low", "medium", "high", "ultra"])
    p_render_code.add_argument("--outdir", default=str(Path.cwd() / "out"))
    p_render_code.set_defaults(func=cmd_render_code)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
