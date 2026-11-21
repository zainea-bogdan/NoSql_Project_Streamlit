"""Visuals: pitches (mplsoccer, wyscout coordinates 0-100, each team attacks left -> right),
heat-tables (pandas Styler), scatter and bars (plotly)."""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402
from matplotlib.cm import ScalarMappable  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from mplsoccer import Pitch  # noqa: E402

TEAM_COLORS = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd"]
ACTION_STYLE = {  # R3: colour + marker per defensive action
    "clearance": ("#1f77b4", "o"),
    "interception": ("#2ca02c", "^"),
    "duel": ("#d62728", "s"),
}
THIRDS = {"DEF": (0, 33.3), "MID": (33.3, 66.6), "ATT": (66.6, 100)}
LANES = {"LEFT": (0, 33.3), "CENTER": (33.3, 66.6), "RIGHT": (66.6, 100)}
PHASES = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90+"]
BANDS = ["U21", "21-29", "30+", "unknown"]


# ---------------------------------------------------------------- tables
def frame(rows) -> pd.DataFrame:
    """rows -> DataFrame with nested dicts flattened (location.x) and lists joined,
    mixed-type columns cast to text so Streamlit can always display them."""
    df = rows if isinstance(rows, pd.DataFrame) else pd.json_normalize(rows) if rows else pd.DataFrame()
    df = df.copy()
    for column in df.columns:
        if df[column].dtype == object:
            values = df[column].map(lambda v: ", ".join(map(str, v)) if isinstance(v, (list, tuple)) else v)
            kinds = {type(v) for v in values if v is not None and not (isinstance(v, float) and pd.isna(v))}
            df[column] = values.astype(str).replace({"None": "", "nan": ""}) if len(kinds) > 1 else values
    return df


def table(rows) -> None:
    df = frame(rows)
    if df.empty:
        st.info("No rows.")
    else:
        st.dataframe(df, hide_index=True)


def selection_table(rows: list[dict], key: str) -> list:
    """Table with a leading checkbox column 'select'; all other columns read-only. Returns selected ids."""
    df = frame(rows)
    df.insert(0, "select", False)
    edited = st.data_editor(
        df,
        key=key,
        hide_index=True,
        disabled=[c for c in df.columns if c != "select"],
        column_config={"select": st.column_config.CheckboxColumn("select", default=False)},
    )
    return [int(i) for i in edited.loc[edited["select"] == True, "id"].tolist()]  # noqa: E712


def _gradient(df, subset=None, axis=0):
    return df.style.background_gradient(cmap="RdYlGn", subset=subset, axis=axis).format(precision=2, na_rep="-")


# ---------------------------------------------------------------- pitch figures (return a matplotlib figure)
def _get(row: dict, path: str, default=None):
    cur = row
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _pitch(half=False, figsize=(8, 5.6)):
    pitch = Pitch(pitch_type="wyscout", half=half, pitch_color="#f4f6f0", line_color="#8c8c8c",
                  linewidth=1.2, line_zorder=2, pad_bottom=2, pad_top=2)
    fig, ax = pitch.draw(figsize=figsize)
    return pitch, fig, ax


def _legend_below(ax, handles, ncol):
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=ncol,
              frameon=False, fontsize=9, handletextpad=0.4, columnspacing=1.4)


def fig_shot_map(rows):
    """R1: attacking half, marker area grows with xG, each shot labelled with minute and xG."""
    pitch, fig, ax = _pitch(half=True, figsize=(7, 6))
    teams = sorted({_get(r, "team.name", "?") for r in rows})
    for i, team in enumerate(teams):
        color = TEAM_COLORS[i % len(TEAM_COLORS)]
        for r in (r for r in rows if _get(r, "team.name", "?") == team):
            x, y, xg = _get(r, "location.x", 0), _get(r, "location.y", 0), _get(r, "shot.xg", 0) or 0
            size = 80 + xg * 1400
            pitch.scatter(x, y, s=size, ax=ax, color=color, alpha=0.75, zorder=3,
                          edgecolors="black", linewidth=2 if _get(r, "shot.onTarget") else 0.8)
            ax.annotate(f"{_get(r, 'minute', '')}' | {xg:.2f}", (x, y), xytext=(size ** 0.5 / 2 + 3, 0),
                        textcoords="offset points", ha="left", va="center", fontsize=8, zorder=4,
                        bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "none", "alpha": 0.8})
    ax.set_xlim(58, 101)  # zoom on the final third
    ax.set_ylim(90, 10)  # wyscout y axis is inverted (0 = top)
    handles = [Line2D([], [], marker="o", ls="", markerfacecolor=TEAM_COLORS[i % len(TEAM_COLORS)],
                      markeredgecolor="black", markersize=9, label=t) for i, t in enumerate(teams)]
    handles += [Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor="black",
                       markeredgewidth=2, markersize=9, label="thick edge = on target")]
    _legend_below(ax, handles, ncol=len(handles))
    ax.set_title("Missed big chances (label = minute | xG, marker size = xG)", fontsize=11)
    return fig


