# dshmath-manim

DeepSeek Harness（dsh）数学动画插件 —— 基于 Manim CE 将数学概念渲染为动画视频。

「一切皆插件」：本插件以 Cordis 插件形式提供一组 **Tool**，模型通过自然语言即可生成数学动画。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│  DeepSeek Harness (dsh)                                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ dshmath-manim (TS / Cordis 插件)                     │  │
│  │   tools: list_math_templates / render_math_scene      │  │
│  │          render_math_code / validate_math_code        │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         │ spawn python3 (沙箱子进程)        │
└─────────────────────────┼───────────────────────────────────┘
                          ▼
          py/manim_runner.py（渲染执行器）
            ├── 模板系统（JSON 声明参数模式 + Python 场景代码）
            ├── AST 静态安全校验（拦截 os/import/eval 等）
            └── manim CLI 渲染（low/medium/high/ultra）
```

## 目录结构

```
dshmath-manim/
├── math-manim.cordis.yml     # 插件加载配置
├── package.json / tsconfig   # TS 插件（tools 注册）
├── src/
│   ├── index.ts              # 插件入口，注册 4 个工具
│   └── runner.ts             # TS ⇄ Python 桥接（子进程 + 超时 + 安全环境）
└── py/
    ├── manim_runner.py       # 渲染执行器（模板/校验/渲染，JSON 输出）
    └── templates/            # 数学动画模板
        ├── function_plot     # 函数绘图（一/二元函数）
        ├── derivative_tangent# 导数与切线（数值斜率）
        ├── definite_integral # 定积分（曲线下面积）
        ├── geometry          # 几何图形（三角形/圆/正多边形）
        ├── polar_plot        # 极坐标曲线（心形线等）
        └── surface_3d        # 3D 曲面（ThreeDScene）
