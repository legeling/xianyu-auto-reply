"""
GUI 仪表盘页面模块。
"""
import tkinter as tk

from launcher.gui_theme import COLORS


def render_dashboard_page(app):
    """
    在右侧内容区渲染仪表盘页面。

    Args:
        app: LauncherApp 实例
    """
    content = app._content_frame

    container = tk.Frame(content, bg=COLORS["card_bg"])
    container.pack(fill=tk.BOTH, expand=True)

    header = tk.Frame(container, bg=COLORS["card_bg"])
    header.pack(fill=tk.X, padx=20, pady=(16, 12))
    tk.Label(
        header,
        text="仪表盘",
        font=("微软雅黑", 14, "bold"),
        fg=COLORS["text"],
        bg=COLORS["card_bg"],
    ).pack(anchor=tk.W)
    tk.Label(
        header,
        text="系统运行入口",
        font=("微软雅黑", 9),
        fg=COLORS["text_secondary"],
        bg=COLORS["card_bg"],
    ).pack(anchor=tk.W, pady=(2, 0))

    card = tk.Frame(
        container,
        bg="#ffffff",
        highlightbackground="#e2e8f0",
        highlightthickness=1,
    )
    card.pack(fill=tk.X, padx=16, pady=(0, 16))

    tk.Label(
        card,
        text="服务启动后，可在左侧菜单进入运行状态、日志和配置页面。",
        font=("微软雅黑", 10),
        fg=COLORS["text_secondary"],
        bg="#ffffff",
        padx=16,
        pady=18,
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(fill=tk.X)
