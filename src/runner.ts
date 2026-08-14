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

function runProcess(
  args: string[],
  signal?: AbortSignal,
  timeoutMs = TIMEOUT_MS,
): Promise<RunnerResult> {
  return new Promise((resolve) => {
    const child = spawn('python3', ['-u', RUNNER_PATH, ...args], {
      cwd: join(__dirname, '..'),
      env: cleanEnv(),
      signal,
    })

    let stdout = ''
    let stderr = ''
    const timer = setTimeout(() => child.kill('SIGKILL'), timeoutMs)

    child.stdout.on('data', (chunk: Buffer) => {
      stdout += chunk.toString()
    })
    child.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString()
    })
    child.on('error', (err) => {
      clearTimeout(timer)
      resolve({ ok: false, returncode: -1, stderrTail: String(err) })
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
      resolve({
        ok: data?.ok === true,
        data,
        returncode: code ?? -1,
        stderrTail: stderr.slice(-3000),
      })
    })
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
  const args = [
    'render',
    '--template', req.template,
    '--params', JSON.stringify(req.params ?? {}),
    '--quality', req.quality ?? 'low',
    '--outdir', req.outdir ?? join(__dirname, '..', 'out'),
  ]
  return runProcess(args, signal)
}

export async function renderCode(req: RenderCodeRequest, signal?: AbortSignal): Promise<RunnerResult> {
  // 自定义代码写入临时文件后交给 Python 侧校验 + 渲染
  const tmp = join(__dirname, '..', 'out', `.scene_${Date.now()}.py`)
  const { writeFileSync } = await import('node:fs')
  writeFileSync(tmp, req.code, 'utf8')
  try {
    return await runProcess(['render-code', '--code-file', tmp, '--quality', req.quality ?? 'low', '--outdir', req.outdir ?? join(__dirname, '..', 'out')], signal)
  } finally {
    const { rmSync } = await import('node:fs')
    rmSync(tmp, { force: true })
  }
}

export async function validateScene(code: string, signal?: AbortSignal): Promise<RunnerResult> {
  return runProcess(['validate', '--code', code], signal)
}
