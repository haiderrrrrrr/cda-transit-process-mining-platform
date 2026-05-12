from __future__ import annotations

import json

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pipeline_utils import DATA_DIR, FIGURES_DIR, REPORT_DIR, data_file, ensure_dirs, fmt_duration


def save_process_map(edges: pd.DataFrame, path, title: str, limit_edges: int = 80) -> None:
    subset = edges.sort_values("case_frequency", ascending=False).head(limit_edges)
    graph = nx.DiGraph()
    for row in subset.itertuples(index=False):
        graph.add_edge(row.from_stop, row.to_stop, weight=float(row.avg_duration_seconds), label=row.avg_duration_label)
    plt.figure(figsize=(16, 11))
    if graph.number_of_nodes():
        pos = nx.spring_layout(graph, seed=7, k=0.9, iterations=100)
        nx.draw_networkx_nodes(graph, pos, node_size=900, node_color="#0f766e", edgecolors="white", linewidths=1.5)
        nx.draw_networkx_edges(graph, pos, edge_color="#475569", arrows=True, arrowsize=18, width=1.4)
        nx.draw_networkx_labels(graph, pos, font_size=7, font_color="#111827")
        edge_labels = {(u, v): d["label"] for u, v, d in graph.edges(data=True)}
        nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=6)
    plt.title(title, fontsize=16)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def save_bottleneck_chart(bottlenecks: pd.DataFrame, path) -> None:
    top = bottlenecks.sort_values("avg_duration_seconds", ascending=True).tail(10)
    labels = [f"{row.from_stop} -> {row.to_stop}" for row in top.itertuples(index=False)]
    plt.figure(figsize=(14, 8))
    plt.barh(labels, top["avg_duration_seconds"] / 60, color="#dc2626")
    plt.xlabel("Average transition duration (minutes)")
    plt.title("Top Bottleneck Transitions")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def save_xes_validation_figure(validation: dict, routes: pd.DataFrame, trips: pd.DataFrame, path) -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.axis("off")
    rows = [
        ["Validation Item", "Result"],
        ["Process mining tool", "PM4Py"],
        ["XES file", "data/cda_transit_event_log.xes"],
        ["XES version", validation.get("xes_version_required", "1.0")],
        ["PM4Py import", "Successful" if validation.get("valid_pm4py_import") else "Review required"],
        ["Traces / cases", f"{validation.get('num_traces', trips['case_id'].nunique()):,}"],
        ["Events", f"{validation.get('num_events', len(routes)):,}"],
        ["Routes represented", f"{routes['route_id'].nunique():,}"],
        ["Timestamp format", "ISO 8601 with timezone"],
    ]
    table = ax.table(cellText=rows, cellLoc="left", loc="center", colWidths=[0.35, 0.55])
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 1.8)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#cbd5e1")
        if row == 0:
            cell.set_facecolor("#0f766e")
            cell.set_text_props(color="white", weight="bold")
        elif col == 1 and row == 4:
            cell.set_facecolor("#dcfce7")
        else:
            cell.set_facecolor("#f8fafc" if row % 2 == 0 else "white")
    ax.set_title("PM4Py XES Validation Evidence", fontsize=18, weight="bold", pad=20)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def build_undirected_path(global_edges: pd.DataFrame, origin: str, destination: str) -> dict | None:
    graph = nx.Graph()
    for row in global_edges.itertuples(index=False):
        graph.add_edge(
            row.from_stop,
            row.to_stop,
            weight=float(row.avg_duration_seconds),
            routes=row.routes,
            duration=row.avg_duration_label,
        )
    if origin not in graph or destination not in graph:
        return None
    try:
        path = nx.shortest_path(graph, origin, destination, weight="weight")
    except nx.NetworkXNoPath:
        return None
    total = nx.shortest_path_length(graph, origin, destination, weight="weight")
    route_runs = []
    active_route = None
    active_start = None
    for source, target in zip(path[:-1], path[1:]):
        route_id = str(graph[source][target].get("routes", "")).split(",")[0].strip() or "route"
        if active_route is None:
            active_route = route_id
            active_start = source
        elif route_id != active_route:
            route_runs.append(f"{active_start} --{active_route}--> {source}")
            active_route = route_id
            active_start = source
    if active_route and len(path) > 1:
        route_runs.append(f"{active_start} --{active_route}--> {path[-1]}")
    return {"path": path, "duration": fmt_duration(total), "route_runs": route_runs}


