"""Matplotlib financial charts generator for FRA investor reports."""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless server/worker
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)

# Professional palette
COLOR_PRIMARY = "#1E40AF"    # Deep Royal Blue
COLOR_SECONDARY = "#0D9488"  # Teal
COLOR_ACCENT = "#F59E0B"     # Amber
COLOR_HIGHLIGHT = "#6366F1"  # Indigo
COLOR_BG = "#F8FAFC"         # Soft slate background


def generate_revenue_trend_chart(
    periods_data: List[Dict[str, Any]],
    output_path: Path,
) -> Path:
    """Generates a high-resolution chart showing Revenue and Net Income quarterly trend."""
    labels = [f"{p.get('period_type', '')} '{str(p.get('fiscal_year', ''))[-2:]}" for p in periods_data]
    revenues = [p.get("items", {}).get("revenue", 0.0) for p in periods_data]
    net_incomes = [p.get("items", {}).get("net_income", 0.0) for p in periods_data]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(8, 4.5), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax1.set_facecolor(COLOR_BG)

    # Bar chart for revenue
    rects1 = ax1.bar(x - width/2, revenues, width, label="Revenue ($M)", color=COLOR_PRIMARY, edgecolor="none", alpha=0.9)
    rects2 = ax1.bar(x + width/2, net_incomes, width, label="Net Income ($M)", color=COLOR_SECONDARY, edgecolor="none", alpha=0.9)

    ax1.set_ylabel("USD (Millions)", fontsize=11, fontweight="bold", color="#1F2937")
    ax1.set_title("Quarterly Revenue & Net Income Trajectory", fontsize=13, fontweight="bold", pad=15, color="#111827")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=10, fontweight="semibold", color="#374151")
    ax1.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E5E7EB", fontsize=10)
    ax1.grid(axis="y", linestyle="--", alpha=0.5, color="#CBD5E1")
    ax1.set_axisbelow(True)

    # Clean borders
    for spine in ["top", "right", "left", "bottom"]:
        ax1.spines[spine].set_color("#E2E8F0")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved revenue trend chart to {output_path}")
    return output_path


def generate_margins_chart(
    periods_data: List[Dict[str, Any]],
    output_path: Path,
) -> Path:
    """Generates a line chart showing Net Margin and ROE progression."""
    labels = [f"{p.get('period_type', '')} '{str(p.get('fiscal_year', ''))[-2:]}" for p in periods_data]
    
    net_margins = []
    roes = []
    for p in periods_data:
        ratios = p.get("computed_ratios", {})
        nm = ratios.get("net_margin")
        roe = ratios.get("roe")
        net_margins.append(nm * 100 if nm is not None else 0.0)
        roes.append(roe * 100 if roe is not None else 0.0)

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor(COLOR_BG)

    ax.plot(labels, net_margins, marker="o", linewidth=2.5, color=COLOR_SECONDARY, label="Net Margin (%)")
    ax.plot(labels, roes, marker="s", linewidth=2.5, color=COLOR_ACCENT, label="Return on Equity (%)")

    ax.set_ylabel("Percentage (%)", fontsize=11, fontweight="bold", color="#1F2937")
    ax.set_title("Profitability & Return Dynamics (Net Margin vs ROE)", fontsize=13, fontweight="bold", pad=15, color="#111827")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E5E7EB", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5, color="#CBD5E1")
    ax.set_axisbelow(True)

    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_color("#E2E8F0")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved margins trend chart to {output_path}")
    return output_path


def generate_peer_comparison_chart(
    companies_data: List[Dict[str, Any]],
    target_ticker: str,
    output_path: Path,
) -> Path:
    """Generates a horizontal bar chart benchmarking Net Margin across peer companies."""
    tickers = [c["ticker"] for c in companies_data]
    margins = [(c.get("net_margin") or 0.0) * 100 for c in companies_data]

    colors = [
        COLOR_PRIMARY if t.upper() == target_ticker.upper() else "#94A3B8"
        for t in tickers
    ]

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor(COLOR_BG)

    y_pos = np.arange(len(tickers))
    bars = ax.barh(y_pos, margins, color=colors, height=0.55, edgecolor="none")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(tickers, fontsize=11, fontweight="bold", color="#1F2937")
    ax.invert_yaxis()  # top-down ranking
    ax.set_xlabel("Net Margin (%)", fontsize=11, fontweight="bold", color="#1F2937")
    ax.set_title(f"Peer Net Margin Comparison (Highlight: {target_ticker})", fontsize=13, fontweight="bold", pad=15, color="#111827")
    ax.grid(axis="x", linestyle="--", alpha=0.5, color="#CBD5E1")
    ax.set_axisbelow(True)

    # Label bar values
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.1f}%",
            ha="left",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="#334155",
        )

    for spine in ["top", "right", "left", "bottom"]:
        ax.spines[spine].set_color("#E2E8F0")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved peer comparison chart to {output_path}")
    return output_path
