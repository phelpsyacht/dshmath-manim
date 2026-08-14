/**
 * skill.ts — 数学动画技能（Skill）注册。
 *
 * 面向"不懂代码、只懂数学物理"的用户：插件在加载时向 `ctx.skills` 注册
 * skills/ 目录下的全部技能：
 *   - math-animation  零代码技能包（默认推荐：模板路径）
 *   - manim-codegen   进阶技能包（自由代码：模型直接写 Manim 场景代码）
 *
 * 每个技能正文都是一份完整提示词（SKILL.md），引导模型完成特定工作流。
 * 内容单一来源：skills/<name>/SKILL.md（同时可直接作为本地文件技能放入
 * ~/.dsh/skills 或项目 .dsh/skills 使用，无需本插件）。
 */

import { readdirSync, readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import type { Context } from '@deepseek-ai/cordis'
import type { SkillRegistration } from '@deepseek-ai/dsh-skill'

const __dirname = dirname(fileURLToPath(import.meta.url))
/** 编译后 dist/skill.js → 项目根上一级；技能位于项目根 skills/ 下。 */
export const SKILLS_DIR = join(__dirname, '..', 'skills')

export interface MathAnimationSkill {
  name: string
  description: string
  whenToUse?: string
  content: string
}

/** 解析单个 SKILL.md：剥离 frontmatter，返回可注册的技能定义。 */
function parseSkillFile(file: string, fallbackName: string): MathAnimationSkill {
  const raw = readFileSync(file, 'utf8')
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(raw)
  if (!match) {
    return { name: fallbackName, description: `Skill ${fallbackName}`, content: raw }
  }
  const meta: Record<string, string> = {}
  for (const line of match[1].split('\n')) {
    const idx = line.indexOf(':')
    if (idx > 0) {
      const key = line.slice(0, idx).trim()
      const value = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '')
      meta[key] = value
    }
  }
  return {
    name: meta.name ?? fallbackName,
    description: meta.description ?? `Skill ${fallbackName}`,
    whenToUse: meta.whenToUse || undefined,
    content: match[2].trim(),
  }
}

/**
 * 扫描 skills/ 目录并解析全部技能。
 * 支持两种形态（与 dsh-skill-filesystem 一致）：
 *   - 目录 bundle：<root>/<name>/SKILL.md
 *   - 扁平文件：<root>/<name>.md
 */
export function listSkills(): MathAnimationSkill[] {
  const out: MathAnimationSkill[] = []
  if (!existsSync(SKILLS_DIR)) return out
  for (const entry of readdirSync(SKILLS_DIR, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      const file = join(SKILLS_DIR, entry.name, 'SKILL.md')
      if (existsSync(file)) out.push(parseSkillFile(file, entry.name))
    } else if (entry.isFile() && entry.name.endsWith('.md')) {
      out.push(parseSkillFile(join(SKILLS_DIR, entry.name), entry.name.replace(/\.md$/, '')))
    }
  }
  return out
}

/**
 * 在运行时注册全部数学动画技能。
 * 运行时技能固定使用 rank 250：项目 provider 能覆盖它，它又能覆盖
 * custom/user 根的本地技能；同层同名先到先得。
 */
export function registerSkills(ctx: Context) {
  for (const skill of listSkills()) {
    const registration: SkillRegistration = {
      ...skill,
      source: 'runtime',
      provider: 'math-manim',
      invocation: { modelInvocable: true, userInvocable: true },
    }
    ctx.skills.register(registration)
  }
}
