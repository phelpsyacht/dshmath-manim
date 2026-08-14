#!/usr/bin/env python3
"""wizard_server.py — 数学动画向导 Web 服务（零代码使用）。

面向只懂数学、不懂代码的用户：
  1. 从模板卡片选择场景（函数图像 / 导数切线 / 定积分 / 几何 / 极坐标 / 3D 曲面）
  2. 填写数学参数表单（全中文，无代码）
  3. 点击"生成动画"，预览并下载视频

启动：
  python3 py/wizard_server.py [--port 8321]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import manim_runner as mr

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "wizard_out"
OUTDIR.mkdir(parents=True, exist_ok=True)

_executor = ThreadPoolExecutor(max_workers=2)
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>数学动画向导 — Manim CE</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    min-height: 100vh; color: #e2e8f0;
  }
  .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
  header { text-align: center; margin-bottom: 36px; }
  header h1 {
    font-size: 34px; font-weight: 700;
    background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  header p { margin-top: 10px; color: #94a3b8; font-size: 15px; }
  main { display: grid; grid-template-columns: 340px 1fr; gap: 24px; }
  @media (max-width: 860px) { main { grid-template-columns: 1fr; } }
  .panel {
    background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 16px; padding: 20px; backdrop-filter: blur(8px);
  }
  .panel h2 { font-size: 15px; color: #94a3b8; margin-bottom: 14px; font-weight: 600; }
  .tpl-grid { display: flex; flex-direction: column; gap: 10px; }
  .tpl-card {
    cursor: pointer; padding: 14px 16px; border-radius: 12px;
    background: rgba(51, 65, 85, 0.6); border: 1px solid transparent;
    transition: all .15s ease;
  }
  .tpl-card:hover { border-color: #60a5fa; transform: translateX(2px); }
  .tpl-card.active {
    border-color: #60a5fa; background: rgba(37, 99, 235, 0.2);
    box-shadow: 0 0 0 1px #60a5fa33;
  }
  .tpl-card .tpl-name { font-size: 16px; font-weight: 600; color: #f1f5f9; }
  .tpl-card .tpl-desc { margin-top: 4px; font-size: 13px; color: #94a3b8; line-height: 1.5; }
  .form-panel { position: relative; }
  .form-empty { color: #64748b; text-align: center; padding: 60px 20px; line-height: 2; }
  .field { margin-bottom: 18px; }
  .field label { display: block; font-size: 14px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px; }
  .field .hint { display: block; font-size: 12px; color: #64748b; margin-top: 5px; line-height: 1.5; }
  input[type=text], input[type=number], textarea, select {
    width: 100%; padding: 10px 12px; border-radius: 10px;
    background: #0f172a; border: 1px solid #334155; color: #e2e8f0;
    font-size: 14px; outline: none; transition: border-color .15s;
  }
  input:focus, textarea:focus, select:focus { border-color: #60a5fa; }
  textarea { resize: vertical; min-height: 80px; font-family: ui-monospace, Menlo, monospace; }
  .actions { display: flex; gap: 12px; align-items: center; margin-top: 8px; }
  button.primary {
    padding: 12px 28px; border: none; border-radius: 12px; cursor: pointer;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6); color: #fff;
    font-size: 15px; font-weight: 600; transition: opacity .15s;
  }
  button.primary:hover { opacity: 0.9; }
  button.primary:disabled { opacity: 0.4; cursor: not-allowed; }
  .status { font-size: 13px; color: #94a3b8; }
  .status.running { color: #60a5fa; }
  .status.error { color: #f87171; }
  .result { margin-top: 20px; display: none; }
  .result.show { display: block; }
  video { width: 100%; border-radius: 12px; background: #000; max-height: 480px; }
  .dl-link { display: inline-block; margin-top: 12px; color: #60a5fa; font-size: 14px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>数学动画向导</h1>
    <p>选择场景，填写数学参数，即可生成教学动画 —— 全程无需任何代码</p>
  </header>
  <main>
    <section class="panel">
      <h2>选择场景</h2>
      <div class="tpl-grid" id="tplGrid"></div>
    </section>
    <section class="panel form-panel">
      <h2 id="formTitle">场景参数</h2>
      <div id="formBody" class="form-empty">
        请先在左侧选择一个场景类型
      </div>
      <div id="result" class="result">
        <h2>动画预览</h2>
        <video id="video" controls autoplay loop muted></video>
        <a id="dl" class="dl-link" download>下载视频</a>
      </div>
    </section>
  </main>
</div>
<script>
let templates = {};
let activeTemplate = null;

async function loadTemplates() {
  const res = await fetch('/api/templates');
  templates = await res.json();
  const grid = document.getElementById('tplGrid');
  grid.innerHTML = '';
  for (const [name, t] of Object.entries(templates)) {
    const ui = t.ui || {};
    const card = document.createElement('div');
    card.className = 'tpl-card';
    card.innerHTML = '<div class="tpl-name">' + (ui.label || name) + '</div>' +
      '<div class="tpl-desc">' + (ui.description || t.description || '') + '</div>';
    card.onclick = () => selectTemplate(name);
    grid.appendChild(card);
  }
}

function selectTemplate(name) {
  activeTemplate = name;
  document.querySelectorAll('.tpl-card').forEach(c => c.classList.remove('active'));
  event.currentTarget.classList.add('active');
  const t = templates[name];
  const ui = t.ui || {};
  document.getElementById('formTitle').textContent = (ui.label || name) + ' — 填写参数';
  const body = document.getElementById('formBody');
  body.className = '';
  body.innerHTML = '';
  const fields = ui.fields || [];
  fields.forEach(f => {
    const wrap = document.createElement('div');
    wrap.className = 'field';
    let input;
    if (f.control === 'select') {
      input = document.createElement('select');
      (f.options || []).forEach(opt => {
        const o = document.createElement('option');
        o.value = opt.value; o.textContent = opt.label;
        input.appendChild(o);
      });
    } else if (f.control === 'textarea') {
      input = document.createElement('textarea');
      input.placeholder = f.hint || '';
    } else {
      input = document.createElement('input');
      input.type = f.control === 'number' ? 'number' : 'text';
      input.placeholder = f.hint || '';
    }
    input.dataset.format = f.format || '';
    const label = document.createElement('label');
    label.textContent = f.label;
    wrap.appendChild(label); wrap.appendChild(input);
    if (f.hint && f.control !== 'textarea') {
      const hint = document.createElement('span');
      hint.className = 'hint'; hint.textContent = f.hint;
      wrap.appendChild(hint);
    }
    body.appendChild(wrap);
  });
  const actions = document.createElement('div');
  actions.className = 'actions';
  const btn = document.createElement('button');
  btn.className = 'primary'; btn.textContent = '生成动画';
  btn.onclick = () => render();
  const status = document.createElement('div');
  status.className = 'status'; status.id = 'status';
  actions.appendChild(btn); actions.appendChild(status);
  body.appendChild(actions);
  document.getElementById('result').classList.remove('show');
}

function collectParams() {
  const t = templates[activeTemplate];
  const ui = t.ui || {};
  const params = {};
  (ui.fields || []).forEach(f => {
    const input = document.querySelector('#formBody .field input[data-format], #formBody .field textarea[data-format], #formBody .field select[data-format]') || null;
  });
  // 按字段顺序读取
  const inputs = document.querySelectorAll('#formBody .field input, #formBody .field textarea, #formBody .field select');
  (ui.fields || []).forEach((f, i) => {
    const el = inputs[i];
    if (!el) return;
    let val = el.value.trim();
    if (val === '') return;
    if (el.dataset.format === 'array') {
      val = val.split(',').map(s => parseFloat(s.trim()));
    } else if (el.type === 'number') {
      val = parseFloat(val);
    }
    params[f.key] = val;
  });
  return params;
}

async function render() {
  const btn = document.querySelector('#formBody .primary');
  const status = document.getElementById('status');
  btn.disabled = true;
  status.className = 'status running';
  status.textContent = '提交渲染任务…';
  const params = collectParams();
  const res = await fetch('/api/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template: activeTemplate, params })
  });
  const { task_id } = await res.json();
  status.textContent = '正在渲染（首次约 30~60 秒）…';
  const poll = setInterval(async () => {
    const r = await fetch('/api/status/' + task_id);
    const data = await r.json();
    if (data.state === 'done') {
      clearInterval(poll);
      status.className = 'status';
      status.textContent = '完成';
      btn.disabled = false;
      const result = document.getElementById('result');
      result.classList.add('show');
      document.getElementById('video').src = data.video;
      document.getElementById('dl').href = data.video;
    } else if (data.state === 'error') {
      clearInterval(poll);
      status.className = 'status error';
      status.textContent = '生成失败：' + (data.error || '未知错误');
      btn.disabled = false;
    }
  }, 1500);
}

loadTemplates();
</script>
</body>
</html>
"""


