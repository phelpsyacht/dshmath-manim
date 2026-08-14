"""小球弹跳精细动画（manim-codegen 示例）。

特性：
- 物理模拟：自由落体 + 能量衰减反弹（每次损失 25%，速度乘 0.866），t 由 ValueTracker 驱动
- 落地挤压 / 弹起拉伸（squash & stretch）
- 动态影子（高度越高影子越小越浅）
- 运动轨迹（随时间淡出的小点）
- 实时高度标注（球上方数字 + 右侧竖直标尺）
"""
from manim import *


class BouncingBallScene(Scene):
    def construct(self):
        # ------------------------------------------------------------------
        # 布局常量
        # ------------------------------------------------------------------
        floor_y = -3.2
        start_h = 2.8          # 初始高度
        ball_r = 0.42
        ball_x = -2.6
        g = 9.8

        # 地面
        ground = Line([-6.8, floor_y, 0], [6.8, floor_y, 0], color=GREY_BROWN, stroke_width=8)
        # 竖直标尺（右侧）
        ruler = NumberLine(
            x_range=[0, 3, 0.5],
            length=6,
            color=GREY_A,
            include_numbers=True,
            font_size=16,
        ).rotate(PI / 2).move_to([5.0, floor_y + 1.5, 0])
        ruler_text = Text("高度 (m)", font_size=16, color=GREY_A).next_to(ruler, RIGHT, buff=0.15)

        ball = Dot(radius=ball_r, color=BLUE, fill_opacity=1).move_to([ball_x, floor_y + start_h, 0])
        shadow = Ellipse(width=1.0, height=0.22, color=GREY, fill_opacity=0.4).move_to([ball_x, floor_y + 0.02, 0])
        h_label = Text("", font_size=28, color=YELLOW).next_to(ball, UL, buff=0.15)
        trail = VGroup()

        title = Text("小球弹跳动画", font_size=44, color=WHITE).to_edge(UP, buff=0.6)
        subtitle = Text("能量逐次衰减的物理模拟", font_size=22, color=GREY_B).next_to(title, DOWN, buff=0.15)

        self.add(title, subtitle, ground, ruler, ruler_text, shadow, ball, h_label, trail)

        # ------------------------------------------------------------------
        # 物理模拟：给定 t 计算当前高度
        # ------------------------------------------------------------------
        def height_at(t):
            remaining = t
            v = 0.0
            h = start_h
            for _ in range(20):
                if remaining <= 0:
                    break
                t_fall = (v + np.sqrt(v * v + 2 * g * h)) / g
                if remaining < t_fall:
                    h = h - v * remaining - 0.5 * g * remaining * remaining
                    remaining = 0
                else:
                    remaining -= t_fall
                    v_ground = np.sqrt(v * v + 2 * g * h)
                    v = 0.866 * v_ground   # 能量损失 25%
                    h = 0.0
                    if v < 0.3:
                        break
            return h

        tracker = ValueTracker(0)

        # ------------------------------------------------------------------
        # Updater：球体位置 + 挤压拉伸 + 高度标签
        # ------------------------------------------------------------------
        def update_ball(mob):
            h = max(height_at(tracker.get_value()), 0)
            mob.move_to([ball_x, floor_y + h, 0])
            # 落地瞬间挤压、高空中恢复圆形
            squash = np.exp(-abs(h) * 3.0) * (1 if h < 0.25 else 0)
            mob.scale_to_fit_height(ball_r * 2 * (1 + 0.35 * squash))
            h_label.become(Text(f"{h:.2f} m", font_size=28, color=YELLOW)).next_to(mob, UL, buff=0.15)

        # ------------------------------------------------------------------
        # Updater：影子（位置 / 大小 / 透明度随高度变化）
        # ------------------------------------------------------------------
        def update_shadow(mob):
            h = max(height_at(tracker.get_value()), 0)
            mob.move_to([ball_x, floor_y + 0.02, 0])
            s = max(0.4, 1.0 - h / 3.5)
            mob.set_opacity(max(0.2, 0.5 - h / 7))
            mob.scale_to_fit_width(1.0 * s)

        # ------------------------------------------------------------------
        # Updater：轨迹（每帧加一个点，超出 26 个丢弃最旧）
        # ------------------------------------------------------------------
        def update_trail(mob):
            h = max(height_at(tracker.get_value()), 0)
            if h > 0:
                dot = Dot(radius=0.07, color=BLUE_E, fill_opacity=0.35).move_to(ball.get_center())
                mob.add(dot)
                if len(mob) > 26:
                    mob.remove(mob[0])

        ball.add_updater(update_ball)
        shadow.add_updater(update_shadow)
        trail.add_updater(update_trail)

        # ------------------------------------------------------------------
        # 开场
        # ------------------------------------------------------------------
        self.play(
            Write(title),
            Write(subtitle),
            Create(ground),
            Create(ruler),
            Write(ruler_text),
            FadeIn(ball, scale=0.5),
            FadeIn(shadow),
            run_time=1.6,
        )

        # ------------------------------------------------------------------
        # 主弹跳：tracker 从 0 匀速推进到 t_total，物理由 height_at 决定
        # ------------------------------------------------------------------
        t_total = 7.0
        self.play(tracker.animate.set_value(t_total), run_time=6.5, rate_func=smooth)

        ball.remove_updater(update_ball)
        shadow.clear_updaters()
        trail.clear_updaters()

        # ------------------------------------------------------------------
        # 结尾：轨迹定格 + 高亮
        # ------------------------------------------------------------------
        self.play(FadeToColor(ball, YELLOW), Indicate(ball, scale_factor=1.4, color=TEAL), run_time=1.0)
        self.play(FadeOut(VGroup(title, subtitle, ruler, ruler_text, trail), shift=DOWN), run_time=1.0)
        self.wait(1.5)
