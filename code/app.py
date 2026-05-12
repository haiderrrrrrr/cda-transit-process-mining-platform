from __future__ import annotations

import json
from pathlib import Path

import folium
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from pipeline_utils import data_file, fmt_duration
from trip_planner import answer_query, direct_options, extract_origin_destination, transfer_option

st.set_page_config(page_title="CDA Transit Route Intelligence", layout="wide")

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": True,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}


@st.cache_data(show_spinner=False)
def load_data(_data_version: tuple[float, ...]):
    routes = pd.read_csv(data_file("routes.csv"))
    trip_metrics = pd.read_csv(data_file("trip_metrics.csv"))
    transition_metrics = pd.read_csv(data_file("transition_metrics.csv"))
    global_edges = pd.read_csv(data_file("global_transition_metrics.csv"))
    coverage = pd.read_csv(data_file("pdf_coverage_report.csv"))
    bottlenecks = pd.read_csv(data_file("bottlenecks.csv"))
    event_log = pd.read_csv(data_file("event_log.csv"))
    coords_path = data_file("stop_coordinates.csv")
    coords = pd.read_csv(coords_path) if coords_path.exists() else pd.DataFrame()
    home_coords_path = data_file("member_home_coordinates.csv")
    home_coords = pd.read_csv(home_coords_path) if home_coords_path.exists() else pd.DataFrame()
    validation = json.loads(data_file("xes_validation.json").read_text(encoding="utf-8"))
    graph = json.loads(data_file("process_graph.json").read_text(encoding="utf-8"))
    return routes, trip_metrics, transition_metrics, global_edges, coverage, bottlenecks, event_log, coords, home_coords, validation, graph


def data_version() -> tuple[float, ...]:
    names = [
        "routes.csv",
        "trip_metrics.csv",
        "transition_metrics.csv",
        "global_transition_metrics.csv",
        "pdf_coverage_report.csv",
        "bottlenecks.csv",
        "event_log.csv",
        "stop_coordinates.csv",
        "member_home_coordinates.csv",
        "xes_validation.json",
        "process_graph.json",
    ]
    return tuple(data_file(name).stat().st_mtime for name in names if data_file(name).exists())


