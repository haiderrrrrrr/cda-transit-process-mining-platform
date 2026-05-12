from __future__ import annotations

from dataclasses import dataclass
import re

import networkx as nx
import pandas as pd
from rapidfuzz import fuzz, process

from pipeline_utils import fmt_duration, normalize_key, seconds_between


@dataclass
class StopMatch:
    query: str
    stop_name: str
    stop_key: str
    score: float


def stop_inventory(routes: pd.DataFrame) -> dict[str, str]:
    stops = routes[["stop_name_normalized", "stop_name"]].drop_duplicates()
    return dict(zip(stops["stop_name_normalized"], stops["stop_name"]))


def match_stop(text: str, routes: pd.DataFrame, min_score: int = 75) -> StopMatch | None:
    inventory = stop_inventory(routes)
    choices = list(inventory.keys())
    query = normalize_key(text)
    if not query:
        return None
    match = process.extractOne(query, choices, scorer=fuzz.WRatio)
    if not match or match[1] < min_score:
        return None
    return StopMatch(text, inventory[match[0]], match[0], float(match[1]))


def closest_stops(text: str, routes: pd.DataFrame, limit: int = 5) -> list[StopMatch]:
    inventory = stop_inventory(routes)
    query = normalize_key(text)
    if not query:
        return []
    matches = process.extract(query, list(inventory.keys()), scorer=fuzz.WRatio, limit=limit)
    return [StopMatch(text, inventory[key], key, float(score)) for key, score, _ in matches]


def find_stops_in_query(query: str, routes: pd.DataFrame) -> list[StopMatch]:
    inventory = stop_inventory(routes)
    query_key = normalize_key(query)
    exact = []
    for key, label in inventory.items():
        if key and key in query_key:
            exact.append(StopMatch(label, label, key, 100.0))
    exact = sorted(exact, key=lambda item: query_key.find(item.stop_key))
    deduped = []
    seen = set()
    for item in exact:
        if item.stop_key not in seen:
            deduped.append(item)
            seen.add(item.stop_key)
    return deduped[:4]


def extract_origin_destination(query: str, routes: pd.DataFrame) -> tuple[StopMatch | None, StopMatch | None]:
    query_lower = query.lower()
    found = find_stops_in_query(query, routes)
    if len(found) >= 2:
        query_key = normalize_key(query)
        ordered = sorted(found[:2], key=lambda item: query_key.find(item.stop_key))
        return ordered[0], ordered[1]
    if " to " in query_lower:
        before, after = query_lower.split(" to ", 1)
        origin_text = before.split(" from ")[-1].strip(" ?.-")
        destination_text = after.split("?")[0].strip(" ?.-")
        return match_stop(origin_text, routes), match_stop(destination_text, routes)
    return (found[0], None) if found else (None, None)


def route_stop_sequences(routes: pd.DataFrame) -> pd.DataFrame:
    return routes.sort_values(["route_id", "trip_id", "stop_sequence"])


def direct_options(routes: pd.DataFrame, origin_key: str, dest_key: str) -> list[dict]:
    options = []
    for (route_id, trip_id), group in route_stop_sequences(routes).groupby(["route_id", "trip_id"], sort=False):
        origin_rows = group[group["stop_name_normalized"] == origin_key]
        dest_rows = group[group["stop_name_normalized"] == dest_key]
        if origin_rows.empty or dest_rows.empty:
            continue
        origin = origin_rows.iloc[0]
        dest = dest_rows.iloc[-1]
        if int(origin["stop_sequence"]) >= int(dest["stop_sequence"]):
            continue
        duration_seconds = seconds_between(origin["departure_time"], dest["arrival_time"])
        options.append(
            {
                "route_id": route_id,
                "trip_id": trip_id,
                "origin_stop": origin["stop_name"],
                "destination_stop": dest["stop_name"],
                "departure_time": origin["departure_time"],
                "arrival_time": dest["arrival_time"],
                "duration_seconds": duration_seconds,
                "duration_label": fmt_duration(duration_seconds),
                "transfers": [],
            }
        )
    return sorted(options, key=lambda item: (item["departure_time"], item["duration_seconds"]))


