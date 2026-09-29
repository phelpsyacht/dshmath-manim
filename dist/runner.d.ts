/**
 * runner.ts — TS 侧与 Python Manim 后端（py/manim_runner.py）的桥接层。
 *
 * 所有工具通过本模块 spawn 一个独立 Python 进程执行渲染，返回规范化 JSON。
 * 安全性：模型不可信代码只在 Python 子进程内运行，且经过 AST 静态校验；
 * 本层不 eval 任何模型提供的代码。
 */
export declare const RUNNER_PATH: string;
export interface RenderRequest {
    /** 模板名，如 function_plot */
    template: string;
    /** 模板参数 JSON 对象 */
    params: Record<string, unknown>;
    /** low / medium / high / ultra */
    quality?: string;
    /** 输出目录（绝对路径） */
    outdir?: string;
}
export interface RenderCodeRequest {
    /** 完整的 Manim 场景 Python 源码 */
    code: string;
    quality?: string;
    outdir?: string;
}
export interface RunnerResult {
    ok: boolean;
    /** stdout 解析出的 JSON 负载 */
    data?: Record<string, any>;
    returncode: number;
    stderrTail?: string;
}
export declare function listTemplates(signal?: AbortSignal): Promise<RunnerResult>;
export declare function renderScene(req: RenderRequest, signal?: AbortSignal): Promise<RunnerResult>;
export declare function renderCode(req: RenderCodeRequest, signal?: AbortSignal): Promise<RunnerResult>;
export declare function validateScene(code: string, signal?: AbortSignal): Promise<RunnerResult>;