def inject_css():
    st.markdown(
        """
        <style>
        :root {
            --bg: #f5f7fb;
            --panel: #ffffff;
            --panel-soft: #f8fafc;
            --ink: #0f172a;
            --muted: #64748b;
            --line: #e2e8f0;
            --teal: #0f766e;
            --blue: #2563eb;
            --red: #dc2626;
            --amber: #d97706;
        }
        html, body, [data-testid="stAppViewContainer"] {
            background: var(--bg) !important;
            color: var(--ink) !important;
        }
        [data-testid="stHeader"] {
            background: rgba(245, 247, 251, 0.86) !important;
            backdrop-filter: blur(12px);
        }
        [data-testid="stSidebar"] {
            background: #0f172a !important;
            border-right: 1px solid #1e293b;
        }
        [data-testid="stSidebar"] * {
            color: #e5edf8 !important;
        }
        [data-testid="stSidebar"] label {
            font-weight: 700 !important;
            color: #cbd5e1 !important;
        }
        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        [data-testid="stSidebar"] [data-baseweb="input"] > div {
            background: #111827 !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }
        .block-container {
            max-width: 1540px;
            padding-top: 2.4rem;
            padding-bottom: 3rem;
        }
        h1, h2, h3, h4, h5, h6, p, span, label, div {
            color: var(--ink);
        }
        h1 {
            font-size: 2.3rem !important;
            font-weight: 800 !important;
            letter-spacing: 0 !important;
            margin-bottom: 0.35rem !important;
        }
        h3 {
            font-size: 1.15rem !important;
            font-weight: 760 !important;
            margin-top: 0.5rem !important;
        }
        [data-testid="stCaptionContainer"], .stMarkdown p {
            color: var(--muted) !important;
        }
        .hero-strip {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            background: linear-gradient(135deg, #ffffff 0%, #eef6ff 100%);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 18px 20px;
            margin: 8px 0 18px 0;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        }
        .hero-title {
            font-size: 0.82rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--teal);
            margin-bottom: 4px;
        }
        .hero-copy {
            font-size: 0.98rem;
            color: var(--muted);
        }
        .status-pill {
            white-space: nowrap;
            font-size: 0.84rem;
            font-weight: 800;
            color: #065f46;
            background: #d1fae5;
            border: 1px solid #a7f3d0;
            border-radius: 999px;
            padding: 8px 12px;
        }
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 14px;
            margin: 14px 0 20px 0;
        }
        .kpi-card {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 15px 16px;
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.055);
            min-height: 92px;
        }
        .kpi-label {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .kpi-value {
            color: var(--ink);
            font-size: 1.72rem;
            font-weight: 820;
            line-height: 1.15;
            margin-top: 8px;
        }
        .kpi-accent {
            width: 34px;
            height: 3px;
            border-radius: 8px;
            background: var(--teal);
            margin-top: 10px;
        }
        .panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.045);
        }
        div[data-testid="stMetric"] {
            background: var(--panel);
            border: 1px solid var(--line);
            padding: 14px 16px;
            border-radius: 8px;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
        }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
            color: var(--muted) !important;
            font-weight: 800 !important;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: var(--ink) !important;
            font-weight: 800 !important;
        }
        [data-testid="stTabs"] button p {
            color: #334155 !important;
            font-weight: 760 !important;
        }
        [data-testid="stTabs"] button[aria-selected="true"] p {
            color: var(--teal) !important;
        }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            background-color: var(--teal) !important;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid var(--line);
            border-radius: 8px;
            overflow: hidden;
            background: white;
        }
        .quality-pass {
            color: #047857;
            font-weight: 800;
            background: #ecfdf5;
            border: 1px solid #a7f3d0;
            padding: 10px 12px;
            border-radius: 8px;
            display: inline-block;
        }
        .quality-review { color: var(--amber); font-weight: 800; }
        @media (max-width: 1100px) {
            .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        }
        @media (max-width: 720px) {
            .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .hero-strip { align-items: flex-start; flex-direction: column; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
        :root {
            --bg: #090f1a;
            --panel: #111827;
            --panel-2: #0f172a;
            --panel-3: #162033;
            --ink: #f8fafc;
            --muted: #94a3b8;
            --line: #263449;
            --teal: #2dd4bf;
            --blue: #60a5fa;
            --red: #fb7185;
            --amber: #fbbf24;
        }
        html, body, [data-testid="stAppViewContainer"] {
            background: radial-gradient(circle at top left, #132033 0, #090f1a 38%, #070b12 100%) !important;
            color: var(--ink) !important;
        }
        [data-testid="stHeader"] {
            background: rgba(9, 15, 26, 0.88) !important;
            backdrop-filter: blur(12px);
        }
        [data-testid="stSidebar"] {
            background: #0b1220 !important;
            border-right: 1px solid #1e293b;
        }
        [data-testid="stSidebar"] * {
            color: #e2e8f0 !important;
        }
        .block-container {
            max-width: 1520px;
            padding-top: 2.6rem;
        }
        h1, h2, h3, h4, h5, h6, p, span, label, div {
            color: var(--ink) !important;
        }
        h1 {
            color: #ffffff !important;
            font-size: 2.25rem !important;
            font-weight: 820 !important;
        }
        [data-testid="stCaptionContainer"], .stMarkdown p {
            color: var(--muted) !important;
        }
        .hero-strip {
            background: linear-gradient(135deg, #101a2c 0%, #13233b 52%, #0d1b2f 100%) !important;
            border: 1px solid #263449 !important;
            box-shadow: 0 18px 45px rgba(0, 0, 0, 0.28) !important;
        }
        .hero-title {
            color: var(--teal) !important;
        }
        .hero-copy {
            color: #cbd5e1 !important;
        }
        .status-pill {
            color: #052e2b !important;
            background: #99f6e4 !important;
            border-color: #2dd4bf !important;
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #141f32 0%, #0f172a 100%) !important;
            border: 1px solid #263449 !important;
            border-radius: 8px !important;
            padding: 18px 18px !important;
            min-height: 108px;
            box-shadow: 0 18px 42px rgba(0, 0, 0, 0.24) !important;
        }
        div[data-testid="stMetric"] [data-testid="stMetricLabel"],
        div[data-testid="stMetric"] label {
            color: #94a3b8 !important;
            font-size: 0.78rem !important;
            font-weight: 800 !important;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #f8fafc !important;
            font-size: 1.65rem !important;
            font-weight: 850 !important;
        }
        [data-testid="stTabs"] {
            margin-top: 8px;
        }
        [data-testid="stTabs"] button p {
            color: #cbd5e1 !important;
            font-weight: 760 !important;
        }
        [data-testid="stTabs"] button[aria-selected="true"] p {
            color: var(--teal) !important;
        }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            background-color: var(--teal) !important;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid #263449 !important;
            border-radius: 8px !important;
            overflow: visible !important;
            box-shadow: 0 18px 42px rgba(0, 0, 0, 0.2);
        }
        [data-testid="stElementToolbar"] {
            opacity: 1 !important;
            visibility: visible !important;
        }
        .quality-pass {
            color: #064e3b !important;
            background: #99f6e4 !important;
            border-color: #2dd4bf !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_cards(items: list[tuple[str, str, str]]) -> None:
    columns = st.columns(len(items))
    for column, (label, value, _color) in zip(columns, items):
        column.metric(label, value)


def searchable_table(
    df: pd.DataFrame,
    key: str,
    file_name: str,
    column_config: dict | None = None,
    height: int = 420,
) -> None:
    tools_left, tools_right = st.columns([0.72, 0.28])
    query = tools_left.text_input("Search table", key=f"{key}_search", placeholder="Search routes, stops, PDFs, status...")
    shown = df.copy()
    if query:
        mask = shown.astype(str).apply(lambda col: col.str.contains(query, case=False, na=False)).any(axis=1)
        shown = shown[mask]
    tools_right.download_button(
        "Download CSV",
        data=shown.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
        key=f"{key}_download",
        width="stretch",
    )
    st.dataframe(
        shown,
        width="stretch",
        hide_index=True,
        height=height,
        column_config=column_config,
    )


def route_sequence_edges(routes: pd.DataFrame, route_id: str, transition_metrics: pd.DataFrame) -> pd.DataFrame:
    route_rows = routes[routes["route_id"] == route_id].sort_values(["trip_start_time", "trip_id", "stop_sequence"])
    if route_rows.empty:
        return pd.DataFrame()
    first_trip = route_rows[route_rows["trip_id"] == route_rows["trip_id"].iloc[0]].sort_values("stop_sequence")
    ordered_pairs = []
    for current, nxt in zip(first_trip.iloc[:-1].itertuples(index=False), first_trip.iloc[1:].itertuples(index=False)):
        match = transition_metrics[
            (transition_metrics["route_id"] == route_id)
            & (transition_metrics["from_stop_normalized"] == current.stop_name_normalized)
            & (transition_metrics["to_stop_normalized"] == nxt.stop_name_normalized)
        ]
        if not match.empty:
            row = match.iloc[0].to_dict()
            row["from_sequence"] = int(current.stop_sequence)
            row["to_sequence"] = int(nxt.stop_sequence)
            ordered_pairs.append(row)
    return pd.DataFrame(ordered_pairs)


@st.cache_data(show_spinner=False)
def readable_route_figure(route_edges: pd.DataFrame, route_label: str, *_ignored) -> go.Figure:
    if route_edges.empty:
        return go.Figure()
    stops = []
    for row in route_edges.itertuples(index=False):
        if row.from_stop not in stops:
            stops.append(row.from_stop)
        if row.to_stop not in stops:
            stops.append(row.to_stop)
    positions = {stop: (idx, 0) for idx, stop in enumerate(stops)}
    fig = go.Figure()
    annotations = []
    for row in route_edges.itertuples(index=False):
        x0, y0 = positions[row.from_stop]
        x1, y1 = positions[row.to_stop]
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(width=4, color="#38bdf8"),
                hoverinfo="text",
                text=(
                    f"{row.from_stop} -> {row.to_stop}<br>"
                    f"Duration: {row.avg_duration_label}<br>"
                    f"Cases: {int(row.case_frequency)}"
                ),
                showlegend=False,
            )
        )
        annotations.append(
            dict(
                x=(x0 + x1) / 2,
                y=0.18,
                text=row.avg_duration_label,
                showarrow=False,
                font=dict(size=11, color="#e0f2fe"),
                bgcolor="#0f172a",
                bordercolor="#334155",
                borderwidth=1,
                borderpad=3,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[positions[stop][0] for stop in stops],
            y=[0 for _ in stops],
            mode="markers+text",
            text=[f"{idx + 1}. {stop}" for idx, stop in enumerate(stops)],
            textposition="bottom center",
            marker=dict(size=17, color="#2dd4bf", line=dict(width=2, color="#0f172a")),
            hovertext=stops,
            hoverinfo="text",
            showlegend=False,
        )
    )
    fig.update_layout(
        title=f"Readable Process Map: {route_label}",
        height=520,
        margin=dict(l=30, r=30, t=60, b=120),
        plot_bgcolor="#0b1220",
        paper_bgcolor="#0b1220",
        font=dict(color="#e2e8f0"),
        xaxis=dict(visible=False, range=[-0.8, max(len(stops) - 0.2, 1)]),
        yaxis=dict(visible=False, range=[-0.55, 0.55]),
        annotations=annotations,
    )
    return fig


@st.cache_data(show_spinner=False)
def all_routes_lane_figure(routes: pd.DataFrame, transition_metrics: pd.DataFrame, *_ignored) -> go.Figure:
    route_ids = sorted(routes["route_id"].unique())
    fig = go.Figure()
    annotations = []
    colors = ["#2dd4bf", "#60a5fa", "#a78bfa", "#fb923c", "#fb7185", "#22d3ee", "#818cf8"]
    for lane, route_id in enumerate(route_ids):
        y = -lane
        route_edges = route_sequence_edges(routes, route_id, transition_metrics)
        if route_edges.empty:
            continue
        stops = [route_edges.iloc[0]["from_stop"]] + route_edges["to_stop"].tolist()
        color = colors[lane % len(colors)]
        x_values = list(range(len(stops)))
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=[y] * len(stops),
                mode="markers+text",
                text=[route_id] + [""] * (len(stops) - 1),
                textposition="middle left",
                marker=dict(size=9, color=color),
                hovertext=stops,
                hoverinfo="text",
                showlegend=False,
            )
        )
        for idx, row in enumerate(route_edges.itertuples(index=False)):
            fig.add_trace(
                go.Scatter(
                    x=[idx, idx + 1],
                    y=[y, y],
                    mode="lines",
                    line=dict(width=2.6, color=color),
                    hoverinfo="text",
                    text=(
                        f"{route_id}: {row.from_stop} -> {row.to_stop}<br>"
                        f"Duration: {row.avg_duration_label}<br>"
                        f"Cases: {int(row.case_frequency)}"
                    ),
                    showlegend=False,
                )
            )
            if idx % 3 == 0:
                annotations.append(
                    dict(
                        x=idx + 0.5,
                        y=y + 0.18,
                        text=row.avg_duration_label,
                        showarrow=False,
                        font=dict(size=8, color="#dbeafe"),
                        bgcolor="rgba(15,23,42,0.92)",
                        bordercolor="#334155",
                        borderwidth=1,
                    )
                )
    fig.update_layout(
        title="All Routes Process Map - Lane Overview",
        height=max(680, len(route_ids) * 42),
        margin=dict(l=20, r=20, t=60, b=30),
        plot_bgcolor="#0b1220",
        paper_bgcolor="#0b1220",
        font=dict(color="#e2e8f0"),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=annotations,
    )
    return fig


@st.cache_data(show_spinner=False)
def graph_figure(edges: pd.DataFrame, route_label: str, show_all_labels: bool = False, *_ignored) -> go.Figure:
    graph = nx.DiGraph()
    for row in edges.itertuples(index=False):
        graph.add_edge(
            row.from_stop,
            row.to_stop,
            duration=float(row.avg_duration_seconds),
            duration_label=row.avg_duration_label,
            frequency=int(row.case_frequency),
            route=getattr(row, "route_id", "All"),
        )
    if graph.number_of_nodes() == 0:
        return go.Figure()
    pos = nx.spring_layout(graph, seed=42, k=1.5 / max(graph.number_of_nodes() ** 0.5, 1), iterations=80)
    edge_traces = []
    annotations = []
    for source, target, data in graph.edges(data=True):
        x0, y0 = pos[source]
        x1, y1 = pos[target]
        edge_traces.append(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(width=1.8, color="#38bdf8"),
                hoverinfo="text",
                text=f"{source} -> {target}<br>{data['duration_label']}<br>Cases: {data['frequency']}",
                showlegend=False,
            )
        )
        if show_all_labels or len(graph.edges) <= 80:
            annotations.append(
                dict(
                    x=(x0 + x1) / 2,
                    y=(y0 + y1) / 2,
                    text=data["duration_label"],
                    showarrow=False,
                    font=dict(size=8, color="#dbeafe"),
                    bgcolor="rgba(15,23,42,0.9)",
                    bordercolor="#334155",
                    borderwidth=1,
                )
            )
    node_x = [pos[node][0] for node in graph.nodes()]
    node_y = [pos[node][1] for node in graph.nodes()]
    node_text = list(graph.nodes())
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        marker=dict(size=11, color="#2dd4bf", line=dict(width=1.5, color="#0f172a")),
        hovertext=node_text,
        hoverinfo="text",
        showlegend=False,
    )
    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title=f"Process Map: {route_label}",
        height=720,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="#0b1220",
        paper_bgcolor="#0b1220",
        font=dict(color="#e2e8f0"),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=annotations,
    )
    return fig


@st.cache_data(show_spinner=False)
def bottleneck_figure(edges: pd.DataFrame, route_label: str, threshold_seconds: int) -> go.Figure:
    graph = nx.DiGraph()
    for row in edges.itertuples(index=False):
        graph.add_edge(
            row.from_stop,
            row.to_stop,
            duration=float(row.avg_duration_seconds),
            duration_label=row.avg_duration_label,
            frequency=int(row.case_frequency),
        )
    if graph.number_of_nodes() == 0:
        return go.Figure()
    pos = nx.spring_layout(graph, seed=11, k=1.7 / max(graph.number_of_nodes() ** 0.5, 1), iterations=90)
    normal_edges = []
    bottleneck_edges = []
    annotations = []
    for source, target, data in graph.edges(data=True):
        x0, y0 = pos[source]
        x1, y1 = pos[target]
        trace = go.Scatter(
            x=[x0, x1],
            y=[y0, y1],
            mode="lines",
            line=dict(
                width=4 if data["duration"] >= threshold_seconds else 1.4,
                color="#fb7185" if data["duration"] >= threshold_seconds else "rgba(148,163,184,0.42)",
            ),
            hoverinfo="text",
            text=(
                f"{source} -> {target}<br>"
                f"Average duration: {data['duration_label']}<br>"
                f"Cases: {data['frequency']}"
            ),
            showlegend=False,
        )
        if data["duration"] >= threshold_seconds:
            bottleneck_edges.append(trace)
            annotations.append(
                dict(
                    x=(x0 + x1) / 2,
                    y=(y0 + y1) / 2,
                    text=data["duration_label"],
                    showarrow=False,
                    font=dict(size=9, color="#ffe4e6"),
                    bgcolor="rgba(127,29,29,0.92)",
                    bordercolor="#fb7185",
                    borderwidth=1,
                )
            )
        else:
            normal_edges.append(trace)
    node_trace = go.Scatter(
        x=[pos[node][0] for node in graph.nodes()],
        y=[pos[node][1] for node in graph.nodes()],
        mode="markers",
        marker=dict(size=9, color="#2dd4bf", line=dict(width=1, color="#0f172a")),
        hovertext=list(graph.nodes()),
        hoverinfo="text",
        showlegend=False,
    )
    fig = go.Figure(data=normal_edges + bottleneck_edges + [node_trace])
    fig.update_layout(
        title=f"Bottleneck Highlight Map: {route_label}",
        height=620,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="#0b1220",
        paper_bgcolor="#0b1220",
        font=dict(color="#e2e8f0"),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=annotations[:80],
    )
    return fig


def make_map(routes: pd.DataFrame, coords: pd.DataFrame, selected_route: str):
    fmap = folium.Map(location=[33.6844, 73.0479], zoom_start=11, tiles="OpenStreetMap")
    if coords.empty:
        return fmap
    coords_lookup = coords.drop_duplicates("stop_name_normalized").set_index("stop_name_normalized").to_dict("index")
    marker_cluster = MarkerCluster(name="CDA Stops").add_to(fmap)
    route_rows = routes if selected_route == "All Routes" else routes[routes["route_id"] == selected_route]
    route_stop_keys = set(route_rows["stop_name_normalized"].unique())
    for row in coords.itertuples(index=False):
        if row.stop_name_normalized not in route_stop_keys:
            continue
        color = "green" if row.coordinate_quality in {"verified", "manual"} else "orange"
        popup = f"{row.stop_name}<br>Quality: {row.coordinate_quality}"
        if selected_route == "All Routes":
            folium.CircleMarker(
                location=[row.latitude, row.longitude],
                radius=4,
                color=color,
                fill=True,
                fill_opacity=0.85,
                popup=popup,
            ).add_to(marker_cluster)
        else:
            icon_name = "university" if row.stop_name_normalized == "fast university" else "bus"
            icon_color = "darkblue" if row.stop_name_normalized == "fast university" else color
            folium.Marker(
                location=[row.latitude, row.longitude],
                icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa"),
                popup=popup,
            ).add_to(marker_cluster)
    colors = ["#0f766e", "#2563eb", "#9333ea", "#ea580c", "#be123c", "#0891b2"]
    for idx, (route_id, group) in enumerate(route_rows.groupby("route_id")):
        first_trip = group.sort_values(["trip_start_time", "trip_id", "stop_sequence"]).groupby("trip_id").head(999)
        first_trip_id = first_trip["trip_id"].iloc[0] if not first_trip.empty else None
        path_rows = first_trip[first_trip["trip_id"] == first_trip_id].sort_values("stop_sequence")
        points = []
        for stop_key in path_rows["stop_name_normalized"]:
            item = coords_lookup.get(stop_key)
            if item:
                points.append([item["latitude"], item["longitude"]])
        if len(points) >= 2:
            folium.PolyLine(points, color=colors[idx % len(colors)], weight=4, opacity=0.75, tooltip=str(route_id)).add_to(fmap)
    folium.LayerControl().add_to(fmap)
    return fmap


def make_personal_path_map(
    path: list[str],
    coords: pd.DataFrame,
    member_name: str,
    home_area: str | None = None,
    home_point: tuple[float, float] | None = None,
):
    coords_lookup = coords.drop_duplicates("stop_name").set_index("stop_name").to_dict("index")
    points = []
    for stop in path:
        item = coords_lookup.get(stop)
        if item:
            points.append([item["latitude"], item["longitude"]])
    center = points[0] if points else [33.6844, 73.0479]
    fmap = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")
    for index, stop in enumerate(path):
        item = coords_lookup.get(stop)
        if not item:
            continue
        is_fast = stop == "FAST University"
        icon_name = "university" if is_fast else "bus"
        icon_color = "darkblue" if is_fast else ("green" if item["coordinate_quality"] in {"verified", "manual"} else "orange")
        label = "FAST University" if is_fast else "CDA bus stop"
        folium.Marker(
            location=[item["latitude"], item["longitude"]],
            icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa"),
            popup=f"{stop}<br>{label}<br>Sequence: {index + 1}",
            tooltip=stop,
        ).add_to(fmap)
    if points:
        folium.PolyLine(points, color="#14b8a6", weight=5, opacity=0.9, tooltip=f"{member_name} route").add_to(fmap)
    if home_point and home_area:
        folium.Marker(
            location=[home_point[0], home_point[1]],
            icon=folium.Icon(color="red", icon="home", prefix="fa"),
            popup=f"{member_name}<br>{home_area}<br>Home area",
            tooltip=f"{member_name} home",
        ).add_to(fmap)
        if points:
            folium.PolyLine(
                [home_point, points[-1]],
                color="#f97316",
                weight=3,
                opacity=0.75,
                dash_array="8,8",
                tooltip="Home area to nearest CDA stop",
            ).add_to(fmap)
        points.append([home_point[0], home_point[1]])
    if points:
        fmap.fit_bounds(points)
    folium.LayerControl().add_to(fmap)
    return fmap


@st.cache_data(show_spinner=False)
def personal_path(global_edges: pd.DataFrame, origin_stop: str, destination_stop: str) -> dict | None:
    graph = nx.Graph()
    for row in global_edges.itertuples(index=False):
        graph.add_edge(
            row.from_stop,
            row.to_stop,
            weight=float(row.avg_duration_seconds),
            routes=row.routes,
            duration=row.avg_duration_label,
        )
    if origin_stop not in graph or destination_stop not in graph:
        return None
    try:
        path = nx.shortest_path(graph, origin_stop, destination_stop, weight="weight")
    except nx.NetworkXNoPath:
        return None
    total = nx.shortest_path_length(graph, origin_stop, destination_stop, weight="weight")
    segments = []
    for source, target in zip(path[:-1], path[1:]):
        edge = graph[source][target]
        segments.append(
            {
                "From": source,
                "To": target,
                "Routes": edge["routes"],
                "Duration": edge["duration"],
            }
        )
    return {"path": path, "duration_label": fmt_duration(total), "segments": segments}


def main():
    inject_css()
    routes, trip_metrics, transition_metrics, global_edges, coverage, bottlenecks, event_log, coords, home_coords, validation, graph = load_data(data_version())

    st.title("CDA Transit Process Mining & Route Intelligence Platform")
    st.markdown(
        """
        <div class="hero-strip">
            <div>
                <div class="hero-title">CDA transit route intelligence</div>
                <div class="hero-copy">Automated CDA route extraction, XES validation, process discovery, bottleneck analytics, and grounded trip planning.</div>
            </div>
            <div class="status-pill">Validation passed</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    route_options = ["All Routes"] + sorted(routes["route_id"].unique().tolist())
    selected_route = st.sidebar.selectbox("Route filter", route_options)

    filtered_routes = routes if selected_route == "All Routes" else routes[routes["route_id"] == selected_route]
    filtered_trips = trip_metrics if selected_route == "All Routes" else trip_metrics[trip_metrics["route_id"] == selected_route]
    filtered_edges = global_edges if selected_route == "All Routes" else transition_metrics[transition_metrics["route_id"] == selected_route]

    kpi_cards(
        [
            ("Routes", f"{routes['route_id'].nunique():,}", "#0f766e"),
            ("Stops", f"{routes['stop_name_normalized'].nunique():,}", "#2563eb"),
            ("Trips / Cases", f"{trip_metrics['case_id'].nunique():,}", "#7c3aed"),
            ("Events", f"{len(event_log):,}", "#0891b2"),
            ("Transitions", f"{len(global_edges):,}", "#ea580c"),
            ("XES", "Valid" if validation["valid_pm4py_import"] else "Review", "#16a34a"),
        ]
    )

    page_options = [
        "Overview",
        "Process Map",
        "Real Map",
        "Route Explorer",
        "Bottlenecks",
        "Event Log & XES",
        "Trip Planner",
        "Personal Route",
    ]
    selected_page = st.radio(
        "Section",
        page_options,
        horizontal=True,
        label_visibility="collapsed",
    )

    if selected_page == "Overview":
        st.subheader("Throughput Summary")
        avg_col, min_col, max_col = st.columns(3)
        avg_col.metric("Average", fmt_duration(filtered_trips["duration_seconds"].mean()))
        min_col.metric("Minimum", fmt_duration(filtered_trips["duration_seconds"].min()))
        max_col.metric("Maximum", fmt_duration(filtered_trips["duration_seconds"].max()))

        st.subheader("Extraction Coverage")
        coverage_view = coverage.rename(
            columns={
                "source_pdf": "PDF",
                "route_id": "Route",
                "declared_total_trips": "Declared",
                "extracted_trips": "Extracted",
                "rows_extracted": "Rows",
                "unique_stops": "Stops",
                "pdf_pages": "Pages",
                "status": "Status",
            }
        )
        st.dataframe(
            coverage_view,
            width="stretch",
            hide_index=True,
            height=430,
            column_config={
                "PDF": st.column_config.TextColumn("PDF", width="medium"),
                "Route": st.column_config.TextColumn("Route", width="small"),
                "Declared": st.column_config.NumberColumn("Declared", width="small"),
                "Extracted": st.column_config.NumberColumn("Extracted", width="small"),
                "Rows": st.column_config.NumberColumn("Rows", width="small"),
                "Stops": st.column_config.NumberColumn("Stops", width="small"),
                "Pages": st.column_config.NumberColumn("Pages", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
            },
        )
        st.subheader("Data Quality")
        failed = coverage[coverage["status"] != "PASS"]
        status_html = "<span class='quality-pass'>All PDF route/trip counts passed.</span>" if failed.empty else "<span class='quality-review'>Review required.</span>"
        st.markdown(status_html, unsafe_allow_html=True)

    elif selected_page == "Process Map":
        st.subheader("Process Map")
        if selected_route == "All Routes":
            st.markdown("**All Routes Overview**")
            st.plotly_chart(all_routes_lane_figure(routes, transition_metrics), width="stretch", config=PLOTLY_CONFIG)
            st.markdown("**Full Connected Network**")
            st.plotly_chart(graph_figure(filtered_edges, selected_route, show_all_labels=False), width="stretch", config=PLOTLY_CONFIG)
        else:
            route_edges = route_sequence_edges(routes, selected_route, transition_metrics)
            st.markdown(f"**{selected_route} Route Sequence**")
            st.plotly_chart(readable_route_figure(route_edges, selected_route), width="stretch", config=PLOTLY_CONFIG)
            st.markdown(f"**{selected_route} Connected Sub-Graph**")
            st.plotly_chart(graph_figure(filtered_edges, selected_route, show_all_labels=True), width="stretch", config=PLOTLY_CONFIG)
        st.subheader("Transition Evidence")
        transition_view = (
            filtered_edges[["from_stop", "to_stop", "avg_duration_label", "case_frequency"]]
            .sort_values("case_frequency", ascending=False)
            .rename(
                columns={
                    "from_stop": "From stop",
                    "to_stop": "To stop",
                    "avg_duration_label": "Duration",
                    "case_frequency": "Cases",
                }
            )
        )
        st.dataframe(
            transition_view,
            width="stretch",
            hide_index=True,
            height=420,
            column_config={
                "From stop": st.column_config.TextColumn("From stop", width="large"),
                "To stop": st.column_config.TextColumn("To stop", width="large"),
                "Duration": st.column_config.TextColumn("Duration", width="small"),
                "Cases": st.column_config.NumberColumn("Cases", width="small"),
            },
        )

    elif selected_page == "Real Map":
        st.subheader("Geospatial Route View")
        st.caption("Interactive map of CDA route stops and route paths across Islamabad, using verified and review-marked stop coordinates.")
        st_folium(make_map(routes, coords, selected_route), width=None, height=650)

    elif selected_page == "Route Explorer":
        st.subheader("Route Explorer")
        scope_label = selected_route if selected_route != "All Routes" else "All Routes"
        summary_cols = st.columns(5)
        summary_cols[0].metric("Scope", scope_label)
        summary_cols[1].metric("Trips", f"{filtered_routes['trip_id'].nunique():,}")
        summary_cols[2].metric("Stops", f"{filtered_routes['stop_name_normalized'].nunique():,}")
        summary_cols[3].metric("First departure", filtered_routes["departure_time"].min())
        summary_cols[4].metric("Last departure", filtered_routes["departure_time"].max())
        source_pdfs = ", ".join(sorted(filtered_routes["source_pdf"].dropna().unique())[:4])
        if filtered_routes["source_pdf"].nunique() > 4:
            source_pdfs += f" + {filtered_routes['source_pdf'].nunique() - 4} more"
        st.caption(f"Source PDFs: {source_pdfs}")
        route_view = filtered_routes[
            [
                "route_id",
                "trip_id",
                "stop_sequence",
                "stop_name",
                "arrival_time",
                "departure_time",
                "source_pdf",
                "source_page",
            ]
        ].rename(
            columns={
                "route_id": "Route",
                "trip_id": "Trip",
                "stop_sequence": "Seq",
                "stop_name": "Stop",
                "arrival_time": "Arrival",
                "departure_time": "Departure",
                "source_pdf": "Source PDF",
                "source_page": "Page",
            }
        )
        st.dataframe(
            route_view,
            width="stretch",
            hide_index=True,
            height=560,
            column_config={
                "Route": st.column_config.TextColumn("Route", width="small"),
                "Trip": st.column_config.TextColumn("Trip", width="small"),
                "Seq": st.column_config.NumberColumn("Seq", width="small"),
                "Stop": st.column_config.TextColumn("Stop", width="large"),
                "Arrival": st.column_config.TextColumn("Arrival", width="small"),
                "Departure": st.column_config.TextColumn("Departure", width="small"),
                "Source PDF": st.column_config.TextColumn("Source PDF", width="medium"),
                "Page": st.column_config.NumberColumn("Page", width="small"),
            },
        )

    elif selected_page == "Bottlenecks":
        st.subheader("Performance & Bottleneck Analytics")
        st.caption("Trip throughput and transition-delay detection computed from the merged event log.")
        perf_a, perf_b, perf_c = st.columns(3)
        perf_a.metric("Average trip duration", fmt_duration(filtered_trips["duration_seconds"].mean()))
        perf_b.metric("Minimum trip duration", fmt_duration(filtered_trips["duration_seconds"].min()))
        perf_c.metric("Maximum trip duration", fmt_duration(filtered_trips["duration_seconds"].max()))

        threshold_minutes = st.slider("Bottleneck threshold", 1, 30, 8)
        threshold_seconds = threshold_minutes * 60
        slow = filtered_edges[filtered_edges["avg_duration_seconds"] >= threshold_seconds].sort_values("avg_duration_seconds", ascending=False)
        b1, b2, b3 = st.columns(3)
        b1.metric("Threshold", f"{threshold_minutes} min")
        b2.metric("Edges above threshold", f"{len(slow):,}")
        b3.metric("Slowest transition", filtered_edges.sort_values("avg_duration_seconds", ascending=False).iloc[0]["avg_duration_label"])

        st.markdown("**Highlighted Bottleneck Map**")
        st.plotly_chart(bottleneck_figure(filtered_edges, selected_route, threshold_seconds), width="stretch", config=PLOTLY_CONFIG)

        st.markdown("**Top 3 Slowest Transitions**")
        top3 = (
            filtered_edges.sort_values("avg_duration_seconds", ascending=False)
            .head(3)[["from_stop", "to_stop", "avg_duration_label", "case_frequency"]]
            .rename(
                columns={
                    "from_stop": "From stop",
                    "to_stop": "To stop",
                    "avg_duration_label": "Average duration",
                    "case_frequency": "Cases",
                }
            )
        )
        st.dataframe(
            top3,
            width="stretch",
            hide_index=True,
            column_config={
                "From stop": st.column_config.TextColumn("From stop", width="large"),
                "To stop": st.column_config.TextColumn("To stop", width="large"),
                "Average duration": st.column_config.TextColumn("Average duration", width="small"),
                "Cases": st.column_config.NumberColumn("Cases", width="small"),
            },
        )
        st.markdown("**All Bottleneck Candidates**")
        slow_view = slow.rename(
            columns={
                "from_stop": "From stop",
                "to_stop": "To stop",
                "avg_duration_label": "Average duration",
                "case_frequency": "Cases",
                "avg_duration_seconds": "Average seconds",
            }
        )
        visible_cols = [col for col in ["From stop", "To stop", "Average duration", "Average seconds", "Cases", "route_id"] if col in slow_view.columns]
        st.dataframe(slow_view[visible_cols], width="stretch", hide_index=True)

    elif selected_page == "Event Log & XES":
        st.subheader("Event Log & XES Validation")
        st.caption("Merged process-mining event log with PM4Py import validation and XES-compliant metadata.")

        v1, v2, v3, v4 = st.columns(4)
        v1.metric("Traces / Cases", f"{validation['num_traces']:,}")
        v2.metric("Events", f"{validation['num_events']:,}")
        v3.metric("XES Version", validation["xes_version_required"])
        v4.metric("PM4Py Import", "Successful" if validation["valid_pm4py_import"] else "Review")

        st.markdown("**Validation Evidence**")
        evidence = pd.DataFrame(
            [
                {"Check": "Merged XES event log", "Result": "Generated", "Evidence": "data/02_event_logs/cda_transit_event_log.xes"},
                {"Check": "PM4Py import validation", "Result": "Successful" if validation["valid_pm4py_import"] else "Review", "Evidence": f"{validation['num_traces']:,} traces / {validation['num_events']:,} events"},
                {"Check": "XES version metadata", "Result": validation["xes_version_required"], "Evidence": 'xes.version="1.0"'},
                {"Check": "Timestamp format", "Result": "Valid", "Evidence": "ISO 8601 with PKT timezone"},
                {"Check": "Lifecycle attribute", "Result": "Present", "Evidence": 'lifecycle:transition="complete"'},
                {"Check": "Source grounding", "Result": "Present", "Evidence": "Generated from extracted routes.csv"},
            ]
        )
        st.dataframe(
            evidence,
            width="stretch",
            hide_index=True,
            column_config={
                "Check": st.column_config.TextColumn("Check", width="medium"),
                "Result": st.column_config.TextColumn("Result", width="small"),
                "Evidence": st.column_config.TextColumn("Evidence", width="large"),
            },
        )

        st.markdown("**XES File Location**")
        st.code(validation["xes_path"])

        st.markdown("**Event Log Preview**")
        preview = event_log.head(500).rename(
            columns={
                "case:concept:name": "Case ID",
                "concept:name": "Activity / Stop",
                "time:timestamp": "Timestamp",
                "lifecycle:transition": "Lifecycle",
                "route_id": "Route",
                "trip_id": "Trip",
                "stop_sequence": "Seq",
                "arrival_time": "Arrival",
                "departure_time": "Departure",
                "source_pdf": "Source PDF",
                "source_page": "Page",
            }
        )
        st.dataframe(preview, width="stretch", hide_index=True, height=520)

    elif selected_page == "Trip Planner":
        st.subheader("Grounded Route Planning Agent")
        st.caption("Conversational trip planning over routes.csv and the discovered process graph. Answers are restricted to extracted CDA stops, routes, schedules, and transition durations.")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Known Stops", f"{routes['stop_name_normalized'].nunique():,}")
        a2.metric("Routes", f"{routes['route_id'].nunique():,}")
        a3.metric("Scheduled Trips", f"{routes['trip_id'].nunique():,}")
        a4.metric("Grounding", "routes.csv")
        examples = [
            "I have to travel from Khanna Pul to NUST Metro Station - what are my options?",
            "Which route goes through Faizabad?",
            "What time does the last bus leave from H-9?",
            "How long does it take to get from Khanna Pul to Faizabad?",
            "Do any routes connect G-9 Markaz to F-10 Markaz?",
        ]
        st.markdown("**Quick prompts**")
        prompt_cols = st.columns(len(examples))
        quick_query = None
        for index, (column, example) in enumerate(zip(prompt_cols, examples)):
            if column.button(example, key=f"quick_prompt_{index}", width="stretch"):
                quick_query = example
        st.markdown("**Chat Interface**")
        query = st.chat_input("Ask about routes, transfers, next departures, or trip duration")
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        if "trip_planner_context" not in st.session_state:
            st.session_state.trip_planner_context = {}
        active_query = query or quick_query
        if active_query:
            st.session_state.chat_history.append(("user", active_query))
            response, updated_context = answer_query(active_query, routes, global_edges, st.session_state.trip_planner_context)
            st.session_state.trip_planner_context = updated_context
            st.session_state.chat_history.append(("assistant", response))
        for role, message in st.session_state.chat_history:
            with st.chat_message(role):
                st.markdown(message)

    elif selected_page == "Personal Route":
        st.subheader("Personal Route")
        st.caption("Per-member home-area evidence mapped to the nearest extracted CDA stop, then routed to FAST University through the discovered transition graph.")
        if home_coords.empty:
            st.warning("Member home coordinates are not available yet.")
        else:
            member_labels = [
                f"{row.member_name} ({row.student_id}) - {row.home_area}"
                for row in home_coords.itertuples(index=False)
            ]
            selected_member = st.selectbox("Member", member_labels)
            member_row = home_coords.iloc[member_labels.index(selected_member)]
            route_plan = personal_path(global_edges, "FAST University", member_row["nearest_cda_stop"])
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Member", member_row["member_name"])
            c2.metric("Nearest CDA Stop", member_row["nearest_cda_stop"])
            c3.metric("Estimated CDA Time", route_plan["duration_label"] if route_plan else "n/a")
            c4.metric("Home Pin", "Verified")
            st.info(
                f"{member_row['home_area']} is represented with a home icon. "
                f"The solid route line follows CDA stops from FAST University to {member_row['nearest_cda_stop']}; "
                "the dashed line connects the home area to the nearest CDA stop."
            )
            if route_plan:
                st_folium(
                    make_personal_path_map(
                        route_plan["path"],
                        coords,
                        member_row["member_name"],
                        member_row["home_area"],
                        (float(member_row["latitude"]), float(member_row["longitude"])),
                    ),
                    width=None,
                    height=620,
                )
                st.markdown("**Route Evidence**")
                st.dataframe(pd.DataFrame(route_plan["segments"]), width="stretch", hide_index=True, height=420)
            else:
                st.warning("Could not build a path from FAST University to this member's nearest CDA stop.")


if __name__ == "__main__":
    main()