```

## 数学动画向导（零代码使用）

面向只懂数学、不懂代码的用户。启动后浏览器打开即可使用：

```bash
python3 py/wizard_server.py --port 8321
# 打开 http://127.0.0.1:8321
```

流程：选择场景卡片（函数图像/导数切线/定积分/几何/极坐标/3D 曲面）→ 填写数学参数（全中文表单）→ 点击「生成动画」→ 预览并下载视频。全程无任何代码。

每个模板在 `py/templates/*.json` 中带有 `ui` 元数据（中文标签、参数提示、控件类型、下拉选项），向导页面由此自动生成表单。

## 提供的工具（模型可见）

| 工具 | 作用 | 适用场景 |
|---|---|---|
| `list_math_templates` | 列出模板与参数模式 | 开场发现能力 |
| `render_math_scene` | 模板参数化渲染（安全） | 推荐路径 |
| `render_math_code` | 渲染模型自写 Manim 场景 | 模板不匹配时 |
| `validate_math_code` | AST 静态安全校验 | 渲染前的自愈检查 |

## 零代码技能包（Skill，核心推荐）

插件加载时会自动向 `ctx.skills` 注册两个技能（`skills/<name>/SKILL.md`，每份都是一份完整提示词）：

| 技能 | 路径 | 定位 |
|---|---|---|
| `math-animation` | `skills/math-animation/` | **默认推荐**：模板路径。把模型训练成"数学动画翻译官"，口语 → 模板参数 → `render_math_scene` |
| `manim-codegen` | `skills/manim-codegen/` | **进阶**：自由代码路径。模板无法表达时，模型直接编写 Manim 0.19 场景代码 → `validate_math_code` → `render_math_code`，实现多步动画、物体运动、图形变换、物理模拟等无限表现力 |

**双轨自动决策**：`math-animation` 技能内置决策树，模板覆盖得了的需求走模板（安全、成功率高）；覆盖不了或连续失败时，自动加载 `manim-codegen` 切换自由代码。用户视角始终是零代码。

### 使用者视角（零代码，完全不用接触代码）

在 dsh 对话中直接说数学/物理语言即可，例如：

- 「画一个正弦函数和余弦函数在同一坐标系里的对比动画」
- 「y=x² 在 x=1 处的切线，标出导数」
- 「画出 sin x 从 0 到 π 的定积分，涂上面积」
- 「画一个蓝色三角形，标 ∠ABC」
- 「画心形线 r=1+cosθ」
- 「画马鞍面 z=x²-y²，能旋转的」
- 「弹簧振子的位移-时间图像」（物理 → 自动翻译为简谐运动曲线）

模型会加载技能 → 翻译成模板参数 → 调用 `render_math_scene` → 返回视频。超出模板时自动切换 `manim-codegen` 写代码渲染。技能内置：

- **口语 → 表达式翻译表**（"x 的平方"→`x**2`，极坐标、3D 双变量同样覆盖）
- **模板选择决策树**（需求类型 → 模板）
- **精细动画加分项**（标题智能渲染：数学公式走 LaTeX、含中文自动走 Pango 文本渲染，中文标题无忧；贴合函数形状的坐标区间、多曲线配色、low 预览→high 出片）
- **自愈循环**（参数校验/表达式/LaTeX 报错 → 自动修正重试，连续 2 次失败才询问用户）

### 技能启用方式（二选一）

```bash
# 方式 A：加载本插件，技能随插件自动注册（推荐，零配置）
dsh --patch /path/to/dshmath-manim/math-manim.cordis.yml

# 方式 B：不加载插件，直接把技能文件放入技能根目录
mkdir -p ~/.dsh/skills && cp -r skills/math-animation skills/manim-codegen ~/.dsh/skills/
```

> 技能遵循 dsh「渐进披露」：默认只向模型暴露 `name + description` 摘要（小 token），
> 模型判定需要时才通过 `skill` 工具展开完整 `<skill_content>`，不占日常对话预算。
> 用户也可直接输入 `/math-animation` 显式注入技能全文。

## 快速开始

### 1. Python 依赖

```bash
pip install manim numpy
```

### 2. 独立验证 Python 后端（无需 dsh）

```bash
# 列出模板
python3 py/manim_runner.py templates

# 渲染函数绘图（sin + x²）
python3 py/manim_runner.py render \
  --template function_plot \
  --params '{"functions": ["np.sin(x)", "x**2"], "title": "y=\\sin(x),\\ y=x^2"}' \
  --quality low --outdir out

# 校验模型代码（拦截危险调用）
python3 py/manim_runner.py validate --code 'import os; os.system("rm -rf /")'
```

### 3. 在 DeepSeek Harness 中加载

```bash
# 方式 A：本地 patch（在 dsh 仓库目录）
dsh --patch /path/to/dshmath-manim/math-manim.cordis.yml

# 方式 B：作为 npm 插件发布后按名字加载
# - insert:
#     - id: dshmath-manim
#       name: 'dshmath-manim'
```

加载后启动 `npx @deepseek-ai/dsh web`，在对话中即可使用，例如：

> "用曼哈顿比例绘制 y = sin(x) 和 y = x² 的动画，并标注函数名"

模型会调用 `list_math_templates` → `render_math_scene` 完成渲染。

## 打包与发布（让其他使用者安装）

插件是标准的 dsh bundle 包：`package.json` 声明 `dsh.bundle.patch` 指向 `math-manim.cordis.yml`，
`files` 字段保证 `dist/`（编译产物）、`py/`（Python 渲染后端与模板）、`skills/`（技能提示词）全部随包分发。

### 方式一：npm 发布（推荐，使用者一行安装）

```bash
cd dshmath-manim
npm run build            # 编译 dist/
npm publish              # 发布到 npm（会先跑 build）
# 使用者侧：
dsh plugin --profile web add dshmath-manim
```

### 方式二：tarball 交付（内部/私有分发）

```bash
npm pack                 # 生成 dshmath-manim-0.1.0.tgz
# 使用者侧：
dsh plugin add ./dshmath-manim-0.1.0.tgz
```

### 方式三：GitHub 安装

给仓库打 `dsh-plugin` 话题即可进入社区生态；使用者可 `dsh plugin add github:you/dshmath-manim`。
注意 git 安装拉取的是源码，需要 `prepare` 脚本且用户需在 profile 的 `pnpm-workspace.yaml`
`allowBuilds` 中授权构建——推荐优先用 npm / tarball 避免此门槛。

### 使用者安装后的效果

安装成功后，使用者只需在 dsh 对话中说数学/物理语言，例如「画一个蓝色三角形标 ∠ABC」或
「弹簧振子的动画」，模型会加载插件注册的两个技能（`math-animation` 模板路径 / `manim-codegen`
自由代码路径）自动生成动画。**使用者侧无需安装任何 Python 依赖** —— 但渲染需要本机已安装
`manim` + `numpy`（见上「Python 依赖」），或后续可内置自动检测提示。

## 安全模型

- **模板渲染**：参数只做 `{key}` 文本替换 + JSON 字面量序列化，**绝不 eval 模型输入**
- **模型代码**：AST 静态校验，拦截 `os`/`subprocess`/`eval`/`open` 等危险符号后才渲染
- **进程隔离**：渲染始终在 Python 子进程内执行，带超时与取消信号（`exec.signal`）
- **环境隔离**：子进程清除 IDE 注入的钩子（`CODEBUDDY_SAFE_DELETE_*`），避免 TeX 临时文件清理被拦截

## 自愈循环（与 dsh agent loop 协同）

模型写出场景 → `validate_math_code` 检查 → 失败则根据 violations 重写 → `render_math_scene`/`render_math_code` 渲染 → 渲染错误（含 LaTeX 报错）作为 tool result 回喂 → 模型修正。错误信息被裁剪到末尾 2000 字符返回，避免上下文爆炸。

## 路线图

- [x] Python 渲染后端 + 6 个数学模板（本地验证通过）
- [x] TS 插件（4 个工具注册）
- [x] 零代码技能包：`math-animation` Skill（模板路径：提示词引导参数翻译）
- [x] 进阶技能包：`manim-codegen` Skill（自由代码路径：模型直接写 Manim 场景代码）
- [ ] dsh 仓库内集成测试（需在 deepseek-harness 仓库中 pnpm 安装验证）
- [ ] UI 卡片（`presentResult` 内嵌视频预览）
- [ ] 对话式增量修改（改模板参数重渲染）
