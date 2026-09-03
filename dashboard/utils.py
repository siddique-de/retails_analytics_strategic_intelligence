"""
Shared utility helpers for the Streamlit dashboard.
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Brand colours ─────────────────────────────────────────────────────────────
PRIMARY   = "#1B4F72"
SECONDARY = "#2E86C1"
ACCENT    = "#F39C12"
SUCCESS   = "#27AE60"
DANGER    = "#E74C3C"
NEUTRAL   = "#7F8C8D"
BG_DARK   = "#0E1117"

PALETTE   = px.colors.qualitative.Bold
SEQ_BLUE  = px.colors.sequential.Blues
SEQ_RED   = px.colors.sequential.Reds

REGION_COLORS = {
    "US":  "#2E86C1", "AU": "#27AE60", "UK": "#8E44AD",
    "EE":  "#F39C12", "RU": "#E74C3C", "UAE":"#16A085",
}


def fmt_currency(v, prefix="$", decimals=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if abs(v) >= 1e9:  return f"{prefix}{v/1e9:.{decimals}f}B"
    if abs(v) >= 1e6:  return f"{prefix}{v/1e6:.{decimals}f}M"
    if abs(v) >= 1e3:  return f"{prefix}{v/1e3:.{decimals}f}K"
    return f"{prefix}{v:,.0f}"


def fmt_pct(v, decimals=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{decimals}f}%"


def fmt_num(v, decimals=0):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:,.{decimals}f}"


def kpi_card(col, label: str, value: str, delta: str = None,
             delta_color: str = "normal", help: str = None):
    """Render a metric card in a Streamlit column."""
    col.metric(label=label, value=value, delta=delta,
               delta_color=delta_color, help=help)


def gauge(value: float, title: str, min_val=0, max_val=100,
          threshold_good=70, threshold_warn=40) -> go.Figure:
    color = SUCCESS if value >= threshold_good else (ACCENT if value >= threshold_warn else DANGER)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis":  {"range": [min_val, max_val]},
            "bar":   {"color": color},
            "steps": [
                {"range": [min_val, threshold_warn],  "color": "#FADBD8"},
                {"range": [threshold_warn, threshold_good], "color": "#FDEBD0"},
                {"range": [threshold_good, max_val],  "color": "#D5F5E3"},
            ],
            "threshold": {"line": {"color": PRIMARY, "width": 3},
                          "thickness": 0.75, "value": threshold_good},
        },
        number={"suffix": "%", "font": {"size": 24}},
    ))
    fig.update_layout(height=220, margin=dict(t=40, b=10, l=20, r=20),
                      paper_bgcolor="rgba(0,0,0,0)", font_color="white")
    return fig


def waterfall(labels, values, title="") -> go.Figure:
    colors = [SUCCESS if v >= 0 else DANGER for v in values]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=["relative"] * len(values),
        x=labels, y=values,
        connector={"line": {"color": NEUTRAL}},
        increasing={"marker": {"color": SUCCESS}},
        decreasing={"marker": {"color": DANGER}},
    ))
    fig.update_layout(title=title, height=360,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_color="white", showlegend=False)
    return fig


def sparkline(series: pd.Series, color=SECONDARY) -> go.Figure:
    fig = go.Figure(go.Scatter(y=series, mode="lines",
                               line=dict(color=color, width=2), fill="tozeroy",
                               fillcolor=f"rgba(46,134,193,0.15)"))
    fig.update_layout(height=80, margin=dict(t=0,b=0,l=0,r=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      showlegend=False)
    return fig


def apply_dark_theme(fig: go.Figure, height: int = 400) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(14,17,23,0.6)",
        font=dict(color="white", size=12),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="white")),
        margin=dict(t=50, b=40, l=40, r=20),
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.15)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.15)"),
    )
    return fig