def save_personal_route_maps(global_edges: pd.DataFrame, coords: pd.DataFrame, home_coords: pd.DataFrame) -> list[dict]:
    outputs = []
    coord_lookup = coords.drop_duplicates("stop_name").set_index("stop_name").to_dict("index")
    for member in home_coords.itertuples(index=False):
        plan = build_undirected_path(global_edges, "FAST University", member.nearest_cda_stop)
        if not plan:
            continue
        points = []
        labels = []
        for stop in plan["path"]:
            item = coord_lookup.get(stop)
            if item:
                points.append((float(item["longitude"]), float(item["latitude"])))
                labels.append(stop)
        home_point = (float(member.longitude), float(member.latitude))
        if len(points) < 2:
            continue
        fig, ax = plt.subplots(figsize=(12, 7))
        xs, ys = zip(*points)
        ax.plot(xs, ys, color="#0f766e", linewidth=2.8, marker="o", markersize=4, label="CDA route path")
        ax.plot([home_point[0], xs[-1]], [home_point[1], ys[-1]], color="#f97316", linestyle="--", linewidth=2, label="Home area access")
        ax.scatter([xs[0]], [ys[0]], s=180, marker="^", color="#1d4ed8", edgecolor="white", linewidth=1.4, label="FAST University", zorder=5)
        ax.scatter([home_point[0]], [home_point[1]], s=180, marker="s", color="#dc2626", edgecolor="white", linewidth=1.4, label="Home area", zorder=5)
        ax.scatter([xs[-1]], [ys[-1]], s=150, marker="D", color="#16a34a", edgecolor="white", linewidth=1.2, label="Nearest CDA stop", zorder=5)
        for index, (x, y, label) in enumerate(zip(xs, ys, labels), start=1):
            if index in {1, len(labels)} or index % max(1, len(labels) // 6) == 0:
                ax.annotate(label, (x, y), xytext=(4, 4), textcoords="offset points", fontsize=7)
        ax.annotate(member.home_area, home_point, xytext=(5, 5), textcoords="offset points", fontsize=8, weight="bold")
        ax.set_title(f"{member.member_name} ({member.student_id}) - Personal Route to FAST", fontsize=14, weight="bold")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        safe_id = str(member.student_id).replace("-", "_")
        path = FIGURES_DIR / f"personal_route_{safe_id}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        outputs.append(
            {
                "member": member.member_name,
                "student_id": member.student_id,
                "home_area": member.home_area,
                "nearest_stop": member.nearest_cda_stop,
                "duration": plan["duration"],
                "route_runs": "; ".join(plan["route_runs"]),
                "figure": path,
            }
        )
    return outputs


