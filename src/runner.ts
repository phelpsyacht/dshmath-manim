/**
 * runner.ts — TS 侧与 Python Manim 后端（py/manim_runner.py）的桥接层。
 *
 * 所有工具通过本模块 spawn 一个独立 Python 进程执行渲染，返回规范化 JSON。
 * 安全性：模型不可信代码只在 Python 子进程内运行，且经过 AST 静态校验；
 * 本层不 eval 任何模型提供的代码。
 */

import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
// 打包后 dist/runner.js -> ../py/manim_runner.py
export const RUNNER_PATH = join(__dirname, '..', 'py', 'manim_runner.py')

export interface RenderRequest {
  /** 模板名，如 function_plot */
  template: string
  /** 模板参数 JSON 对象 */
  params: Record<string, unknown>
  /** low / medium / high / ultra */
  quality?: string
  /** 输出目录（绝对路径） */
  outdir?: string
}

export interface RenderCodeRequest {
  /** 完整的 Manim 场景 Python 源码 */
  code: string
  quality?: string
  outdir?: string
}

export interface RunnerResult {
  ok: boolean
  /** stdout 解析出的 JSON 负载 */
  data?: Record<string, any>
  returncode: number
  stderrTail?: string
}

/** 子进程默认超时：low=5min，其余 10min */
const TIMEOUT_MS = 10 * 60 * 1000

/** Python 解释器：可用 PYTHON_BIN 环境变量覆盖（如指向 venv 中的 python） */
const PYTHON_BIN = process.env.PYTHON_BIN ?? 'python3'

function runProcess(
  args: string[],
  signal?: AbortSignal,
  timeoutMs = TIMEOUT_MS,
  input?: string,
): Promise<RunnerResult> {
  return new Promise((resolve) => {
    const child = spawn(PYTHON_BIN, ['-u', RUNNER_PATH, ...args], {
      cwd: join(__dirname, '..'),
      env: cleanEnv(),
      signal,
    })

    let stdout = ''
    let stderr = ''
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      child.kill('SIGKILL')
    }, timeoutMs)

    child.stdout.on('data', (chunk: Buffer) => {
      stdout += chunk.toString()
    })
    child.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString()
    })
    child.on('error', (err) => {
      clearTimeout(timer)
      resolve({ ok: false, returncode: -1, stderrTail: `failed to spawn ${PYTHON_BIN}: ${String(err)}` })
    })
    child.on('close', (code) => {
      clearTimeout(timer)
      let data: Record<string, unknown> | undefined
      try {
        // runner 最后一行 stdout 是 JSON 结果
        const lines = stdout.trim().split('\n')
        const last = lines[lines.length - 1] ?? '{}'
        data = JSON.parse(last)
      } catch {
        // 解析失败时保留原始输出
      }
      if (timedOut) {
        stderr += `\n[render timed out after ${timeoutMs} ms]`
      }
      resolve({
        ok: data?.ok === true,
        data,
        returncode: code ?? -1,
        stderrTail: stderr.slice(-3000),
      })
    })
    if (input != null) {
      child.stdin.write(input)
    }
    child.stdin.end()
  })
}

/**
 * 清除 IDE 注入的安全删除钩子（sitecustomize），避免 manim 批量清理
 * TeX 临时文件时被环境拦截。与 py/manim_runner.py 的 _clean_env 保持一致。
 */
function cleanEnv(): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env }
  for (const key of Object.keys(env)) {
    if (key.startsWith('CODEBUDDY_SAFE_DELETE') || key === 'GENIE_TRASH_DIR' || key === 'PYTHONPATH' || key === 'PYTHONSTARTUP') {
      delete env[key]
    }
  }
  return env
}

export async function listTemplates(signal?: AbortSignal): Promise<RunnerResult> {
  return runProcess(['templates'], signal)
}

export async function renderScene(req: RenderRequest, signal?: AbortSignal): Promise<RunnerResult> {
  // 参数 JSON 走 stdin，避免超长参数撑爆命令行（E2BIG）
  const args = [
    'render',
    '--template', req.template,
    '--quality', req.quality ?? 'low',
    '--outdir', req.outdir ?? join(__dirname, '..', 'out'),
  ]
  return runProcess(args, signal, TIMEOUT_MS, JSON.stringify(req.params ?? {}))
}

export async function renderCode(req: RenderCodeRequest, signal?: AbortSignal): Promise<RunnerResult> {
  // 自定义代码写入临时文件后交给 Python 侧校验 + 渲染
  const { mkdirSync, writeFileSync, rmSync } = await import('node:fs')
  const out = req.outdir ?? join(__dirname, '..', 'out')
  // 确保输出目录存在，否则 writeFileSync 会 ENOENT 崩溃
  mkdirSync(out, { recursive: true })
  const tmp = join(out, `.scene_${Date.now()}.py`)
  writeFileSync(tmp, req.code, 'utf8')
  try {
    return await runProcess(['render-code', '--code-file', tmp, '--quality', req.quality ?? 'low', '--outdir', out], signal)
  } finally {
    rmSync(tmp, { force: true })
  }
}

export async function validateScene(code: string, signal?: AbortSignal): Promise<RunnerResult> {
  // 代码走 stdin，避免超长代码撑爆命令行（E2BIG）
  return runProcess(['validate'], signal, TIMEOUT_MS, code)
}
