"""spring_mass_oscillator.py — 弹簧振荡系统（简谐运动）动画场景。

展示一个质量-弹簧系统：
  - 固定支撑墙
  - 随位移伸缩的螺旋弹簧
  - 在水平导轨上往复运动的质量块
  - 平衡位置标记与位移箭头
  - 右下角同步绘制 x(t) 位移-时间曲线
"""
from manim import *
import math
import numpy as np


def spring_points(start, end, turns=12, amplitude=0.4):
    """返回从 start 到 end 的一条螺旋弹簧折线的关键点（2D）。"""
    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    dx = x1 - x0
    # 沿弹簧轴向的坐标
    n = turns * 4
    pts = []
    for i in range(n + 1):
        t = i / n
        x = x0 + dx * t
        # 垂直轴向的横向偏移（正弦摆动）
        sway = amplitude * math.sin(2 * math.pi * turns * t)
        pts.append(np.array([x, y0 + sway, 0]))
    return pts


class SpringMassScene(Scene):
    def construct(self):
        amplitude = 3.0        # 振荡幅度
        omega = 2.0            # 角频率 rad/s
        natural_len = 3.0      # 弹簧自然长度

        # 位移随时间变化: x(t) = amplitude * cos(omega t)
        def x_at(t):
            return amplitude * math.cos(omega * t)

        # ---- 固定支撑墙（左侧） ----
        wall = Rectangle(width=0.4, height=3.2, color=GREY_BROWN, fill_opacity=1)
        wall.move_to(LEFT * 5.4)
        wall_label = MathTex("m", font_size=44).next_to(wall, LEFT, buff=0.2)
        self.play(FadeIn(wall, shift=RIGHT), Write(wall_label))
        self.wait(0.3)

        # ---- 平衡位置虚线 + 标记 ----
        eq_line = DashedLine(
            start=LEFT * 2.6 + UP * 1.2,
            end=LEFT * 2.6 + DOWN * 1.2,
            dash_length=0.12,
            color=GREY,
        )
        eq_label = MathTex("x=0", font_size=30).next_to(eq_line, DOWN, buff=0.1)
        self.play(Create(eq_line), Write(eq_label))

        # ---- 质量块（初始在最右端 x = amplitude） ----
        block = Square(side_length=1.0, color=BLUE, fill_opacity=0.8)
        initial_pos = LEFT * 2.6 + RIGHT * amplitude
        block.move_to(initial_pos)
        self.play(Create(block))

        # ---- 螺旋弹簧（随位移伸缩） ----
        spring = VMobject(color=YELLOW, stroke_width=4)
        spring.set_points_smoothly(spring_points(wall.get_right(), block.get_left()))

        def update_spring():
            pts = spring_points(wall.get_right(), block.get_left())
            spring.set_points_smoothly(pts)

        update_spring()
        self.play(Create(spring), run_time=0.8)

        # ---- 导轨 ----
        rail = Line(LEFT * 5.6, RIGHT * 1.4, color=GREY_A, stroke_width=2)
        rail.move_to(block.get_bottom() - DOWN * 0.15)
        self.play(Create(rail))

        # ---- 位移-时间曲线坐标轴（右下角小图） ----
        axes = Axes(
            x_range=[0, 4.5, 1],
            y_range=[-amplitude - 0.5, amplitude + 0.5, 1],
            x_length=2.6,
            y_length=1.6,
            axis_config={"include_numbers": False, "font_size": 16},
        ).to_corner(DOWN + RIGHT, buff=0.3)
        axes_xlabel = MathTex("t", font_size=22).next_to(axes.x_axis, DOWN, buff=0.05)
        axes_ylabel = MathTex("x(t)", font_size=22).next_to(axes.y_axis, LEFT, buff=0.05)
        self.play(Create(axes), Write(axes_xlabel), Write(axes_ylabel))

        # ---- 位移箭头、轨迹曲线、运动点的静态容器 ----
        arrow = Arrow(LEFT * 2.6, block.get_center(), buff=0.1, color=RED, stroke_width=4)
        trace = VMobject(color=GREEN, stroke_width=3)
        dot = Dot(axes.coords_to_point(0, x_at(0)), color=GREEN, radius=0.08)

        # ---- ValueTracker 驱动时间，所有动态元素 always_redraw ----
        tracker = ValueTracker(0)
        total_time = 4.0

        # 质量块随 t 振荡
        moving_block = always_redraw(
            lambda: block.move_to(LEFT * 2.6 + RIGHT * x_at(tracker.get_value()))
        )
        # 弹簧随块伸缩
        moving_spring = always_redraw(
            lambda: spring.set_points_smoothly(
                spring_points(wall.get_right(), block.get_left())
            )
        )
        # 位移箭头（从平衡位置指向块）
        moving_arrow = always_redraw(
            lambda: arrow.put_start_and_end_on(LEFT * 2.6, block.get_center())
        )
        disp_label = always_redraw(
            lambda: MathTex("x", font_size=36, color=RED).next_to(arrow, UP, buff=0.05)
        )
        # 位移-时间轨迹曲线
        trace_points = []

        def trace_redraw():
            pts = [axes.coords_to_point(t, x_at(t)) for t in np.linspace(0, tracker.get_value(), 200)]
            return trace.set_points_smoothly(pts)

        moving_trace = always_redraw(trace_redraw)
        # 轨迹小图上的运动点
        moving_dot = always_redraw(
            lambda: dot.move_to(axes.coords_to_point(tracker.get_value(), x_at(tracker.get_value())))
        )

        # 一次性创建动态元素，驱动动画
        dynamic = VGroup(spring, arrow, trace, dot)
        self.add(dynamic)
        self.play(
            tracker.animate.set_value(total_time),
            run_time=total_time,
            rate_func=linear,
        )

        self.wait(1.5)