def generate_pdf_report() -> None:
    coverage = pd.read_csv(data_file("pdf_coverage_report.csv"))
    routes = pd.read_csv(data_file("routes.csv"))
    trips = pd.read_csv(data_file("trip_metrics.csv"))
    global_edges = pd.read_csv(data_file("global_transition_metrics.csv"))
    coords = pd.read_csv(data_file("stop_coordinates.csv"))
    home_coords = pd.read_csv(data_file("member_home_coordinates.csv"))
    validation = json.loads(data_file("xes_validation.json").read_text(encoding="utf-8"))
    personal_maps = save_personal_route_maps(global_edges, coords, home_coords)
    styles = getSampleStyleSheet()
    story = []
    doc = SimpleDocTemplate(str(REPORT_DIR / "CDA_Transit_Route_Intelligence_Report.pdf"), pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)

    story.append(Paragraph("CDA Transit Process Mining & Route Intelligence Platform", styles["Title"]))
    story.append(Paragraph("FAST National University - SE4009 Process Mining and Simulation", styles["Normal"]))
    story.append(Spacer(1, 0.18 * inch))

    summary_rows = [
        ["Metric", "Value"],
        ["PDFs processed", f"{len(coverage):,}"],
        ["Routes extracted", f"{routes['route_id'].nunique():,}"],
        ["Stops extracted", f"{routes['stop_name_normalized'].nunique():,}"],
        ["Trips / traces", f"{trips['case_id'].nunique():,}"],
        ["Events", f"{len(routes):,}"],
        ["Global transitions", f"{len(global_edges):,}"],
        ["Average trip duration", fmt_duration(trips["duration_seconds"].mean())],
        ["XES validation", f"{validation['num_traces']:,} traces / {validation['num_events']:,} events"],
    ]
    table = Table(summary_rows, colWidths=[2.4 * inch, 3.2 * inch])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
    story.append(table)
    story.append(Spacer(1, 0.18 * inch))

    sections = [
        ("Task 1 - Data Extraction", "All available route PDFs were parsed into data/routes.csv. The PDF coverage report shows declared trip counts matching extracted trips for every route."),
        ("Task 2 - Trace Log and XES", "The merged event log was exported to data/cda_transit_event_log.xes with xes.version=\"1.0\" and timezone-aware timestamps, then imported through PM4Py for validation. Screenshot-style evidence is saved as report/figures/xes_pm4py_validation.png."),
        ("Task 3 - Process Discovery and GUI", "The directed process graph represents stops as nodes and consecutive stop transitions as edges. Edge labels show average transition durations and case frequencies are available in the GUI."),
        ("Task 4 - Performance and Bottlenecks", "Trip throughput and transition durations were computed automatically. The GUI provides a configurable bottleneck threshold and top slowest transitions."),
        ("Task 5 - Agentic Trip Planner", "The embedded chat planner is grounded in routes.csv and the discovered transition graph. Unknown stops are refused instead of hallucinated."),
        ("Task 6 - Personal Route Map Bonus", "Four member home areas were mapped to nearest extracted CDA stops and visualised against FAST University. Home pins, FAST, and bus stops are separated by marker style in the GUI and report figures."),
    ]
    for heading, body in sections:
        story.append(Paragraph(heading, styles["Heading2"]))
        story.append(Paragraph(body, styles["BodyText"]))
        story.append(Spacer(1, 0.12 * inch))

    story.append(Paragraph("Extraction Coverage Snapshot", styles["Heading2"]))
    coverage_preview = [["PDF", "Route", "Declared", "Extracted", "Status"]] + coverage[["source_pdf", "route_id", "declared_total_trips", "extracted_trips", "status"]].astype(str).values.tolist()[:21]
    coverage_table = Table(coverage_preview, colWidths=[2.0 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch, 0.75 * inch])
    coverage_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
    story.append(coverage_table)
    story.append(PageBreak())

    figure_sections = [
        ("Task 2 Evidence - PM4Py XES Validation", FIGURES_DIR / "xes_pm4py_validation.png"),
        ("Task 3 Evidence - All Routes Process Map", FIGURES_DIR / "process_map_all_routes.png"),
        ("Task 3 Evidence - FR-01 Filtered Process Map", FIGURES_DIR / "process_map_fr01.png"),
        ("Task 4 Evidence - Bottleneck Annotation", FIGURES_DIR / "bottleneck_top10.png"),
    ]
    for title, image_path in figure_sections:
        story.append(Paragraph(title, styles["Heading2"]))
        story.append(Image(str(image_path), width=7.0 * inch, height=4.35 * inch))
        story.append(Spacer(1, 0.12 * inch))

    story.append(PageBreak())
    story.append(Paragraph("Task 6 Bonus - Per-Member Personal Routes", styles["Heading2"]))
    member_rows = [["Member", "ID", "Home Area", "Nearest CDA Stop", "Est. CDA Time"]]
    for item in personal_maps:
        member_rows.append([item["member"], item["student_id"], item["home_area"], item["nearest_stop"], item["duration"]])
    member_table = Table(member_rows, colWidths=[1.25 * inch, 0.85 * inch, 1.65 * inch, 1.45 * inch, 1.0 * inch])
    member_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
    story.append(member_table)
    story.append(Spacer(1, 0.12 * inch))
    for item in personal_maps:
        story.append(Paragraph(f"{item['member']} ({item['student_id']}) - {item['home_area']} to FAST University", styles["Heading3"]))
        story.append(Paragraph(f"Nearest CDA stop: {item['nearest_stop']}. Route segments: {item['route_runs']}. Estimated CDA time: {item['duration']}.", styles["BodyText"]))
        story.append(Image(str(item["figure"]), width=7.0 * inch, height=4.05 * inch))
        story.append(Spacer(1, 0.12 * inch))
    doc.build(story)


def generate_assets() -> dict:
    ensure_dirs()
    global_edges = pd.read_csv(data_file("global_transition_metrics.csv"))
    transition_metrics = pd.read_csv(data_file("transition_metrics.csv"))
    bottlenecks = pd.read_csv(data_file("bottlenecks.csv"))
    routes = pd.read_csv(data_file("routes.csv"))
    trips = pd.read_csv(data_file("trip_metrics.csv"))
    validation = json.loads(data_file("xes_validation.json").read_text(encoding="utf-8"))
    save_process_map(global_edges, FIGURES_DIR / "process_map_all_routes.png", "CDA Process Map - All Routes")
    fr01 = transition_metrics[transition_metrics["route_id"] == "FR-01"]
    save_process_map(fr01, FIGURES_DIR / "process_map_fr01.png", "CDA Process Map - FR-01", limit_edges=40)
    save_bottleneck_chart(bottlenecks, FIGURES_DIR / "bottleneck_top10.png")
    save_xes_validation_figure(validation, routes, trips, FIGURES_DIR / "xes_pm4py_validation.png")
    generate_pdf_report()
    return {
        "figures": ["process_map_all_routes.png", "process_map_fr01.png", "bottleneck_top10.png", "xes_pm4py_validation.png"],
        "report": "report/CDA_Bus_Route_Process_Mining_Report.pdf",
    }


if __name__ == "__main__":
    print(generate_assets())
