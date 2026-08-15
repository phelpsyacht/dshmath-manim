/**
 * index.ts — dshmath-manim 插件入口。
 *
 * 注册一组数学动画工具（基于 Manim CE），模型可通过自然语言生成数学动画。
 *
 * 用法（在 dsh 配置中加载）：
 *   - insert:
 *       - id: dshmath-manim
 *         name: 'dshmath-manim'
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { listTemplates, renderScene, renderCode, validateScene } from './runner.js'
import { registerSkills } from './skill.js'

export const name = 'dshmath-manim'
export const description = 'Manim CE 数学动画插件：将数学概念渲染为动画视频（零代码技能包）'

export const inject = ['tools', 'skills']

/** 插件配置：outdir 对应 cordis.yml 中的 config.outdir，不配置时用插件 out/ 目录 */
export interface PluginConfig {
  outdir?: string
}

export function apply(ctx: Context, config: PluginConfig = {}) {
  // ---------------------------------------------------------------------
  // 技能包 — 零代码提示词引导（面向不懂代码的用户）
  //   math-animation：模板路径（默认推荐）
  //   manim-codegen：自由代码路径（模型直接写 Manim 场景）
  // ---------------------------------------------------------------------
  registerSkills(ctx)

  // ---------------------------------------------------------------------
  // list_templates — 列出可用数学模板及参数模式
  // ---------------------------------------------------------------------
  ctx.tools.register(
    defineTool({
      name: 'list_math_templates',
      description:
        'List available math animation templates (function plots, derivatives, integrals, geometry, polar, 3D surfaces). Use this first to discover what the math plugin can render.',
      parameters: {},
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args, value: any) => {
          const templates = value?.templates ?? {}
          const lines = Object.entries(templates).map(([k, v]: any) => {
            const required = Object.entries(v?.parameters ?? {})
              .filter(([, s]: any) => s.required)
              .map(([pk]) => pk)
            return `- ${k}: ${v?.description ?? ''}${required.length ? ` (required: ${required.join(', ')})` : ''}`
          })
          return [{ type: 'text', text: `Available math templates:\n${lines.join('\n') || '(none)'}` }]
        },
      },
      async execute(_args, exec) {
        const res = await listTemplates(exec.signal)
        if (!res.ok || !res.data) {
          throw new Error(`Failed to list templates: ${res.stderrTail ?? 'unknown error'}`)
        }
        return res.data
      },
    }),
  )

  // ---------------------------------------------------------------------
  // render_math_scene — 用模板渲染数学动画（推荐，安全）
  // ---------------------------------------------------------------------
  ctx.tools.register(
    defineTool({
      name: 'render_math_scene',
      description:
        'Render a math animation video from a template. Pick a template with list_math_templates, then pass its parameters. Returns the video file path on success.',
      parameters: {
        template: { type: 'string', required: true, description: 'Template name, e.g. "function_plot"' },
        params: {
          type: 'object',
          additionalProperties: true,
          description: 'Template parameters as a JSON object, e.g. {"functions": ["np.sin(x)", "x**2"]}',
        },
        quality: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'ultra'],
          description: 'Render quality. Use "low" for quick preview, "high" for final output.',
        },
        outdir: { type: 'string', description: 'Output directory. Defaults to plugin out/.' },
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args, value: any) => [
          {
            type: 'text',
            text: value?.ok
              ? `Rendered ${value.template} to ${value.video} (${(value.size_bytes ?? 0) / 1024} KB, quality=${value.quality})`
              : `Render failed: ${value?.error ?? 'unknown error'}`,
          },
        ],
      },
      async execute(args, exec) {
        const res = await renderScene(
          {
            template: args.template,
            params: (args.params ?? {}) as Record<string, unknown>,
            quality: args.quality ?? 'low',
            outdir: args.outdir ?? config.outdir,
          },
          exec.signal,
        )
        if (!res.data) {
          throw new Error(`render_math_scene: ${res.stderrTail ?? 'no output'}`)
        }
        return res.data
      },
    }),
  )

  // ---------------------------------------------------------------------
  // render_math_code — 直接渲染模型自写的 Manim 场景（进阶，经安全校验）
  // ---------------------------------------------------------------------
  ctx.tools.register(
    defineTool({
      name: 'render_math_code',
      description:
        'Render an arbitrary Manim CE scene from model-written Python source. The code is statically safety-checked before running. Use this when no template fits; prefer render_math_scene otherwise.',
      parameters: {
        code: { type: 'string', required: true, description: 'Complete Manim Python scene source code (class extending Scene).' },
        quality: { type: 'string', enum: ['low', 'medium', 'high', 'ultra'], description: 'Render quality. Default low.' },
        outdir: { type: 'string', description: 'Output directory. Defaults to plugin out/.' },
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args, value: any) => [
          {
            type: 'text',
            text: value?.ok
              ? `Rendered custom scene to ${value.video}`
              : `Render failed: ${value?.error ?? 'unknown error'}`,
          },
        ],
      },
      async execute(args, exec) {
        const res = await renderCode({ code: args.code, quality: args.quality ?? 'low', outdir: args.outdir ?? config.outdir }, exec.signal)
        if (!res.data) {
          throw new Error(`render_math_code: ${res.stderrTail ?? 'no output'}`)
        }
        return res.data
      },
    }),
  )

  // ---------------------------------------------------------------------
  // validate_math_code — 静态安全校验（供自愈循环使用）
  // ---------------------------------------------------------------------
  ctx.tools.register(
    defineTool({
      name: 'validate_math_code',
      description:
        'Static safety-check Manim Python code without rendering. Returns a list of violations. Use before render_math_code to catch dangerous imports or calls.',
      parameters: {
        code: { type: 'string', required: true, description: 'Manim scene source code to validate.' },
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args, value: any) => [
          {
            type: 'text',
            text: value?.ok
              ? 'Code passed static validation.'
              : `Code rejected: ${(value?.violations ?? []).join('; ')}`,
          },
        ],
      },
      async execute(args, exec) {
        const res = await validateScene(args.code, exec.signal)
        if (!res.data) {
          throw new Error(`validate_math_code: ${res.stderrTail ?? 'no output'}`)
        }
        return res.data
      },
    }),
  )
}
