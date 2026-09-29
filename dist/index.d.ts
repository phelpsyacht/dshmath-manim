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
import type { Context } from '@deepseek-ai/cordis';
import Schema from '@deepseek-ai/schemastery';
export declare const name = "dshmath-manim";
export declare const description = "Manim CE \u6570\u5B66\u52A8\u753B\u63D2\u4EF6\uFF1A\u5C06\u6570\u5B66\u6982\u5FF5\u6E32\u67D3\u4E3A\u52A8\u753B\u89C6\u9891\uFF08\u96F6\u4EE3\u7801\u6280\u80FD\u5305\uFF09";
export declare const inject: string[];
/** 插件配置：outdir 对应 cordis.yml 中的 config.outdir，不配置时用插件 out/ 目录 */
export interface Config {
    outdir?: string;
}
/** 同名 Schema：Cordis 加载插件时据此校验配置并填充默认值 */
export declare const Config: Schema<Config>;
export declare function apply(ctx: Context, config?: Config): void;
