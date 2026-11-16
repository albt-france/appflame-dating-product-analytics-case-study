"""Matplotlib chart helpers shared by the PDF report. Every chart returns an inline SVG string."""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from common import BLUE, BLUE_LIGHT, BORDER, CARD, GREY, GREY_LIGHT, INK, INK2, MUTED, RED  # noqa: E402

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "axes.edgecolor": BORDER,
    "axes.labelcolor": INK2,
    "axes.titlesize": 11,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": BORDER,
    "grid.linewidth": 0.6,
    "figure.facecolor": CARD,
    "axes.facecolor": CARD,
    "svg.fonttype": "none",      # keep text as text in the SVG
    "svg.hashsalt": "casestudy",    # deterministic ids
})


def fig(w_px, h_px):
    f, ax = plt.subplots(figsize=(w_px / 96, h_px / 96), dpi=96)
    return f, ax


def to_svg(f):
    buf = io.StringIO()
    f.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.05, metadata={"Date": None, "Creator": None})
    plt.close(f)
    s = buf.getvalue()
    s = s[s.index("<svg"):]
    return s.replace("<svg ", '<svg class="chart" ', 1)


def pct_axis(ax, axis="y", digits=0):
    fmt = FuncFormatter(lambda v, _: f"{v * 100:.{digits}f}%")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def thousands_axis(ax, axis="y"):
    def short(v, _):
        for div, unit in ((1e6, "M"), (1e3, "K")):
            if abs(v) >= div:
                return f"{v / div:.1f}".rstrip("0").rstrip(".") + unit   # 1500 -> 1.5K, 2000 -> 2K
        return f"{v:.0f}"
    fmt = FuncFormatter(short)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def waterfall(steps, w, h, start_color=GREY, end_color=BLUE):
    """steps: list of (label, value, kind) with kind 'total' or 'delta'. Horizontal bars, read top to bottom."""
    f, ax = fig(w, h)
    running, rows = 0, []
    for i, (label, value, kind) in enumerate(steps):
        if kind == "total":
            left, width = 0, value
            color = end_color if i == len(steps) - 1 else start_color
            running = value
        else:
            left = running if value >= 0 else running + value
            width = abs(value)
            color = BLUE_LIGHT if value >= 0 else RED
            running += value
        rows.append((label, left, width, color, value, kind))
    y = list(range(len(rows)))[::-1]
    for yy, (label, left, width, color, value, kind) in zip(y, rows):
        ax.barh(yy, width, left=left, color=color, height=0.62, edgecolor=CARD, linewidth=1)
        txt = f"{value:,.0f}" if kind == "total" else f"{value:+,.0f}"
        ax.text(left + width + max(r[1] + r[2] for r in rows) * 0.01, yy, txt, va="center", ha="left",
                fontsize=10, color=INK, fontweight="bold" if kind == "total" else "normal")
    ax.set_yticks(y, [r[0] for r in rows], fontsize=9.5, color=INK2)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(r[1] + r[2] for r in rows) * 1.12)
    thousands_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    return to_svg(f)


def hbar(labels, values, w, h, color=BLUE, fmt="{:,.0f}", highlight=None, highlight_color=RED, xpct=False):
    f, ax = fig(w, h)
    y = list(range(len(labels)))[::-1]
    colors = [highlight_color if highlight and lab in highlight else color for lab in labels]
    ax.barh(y, values, color=colors, height=0.62)
    for yy, v in zip(y, values):
        ax.text(v + max(values) * 0.01, yy, fmt.format(v), va="center", fontsize=9, color=INK)
    ax.set_yticks(y, labels, fontsize=9.5, color=INK2)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, max(values) * 1.15)
    if xpct:
        pct_axis(ax, "x")
    else:
        thousands_axis(ax, "x")
    return to_svg(f)


__all__ = ["fig", "to_svg", "pct_axis", "thousands_axis", "waterfall", "hbar", "plt",
           "BLUE", "BLUE_LIGHT", "GREY", "GREY_LIGHT", "INK", "INK2", "MUTED", "RED", "CARD", "BORDER"]