def _build_public_templates() -> dict:
    templates = mr._load_templates()
    public = {}
    for name, meta in templates.items():
        public[name] = {
            "name": name,
            "description": meta.get("description", ""),
            "ui": meta.get("ui", {}),
        }
    return public


def _render_job(tid: str, template: str, params: dict) -> None:
    try:
        result = mr.render_scene(template, params, quality="low", outdir=OUTDIR)
        if result.get("ok") and result.get("video"):
            video_path = Path(result["video"])
            rel = video_path.relative_to(OUTDIR)
            with _tasks_lock:
                _tasks[tid] = {
                    "state": "done",
                    "video": f"/video/{rel}",
                    "size": result.get("size_bytes"),
                }
        else:
            with _tasks_lock:
                _tasks[tid] = {"state": "error", "error": str(result.get("error", "unknown error"))[:1500]}
    except Exception as exc:  # noqa: BLE001
        with _tasks_lock:
            _tasks[tid] = {"state": "error", "error": str(exc)[:1500]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静默
        pass

    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/templates":
            self._send_json(_build_public_templates())
        elif path.startswith("/api/status/"):
            tid = path.rsplit("/", 1)[-1]
            with _tasks_lock:
                data = _tasks.get(tid, {"state": "unknown"})
            self._send_json(data)
        elif path.startswith("/video/"):
            rel = path[len("/video/"):]
            target = OUTDIR / rel
            if target.is_file():
                ctype, _ = mimetypes.guess_type(str(target))
                body = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype or "video/mp4")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send_json({"error": "video not found"}, 404)
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/render":
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON"}, 400)
                return
            template = payload.get("template", "")
            params = payload.get("params", {})
            templates = mr._load_templates()
            if template not in templates:
                self._send_json({"error": f"unknown template: {template}"}, 400)
                return
            tid = uuid.uuid4().hex[:12]
            with _tasks_lock:
                _tasks[tid] = {"state": "running"}
            _executor.submit(_render_job, tid, template, params)
            self._send_json({"task_id": tid})
        else:
            self._send_json({"error": "not found"}, 404)


def main() -> int:
    parser = argparse.ArgumentParser(description="Math animation wizard server")
    parser.add_argument("--port", type=int, default=8321)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"数学动画向导已启动: http://127.0.0.1:{args.port}")
    print(f"输出目录: {OUTDIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