def route_through_stop(routes: pd.DataFrame, stop_key: str) -> pd.DataFrame:
    rows = routes[routes["stop_name_normalized"] == stop_key]
    return (
        rows.groupby("route_id")
        .agg(first_departure=("departure_time", "min"), last_departure=("departure_time", "max"), trips=("trip_id", "nunique"))
        .reset_index()
        .sort_values("route_id")
    )


def build_weighted_graph(global_edges: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    for row in global_edges.itertuples(index=False):
        graph.add_edge(
            row.from_stop_normalized,
            row.to_stop_normalized,
            weight=float(row.avg_duration_seconds),
            label=f"{row.from_stop} -> {row.to_stop}",
            routes=row.routes,
        )
    return graph


def transfer_option(routes: pd.DataFrame, global_edges: pd.DataFrame, origin_key: str, dest_key: str) -> dict | None:
    graph = build_weighted_graph(global_edges)
    if origin_key not in graph or dest_key not in graph:
        return None
    try:
        path = nx.shortest_path(graph, origin_key, dest_key, weight="weight")
    except nx.NetworkXNoPath:
        return None
    inventory = stop_inventory(routes)
    total_seconds = 0.0
    segments = []
    route_runs = []
    active_route = None
    active_start = None
    for source, target in zip(path[:-1], path[1:]):
        edge = graph[source][target]
        total_seconds += edge["weight"]
        route_choices = [route.strip() for route in str(edge.get("routes", "")).split(",") if route.strip()]
        route_id = route_choices[0] if route_choices else "unknown route"
        source_label = inventory.get(source, source)
        target_label = inventory.get(target, target)
        segments.append({"from": source_label, "to": target_label, "route": route_id, "routes": ", ".join(route_choices)})
        if active_route is None:
            active_route = route_id
            active_start = source_label
        elif route_id != active_route:
            route_runs.append({"route": active_route, "from": active_start, "to": source_label})
            active_route = route_id
            active_start = source_label
    if active_route is not None and segments:
        route_runs.append({"route": active_route, "from": active_start, "to": segments[-1]["to"]})
    transfer_points = [run["from"] for previous, run in zip(route_runs[:-1], route_runs[1:]) if previous["route"] != run["route"]]
    origin_rows = routes[routes["stop_name_normalized"] == origin_key].sort_values("departure_time")
    next_departure = origin_rows.iloc[0]["departure_time"] if not origin_rows.empty else "n/a"
    return {
        "path": [inventory.get(stop, stop) for stop in path],
        "segments": segments,
        "route_runs": route_runs,
        "transfer_points": transfer_points,
        "duration_seconds": int(total_seconds),
        "duration_label": fmt_duration(total_seconds),
        "next_departure": next_departure,
    }


def unknown_stop_message(query: str, routes: pd.DataFrame) -> str:
    suggestions = closest_stops(query, routes, limit=5)
    if not suggestions:
        return "I could not ground that query in the extracted CDA stops. Please use a stop name from routes.csv."
    lines = [
        "I could not confidently match one or more stops from that query to the extracted CDA route data.",
        "Closest extracted stop names:",
    ]
    for item in suggestions:
        lines.append(f"- {item.stop_name} (match {item.score:.0f}%)")
    lines.append("I will only answer using stops that exist in routes.csv.")
    return "\n".join(lines)


def answer_query(query: str, routes: pd.DataFrame, global_edges: pd.DataFrame) -> str:
    origin, destination = extract_origin_destination(query, routes)
    lower = query.lower()

    if ("through" in lower or "goes" in lower) and origin and not destination:
        route_rows = route_through_stop(routes, origin.stop_key)
        if route_rows.empty:
            return f"I could not find any extracted route through {origin.stop_name}."
        lines = [f"Routes through {origin.stop_name}: " + ", ".join(route_rows["route_id"].tolist()) + "."]
        lines.append("Schedule evidence:")
        for row in route_rows.head(8).itertuples(index=False):
            lines.append(f"- {row.route_id}: {row.trips} trips, first {row.first_departure}, last {row.last_departure}")
        return "\n".join(lines)

    if "last bus" in lower and origin:
        route_rows = route_through_stop(routes, origin.stop_key)
        if route_rows.empty:
            return f"I found {origin.stop_name}, but no departure rows are available for it."
        best = route_rows.sort_values("last_departure", ascending=False).iloc[0]
        return (
            f"The last extracted departure from {origin.stop_name} is {best['last_departure']} "
            f"on route {best['route_id']}.\n"
            f"Evidence: stop matched from routes.csv; schedule scanned across {len(route_rows)} route(s)."
        )

    if origin and destination:
        direct = direct_options(routes, origin.stop_key, destination.stop_key)
        if direct:
            first = direct[0]
            routes_found = sorted({item["route_id"] for item in direct})
            return (
                f"Direct option found from {origin.stop_name} to {destination.stop_name}.\n"
                f"Routes: {', '.join(routes_found)}.\n"
                f"Next available extracted departure: route {first['route_id']} at {first['departure_time']} "
                f"arriving {first['arrival_time']}.\n"
                f"Estimated travel time: {first['duration_label']}.\n"
                f"Transfers required: none.\n"
                f"Evidence: matched stops `{origin.stop_name}` and `{destination.stop_name}` from routes.csv."
            )
        transfer = transfer_option(routes, global_edges, origin.stop_key, destination.stop_key)
        if transfer:
            path_label = " -> ".join(transfer["path"])
            route_plan = "; ".join(f"{run['route']}: {run['from']} to {run['to']}" for run in transfer["route_runs"][:8])
            transfers = ", ".join(transfer["transfer_points"]) if transfer["transfer_points"] else "none detected from route changes"
            return (
                f"No single-trip direct option was found, but a graph path exists.\n"
                f"Path: {path_label}.\n"
                f"Route segments: {route_plan}.\n"
                f"Transfer points: {transfers}.\n"
                f"Estimated transition time: {transfer['duration_label']}.\n"
                f"Next available departure near origin: {transfer['next_departure']}.\n"
                f"Evidence: route path is computed from discovered transition durations in the process graph."
            )
        for candidate in closest_stops(destination.stop_name, routes, limit=6):
            if candidate.stop_key == destination.stop_key:
                continue
            alternate = transfer_option(routes, global_edges, origin.stop_key, candidate.stop_key)
            if alternate:
                path_label = " -> ".join(alternate["path"])
                route_plan = "; ".join(f"{run['route']}: {run['from']} to {run['to']}" for run in alternate["route_runs"][:8])
                transfers = ", ".join(alternate["transfer_points"]) if alternate["transfer_points"] else "none detected from route changes"
                return (
                    f"I found `{destination.stop_name}` exactly, but no forward-schedule path reaches that exact stop from {origin.stop_name}.\n"
                    f"Closest connected extracted stop: {candidate.stop_name}.\n"
                    f"Path: {path_label}.\n"
                    f"Route segments: {route_plan}.\n"
                    f"Transfer points: {transfers}.\n"
                    f"Estimated transition time: {alternate['duration_label']}.\n"
                    f"Next available departure near origin: {alternate['next_departure']}.\n"
                    f"Evidence: fallback stop is explicitly named as a closest connected extracted stop, not assumed to be the same stop."
                )
        return f"I found both stops, but no extracted route path connects {origin.stop_name} to {destination.stop_name} in the forward schedules."

    if origin:
        route_rows = route_through_stop(routes, origin.stop_key)
        if not route_rows.empty:
            return f"I matched `{origin.query}` to {origin.stop_name}. Routes available: {', '.join(route_rows['route_id'].tolist())}."

    return unknown_stop_message(query, routes)


def classify_intent(query: str) -> str:
    lower = query.lower()
    if any(term in lower for term in ["last bus", "last departure", "last leave"]):
        return "last_departure"
    if any(term in lower for term in ["which route", "goes through", "through ", "routes through"]):
        return "route_through_stop"
    if any(term in lower for term in ["connect", "connection", "direct"]):
        return "direct_connection"
    if any(term in lower for term in ["how long", "time does it take", "duration"]):
        return "travel_time"
    if any(term in lower for term in ["travel", "from ", " to ", "options", "go to", "get from"]):
        return "route_options"
    return "stop_lookup"


def format_match(match: StopMatch | None) -> str:
    if not match:
        return "not matched"
    return f"{match.stop_name} ({match.score:.0f}% match)"


def top_direct_options(routes: pd.DataFrame, origin_key: str, dest_key: str, limit: int = 3) -> list[dict]:
    seen = set()
    ranked = []
    for option in direct_options(routes, origin_key, dest_key):
        signature = (option["route_id"], option["departure_time"], option["arrival_time"])
        if signature in seen:
            continue
        seen.add(signature)
        ranked.append(option)
        if len(ranked) >= limit:
            break
    return ranked


def format_direct_options(options: list[dict]) -> list[str]:
    lines = []
    for index, option in enumerate(options, start=1):
        lines.append(
            f"{index}. Route {option['route_id']} | depart {option['departure_time']} | "
            f"arrive {option['arrival_time']} | {option['duration_label']} | transfers: none"
        )
    return lines


def evidence_block(origin: StopMatch | None, destination: StopMatch | None, source: str) -> str:
    lines = ["Evidence ledger:"]
    lines.append(f"- Origin match: {format_match(origin)}")
    if destination:
        lines.append(f"- Destination match: {format_match(destination)}")
    lines.append(f"- Data source: {source}")
    lines.append("- Guardrail: every stop and route named above exists in the extracted data.")
    return "\n".join(lines)


def advanced_answer_query(
    query: str,
    routes: pd.DataFrame,
    global_edges: pd.DataFrame,
    context: dict | None = None,
) -> tuple[str, dict]:
    context = context or {}
    intent = classify_intent(query)
    origin, destination = extract_origin_destination(query, routes)
    explicit_stop_request = re.search(r"\b(?:from|at|leave from|leaves from)\s+([a-zA-Z0-9\-/ ]+)", query, re.IGNORECASE)
    explicit_destination_request = re.search(r"\bto\s+([a-zA-Z0-9\-/ ]+)", query, re.IGNORECASE)

    # Conversation memory for follow-ups such as "what about the last bus?"
    if not origin and explicit_stop_request:
        return unknown_stop_message(explicit_stop_request.group(1), routes), context
    if not destination and explicit_destination_request and intent in {"route_options", "travel_time", "direct_connection"}:
        return unknown_stop_message(explicit_destination_request.group(1), routes), context
    if not origin and context.get("origin_key") and intent in {"last_departure", "route_options", "travel_time", "direct_connection"}:
        origin = StopMatch("previous origin", context["origin_name"], context["origin_key"], 100.0)
    if not destination and context.get("destination_key") and intent in {"route_options", "travel_time", "direct_connection"}:
        destination = StopMatch("previous destination", context["destination_name"], context["destination_key"], 100.0)

    new_context = dict(context)
    if origin:
        new_context.update({"origin_key": origin.stop_key, "origin_name": origin.stop_name})
    if destination:
        new_context.update({"destination_key": destination.stop_key, "destination_name": destination.stop_name})

    if intent == "route_through_stop" and origin:
        route_rows = route_through_stop(routes, origin.stop_key)
        if route_rows.empty:
            return f"No extracted route was found through {origin.stop_name}.\n{evidence_block(origin, None, 'routes.csv')}", new_context
        lines = [f"Answer: {origin.stop_name} is served by {len(route_rows)} route(s): {', '.join(route_rows['route_id'].tolist())}."]
        lines.append("Route evidence:")
        for row in route_rows.head(10).itertuples(index=False):
            lines.append(f"- {row.route_id}: {row.trips} trips | first {row.first_departure} | last {row.last_departure}")
        lines.append(evidence_block(origin, None, "routes.csv"))
        return "\n".join(lines), new_context

    if intent == "last_departure" and origin:
        route_rows = route_through_stop(routes, origin.stop_key)
        if route_rows.empty:
            return f"I found {origin.stop_name}, but no departure records are available.\n{evidence_block(origin, None, 'routes.csv')}", new_context
        best = route_rows.sort_values("last_departure", ascending=False).iloc[0]
        answer = (
            f"Answer: the last extracted departure from {origin.stop_name} is {best['last_departure']} "
            f"on route {best['route_id']}.\n"
            f"Schedule scope: scanned {len(route_rows)} route(s) serving this stop.\n"
            f"{evidence_block(origin, None, 'routes.csv')}"
        )
        return answer, new_context

    if origin and destination:
        direct = top_direct_options(routes, origin.stop_key, destination.stop_key)
        if direct:
            lines = [f"Answer: direct route option(s) exist from {origin.stop_name} to {destination.stop_name}."]
            lines.append("Ranked options:")
            lines.extend(format_direct_options(direct))
            lines.append(f"Recommended: Route {direct[0]['route_id']} at {direct[0]['departure_time']} ({direct[0]['duration_label']}).")
            lines.append(evidence_block(origin, destination, "routes.csv + transition timings"))
            return "\n".join(lines), new_context

        transfer = transfer_option(routes, global_edges, origin.stop_key, destination.stop_key)
        if transfer:
            route_plan = "; ".join(f"{run['route']}: {run['from']} to {run['to']}" for run in transfer["route_runs"][:8])
            transfers = ", ".join(transfer["transfer_points"]) if transfer["transfer_points"] else "none detected from route changes"
            lines = [
                f"Answer: no direct same-trip option was found, but a transfer path is available.",
                f"Route segments: {route_plan}.",
                f"Transfer points: {transfers}.",
                f"Estimated travel time: {transfer['duration_label']}.",
                f"Next available departure near origin: {transfer['next_departure']}.",
                f"Path: {' -> '.join(transfer['path'])}.",
                evidence_block(origin, destination, "routes.csv + process_graph.json + transition_metrics.csv"),
            ]
            return "\n".join(lines), new_context

        # Safe closest-connected fallback for ambiguous destination labels.
        for candidate in closest_stops(destination.stop_name, routes, limit=8):
            if candidate.stop_key == destination.stop_key:
                continue
            alternate = transfer_option(routes, global_edges, origin.stop_key, candidate.stop_key)
            if alternate:
                route_plan = "; ".join(f"{run['route']}: {run['from']} to {run['to']}" for run in alternate["route_runs"][:8])
                transfers = ", ".join(alternate["transfer_points"]) if alternate["transfer_points"] else "none detected from route changes"
                lines = [
                    f"Answer: exact stop `{destination.stop_name}` was found, but no forward-schedule path reaches it from {origin.stop_name}.",
                    f"Closest connected extracted stop: {candidate.stop_name}.",
                    f"Route segments: {route_plan}.",
                    f"Transfer points: {transfers}.",
                    f"Estimated travel time: {alternate['duration_label']}.",
                    f"Next available departure near origin: {alternate['next_departure']}.",
                    evidence_block(origin, candidate, "routes.csv + process graph closest-connected fallback"),
                ]
                return "\n".join(lines), new_context

        return (
            f"Answer: both stops were matched, but no extracted forward-schedule path connects {origin.stop_name} to {destination.stop_name}.\n"
            f"{evidence_block(origin, destination, 'routes.csv + process_graph.json')}"
        ), new_context

    if origin and not destination:
        route_rows = route_through_stop(routes, origin.stop_key)
        if not route_rows.empty:
            lines = [f"Answer: I matched your stop to {origin.stop_name}."]
            lines.append(f"Available routes: {', '.join(route_rows['route_id'].tolist())}.")
            lines.append("Ask with a destination, for example: `from this stop to NUST Metro Station`.")
            lines.append(evidence_block(origin, None, "routes.csv"))
            return "\n".join(lines), new_context

    return unknown_stop_message(query, routes), new_context


def answer_query(query: str, routes: pd.DataFrame, global_edges: pd.DataFrame, context: dict | None = None):
    if context is None:
        answer, _ = advanced_answer_query(query, routes, global_edges, None)
        return answer
    return advanced_answer_query(query, routes, global_edges, context)
