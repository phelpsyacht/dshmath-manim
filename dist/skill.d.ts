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
import type { Context } from '@deepseek-ai/cordis';
/** 编译后 dist/skill.js → 项目根上一级；技能位于项目根 skills/ 下。 */
export declare const SKILLS_DIR: string;
export interface MathAnimationSkill {
    name: string;
    description: string;
    whenToUse?: string;
    content: string;
}
/**
 * 扫描 skills/ 目录并解析全部技能。
 * 支持两种形态（与 dsh-skill-filesystem 一致）：
 *   - 目录 bundle：<root>/<name>/SKILL.md
 *   - 扁平文件：<root>/<name>.md
 */
export declare function listSkills(): MathAnimationSkill[];
/**
 * 在运行时注册全部数学动画技能。
 * 运行时技能固定使用 rank 250：项目 provider 能覆盖它，它又能覆盖
 * custom/user 根的本地技能；同层同名先到先得。
 */
export declare function registerSkills(ctx: Context): void;
