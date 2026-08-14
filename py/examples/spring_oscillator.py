from manim import *

import numpy as np


class SpringOscillator(Scene):
    """弹簧振子简谐运动：左侧弹簧-质量块振荡，右侧同步绘制 x(t) 位移曲线。"""

    def construct(self):
        # ---------------- 物理参数 ----------------
        omega = 2 * PI / 2.0      # 角频率（周期 2 秒）
        A = 1.8                   # 振幅
        coils = 10                # 弹簧圈数

        # ---------------- 固定结构与布局 ----------------
        wall = LEFT * 4.2 + UP * 2.0
        eq = wall + RIGHT * 2.0   # 平衡位置

        ceiling = Line(wall + LEFT * 1.5, wall + RIGHT * 1.5, stroke_width=8, color=GREY_BROWN)
        hanger = Line(wall, wall + DOWN * 0.4, stroke_width=6, color=GREY_BROWN)
        eq_line = DashedLine(eq + DOWN * 1.5, eq + UP * 1.5, color=GREY, stroke_width=2,
                             dash_length=0.08, dashed_ratio=0.5)

        wall_bottom = wall + DOWN * 0.4

        # ---------------- 质量块 ----------------
        box = Square(side_length=0.8)
        box.set_fill(BLUE_E, opacity=0.9).set_stroke(WHITE, width=2)
        box.move_to(eq)

        # ---------------- 弹簧（螺旋折线） ----------------
        def spring_points(start, end, radius=0.18):
            d = end - start
            L = np.linalg.norm(d)
            if L < 1e-6:
                return [start, end]
            u = d / L
            perp = np.array([-u[1], u[0], 0.0])
            n = coils * 40
            pts = []
            for i in range(n + 1):
                frac = i / n
                along = start + u * L * frac
                if frac < 0.06 or frac > 0.94:
                    off = 0.0
                else:
                    phase = (frac - 0.06) / 0.88
                    off = radius * np.sin(phase * coils * 2 * PI)
                pts.append(along + perp * off)
            return pts

        spring = VMobject().set_stroke(YELLOW, width=4)

        # ---------------- 时间驱动与更新 ----------------
        t = ValueTracker(0)

        def refresh(mob):
            tt = t.get_value()
            x = A * np.cos(omega * tt)
            end = eq + RIGHT * x
            box.move_to(end)
            spring.set_points_as_corners(spring_points(wall_bottom, end + LEFT * 0.35))

        box.add_updater(refresh)
        spring.add_updater(refresh)

        # ---------------- 位移箭头（指向平衡位置） ----------------
        arrow = always_redraw(
            lambda: Arrow(
                box.get_center(), eq + RIGHT * 0.0,
                buff=0.15, stroke_width=5, color=RED,
            )
        )

        # ---------------- 右侧位移-时间曲线 ----------------
        axes = Axes(
            x_range=[0, 6, 1], y_range=[-2.2, 2.2, 1],
            x_length=3.6, y_length=2.8,
            axis_config={"include_numbers": True, "font_size": 14},
        ).to_corner(DR, buff=0.6)
        labels = axes.get_axis_labels(x_label="t", y_label="x")

        trace = always_redraw(
            lambda: axes.plot(
                lambda xx: A * np.cos(omega * xx),
                x_range=[0, min(6, t.get_value())],
                color=YELLOW, stroke_width=4,
            )
        )
        tracer = always_redraw(
            lambda: Dot(
                axes.coords_to_point(t.get_value(), A * np.cos(omega * t.get_value())),
                color=RED, radius=0.09,
            )
        )
        ref_curve = axes.plot(lambda xx: A * np.cos(omega * xx), x_range=[0, 6],
                              color=GREY, stroke_width=2).set_stroke(opacity=0.4)

        # ---------------- 文字 ----------------
        title = Text("弹簧振子简谐运动", font_size=42).to_edge(UP)
        formula = MathTex(r"x(t) = A\cos(\omega t)", font_size=38).to_corner(UR, buff=0.6)

        # ---------------- 播放 ----------------
        self.play(FadeIn(title))
        self.play(Create(ceiling), Create(hanger), Create(eq_line), run_time=1)
        self.play(Create(box), Create(spring), Create(ref_curve), run_time=1)
        self.play(Write(formula))
        self.add(arrow, trace, tracer)

        # 3 个周期：t 0 → 6（周期 2 秒）
        self.play(t.animate.set_value(6), run_time=6, rate_func=linear)

        self.wait(1.5)