def fig_box_actions(rows, team):
    """R3: one team's defensive actions in its own box (own goal on the left, pitch zoomed to it)."""
    pitch, fig, ax = _pitch(figsize=(6, 6))
    handles = []
    for action, (color, marker) in ACTION_STYLE.items():
        pts = [r for r in rows if _get(r, "team.name") == team and _get(r, "type.primary") == action]
        if pts:
            pitch.scatter([_get(r, "location.x", 0) for r in pts], [_get(r, "location.y", 0) for r in pts],
                          ax=ax, s=90, marker=marker, color=color, edgecolors="black", linewidth=0.6,
                          alpha=0.85, zorder=3)
            handles.append(Line2D([], [], marker=marker, ls="", markerfacecolor=color, markeredgecolor="black",
                                  markersize=9, label=f"{action} ({len(pts)})"))
    ax.set_xlim(-1, 36)  # own third only
    _legend_below(ax, handles, ncol=max(len(handles), 1))
    ax.set_title(f"{team}\nown box, goal on the left", fontsize=11)
    return fig


def fig_zone_grid(rows, team, value_key, label_fn, vmax, cmap, colorbar_label):
    """A1 / A5: 3x3 zone heatmap for one team. vmax is shared so both teams use the same colour scale."""
    pitch, fig, ax = _pitch(figsize=(8, 6))
    colormap = matplotlib.colormaps[cmap]
    norm = Normalize(vmin=0, vmax=max(vmax, 0.01))
    cells = {(r.get("third"), r.get("lane")): r for r in rows if r.get("team") == team}
    for third, (x0, x1) in THIRDS.items():
        for lane, (y0, y1) in LANES.items():
            row = cells.get((third, lane))
            value = (row or {}).get(value_key) or 0
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=colormap(norm(value)),
                                   edgecolor="white", linewidth=1.5, alpha=0.85, zorder=1))
            if row:
                ax.text((x0 + x1) / 2, (y0 + y1) / 2, label_fn(row), ha="center", va="center", fontsize=10,
                        zorder=4, bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "none", "alpha": 0.75})
    colorbar = fig.colorbar(ScalarMappable(norm=norm, cmap=colormap), ax=ax, orientation="horizontal",
                            fraction=0.045, pad=0.03, shrink=0.6)
    colorbar.set_label(colorbar_label, fontsize=9)
    ax.set_title(f"{team}   (attacking left to right →)", fontsize=12)
    return fig


def _show(fig, width="stretch") -> None:
    st.pyplot(fig, width=width)  # Streamlit already saves with dpi=200 and bbox_inches="tight"
    plt.close(fig)


def _side_by_side(teams, build):
    for column, team in zip(st.columns(max(len(teams), 1)), teams):
        with column:
            _show(build(team))


# ---------------------------------------------------------------- per-query renderers
def _r1(result):
    _show(fig_shot_map(result["rows"]), width=700)  # one pitch only: don't stretch it over the whole page
    table(result["rows"])


def _r3(result):
    rows = result["rows"]
    teams = sorted({_get(r, "team.name") for r in rows if _get(r, "team.name")})
    _side_by_side(teams, lambda team: fig_box_actions(rows, team))
    table(rows)


def _a1(result):
    rows = result["rows"]
    teams = sorted({r["team"] for r in rows if r.get("team")})
    vmax = max([r.get("xg") or 0 for r in rows] + [0])
    _side_by_side(teams, lambda team: fig_zone_grid(
        rows, team, "xg", lambda r: f"{r['actions']} action{'s' if r['actions'] != 1 else ''}\n{r['xg']:.2f} xG",
        vmax, "YlOrRd", "xG per zone"))
    table(rows)


def _a2(result):
    df = pd.DataFrame(result["rows"])
    metrics = ["passes", "passAccuracy", "finalThirdEntries", "xg", "events", "avgPassLength"]
    metric = st.selectbox("Metric", metrics, key="a2_metric")
    pivot = df.pivot_table(index="team", columns="phaseLabel", values=metric, aggfunc="first")
    pivot = pivot[[p for p in PHASES if p in pivot.columns]]
    baseline = (result.get("extra") or {}).get("baseline") or []
    if baseline:
        pivot.loc["Match average"] = baseline[0].get(metric)
    st.caption("Rows = teams, columns = 15-minute phases. The last row is the match average per team and phase.")
    st.dataframe(_gradient(pivot, axis=None))


def _a3(result):
    df = pd.DataFrame(result["rows"])
    df["size"] = df["avgGain"].fillna(0).clip(lower=0) + 2
    fig = px.scatter(df, x="passes", y="accuracy", size="size", color="role", hover_name="fullName",
                     hover_data={"age": True, "foot": True, "team": True, "progressive": True,
                                 "avgGain": True, "size": False},
                     labels={"accuracy": "pass accuracy %"}, title="Volume vs accuracy (size = avg forward gain)")
    st.plotly_chart(fig)
    cols = ["fullName", "team", "role", "foot", "age", "passes", "accuracy", "progressive", "progressiveShare", "avgGain"]
    show = df[[c for c in cols if c in df.columns]]
    st.dataframe(_gradient(show, subset=["accuracy", "progressive", "progressiveShare", "avgGain"]), hide_index=True)


def _a4(result):
    df = pd.DataFrame(result["rows"])
    pivot = df.pivot_table(index="type", columns="team", values=["possessions", "shotRate", "xgPerPossession"],
                           aggfunc="first")
    pivot.columns = [f"{team} | {metric}" for metric, team in pivot.columns]
    pivot = pivot[sorted(pivot.columns)]
    st.caption("Rows = possession type. shotRate = % of possessions ending with a shot.")
    st.dataframe(_gradient(pivot))


def _a5(result):
    rows = result["rows"]
    st.caption("PPDA = opponent passes in their own 60% / our defensive actions there. Lower = more intense press.")
    for column, r in zip(st.columns(max(len(rows), 1)), rows):
        with column:
            st.markdown(f"**{r['team']}**")
            st.metric("PPDA", r["ppda"])
            st.metric("High recoveries (x >= 60)", r["highRecoveries"])
    zones = (result.get("extra") or {}).get("zones") or []
    if zones:
        teams = sorted({r["team"] for r in zones if r.get("team")})
        vmax = max([r.get("recoveries") or 0 for r in zones] + [0])
        _side_by_side(teams, lambda team: fig_zone_grid(
            zones, team, "recoveries", lambda r: f"{r['recoveries']} rec\n{r['defActions']} def",
            vmax, "Blues", "ball recoveries per zone"))
    table(rows)


def _a6(result):
    df = pd.DataFrame(result["rows"])
    fig = px.bar(df, x="team", y="eventShare", color="band", barmode="stack",
                 category_orders={"band": BANDS}, hover_data=["players", "events", "avgAge"],
                 labels={"eventShare": "% of team events"}, title="Share of team events by age band")
    st.plotly_chart(fig)
    table(result["rows"])


RENDERERS = {
    "shot_map": _r1,
    "table": lambda r: table(r["rows"]),
    "pitch_scatter": _r3,
    "zone_heatmap": _a1,
    "heat_table": _a2,
    "scatter_profile": _a3,
    "styled_table": _a4,
    "pressing": _a5,
    "stacked_bar": _a6,
}


def render(result: dict) -> None:
    if not result.get("rows"):
        st.info("The query ran but returned no rows. Try lowering the thresholds or picking another match.")
        return
    RENDERERS.get(result.get("viz"), lambda r: table(r["rows"]))(result)
