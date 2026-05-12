from __future__ import annotations

import pandas as pd
import pm4py

from pipeline_utils import DATA_DIR, PKT, combine_date_time, fmt_duration, safe_json_dump, seconds_between


def add_event_timestamps(routes: pd.DataFrame) -> pd.DataFrame:
    routes = routes.copy()
    routes["case_id"] = routes["route_id"].astype(str) + "::" + routes["trip_id"].astype(str)
    routes["event_index"] = routes["stop_sequence"].astype(int)
    routes["arrival_timestamp"] = routes["arrival_time"].apply(combine_date_time)
    routes["departure_timestamp"] = routes["departure_time"].apply(combine_date_time)

    # If a trip crosses midnight, keep timestamps monotonic within the case.
    adjusted_arrivals = []
    adjusted_departures = []
    for _, group in routes.groupby("case_id", sort=False):
        day_offset = 0
        previous_departure = None
        for row in group.sort_values("event_index").itertuples(index=False):
            arrival = combine_date_time(row.arrival_time, day_offset)
            departure = combine_date_time(row.departure_time, day_offset)
            if previous_departure is not None and arrival < previous_departure:
                day_offset += 1
                arrival = combine_date_time(row.arrival_time, day_offset)
                departure = combine_date_time(row.departure_time, day_offset)
            if departure < arrival:
                departure += pd.Timedelta(days=1)
            adjusted_arrivals.append(arrival)
            adjusted_departures.append(departure)
            previous_departure = departure
    routes["arrival_timestamp"] = adjusted_arrivals
    routes["departure_timestamp"] = adjusted_departures
    return routes


def build_event_log(routes: pd.DataFrame) -> pd.DataFrame:
    events = add_event_timestamps(routes)
    event_log = pd.DataFrame(
        {
            "case:concept:name": events["case_id"],
            "concept:name": events["stop_name"],
            "time:timestamp": events["arrival_timestamp"],
            "lifecycle:transition": "complete",
            "route_id": events["route_id"],
            "trip_id": events["trip_id"],
            "stop_sequence": events["stop_sequence"],
            "arrival_time": events["arrival_time"],
            "departure_time": events["departure_time"],
            "source_pdf": events["source_pdf"],
            "source_page": events["source_page"],
        }
    )
    return event_log


def build_trip_metrics(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for case_id, group in events.groupby("case_id", sort=False):
        group = group.sort_values("stop_sequence")
        first = group.iloc[0]
        last = group.iloc[-1]
        duration_seconds = int((last["departure_timestamp"] - first["arrival_timestamp"]).total_seconds())
        rows.append(
            {
                "case_id": case_id,
                "route_id": first["route_id"],
                "trip_id": first["trip_id"],
                "start_stop": first["stop_name"],
                "end_stop": last["stop_name"],
                "first_arrival": first["arrival_timestamp"].isoformat(),
                "last_departure": last["departure_timestamp"].isoformat(),
                "duration_seconds": duration_seconds,
                "duration_label": fmt_duration(duration_seconds),
                "event_count": len(group),
            }
        )
    return pd.DataFrame(rows)


def build_transition_metrics(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    transition_events = []
    for case_id, group in events.groupby("case_id", sort=False):
        group = group.sort_values("stop_sequence").reset_index(drop=True)
        for index in range(len(group) - 1):
            current = group.iloc[index]
            nxt = group.iloc[index + 1]
            duration_seconds = int((nxt["arrival_timestamp"] - current["departure_timestamp"]).total_seconds())
            if duration_seconds < 0:
                duration_seconds = seconds_between(current["departure_time"], nxt["arrival_time"])
            transition_events.append(
                {
                    "case_id": case_id,
                    "route_id": current["route_id"],
                    "trip_id": current["trip_id"],
                    "from_stop": current["stop_name"],
                    "to_stop": nxt["stop_name"],
                    "from_stop_normalized": current["stop_name_normalized"],
                    "to_stop_normalized": nxt["stop_name_normalized"],
                    "from_sequence": int(current["stop_sequence"]),
                    "to_sequence": int(nxt["stop_sequence"]),
                    "departure_time": current["departure_time"],
                    "arrival_time": nxt["arrival_time"],
                    "duration_seconds": duration_seconds,
                    "duration_label": fmt_duration(duration_seconds),
                }
            )
    transitions = pd.DataFrame(transition_events)
    metrics = (
        transitions.groupby(["route_id", "from_stop", "to_stop", "from_stop_normalized", "to_stop_normalized"], dropna=False)
        .agg(
            case_frequency=("case_id", "nunique"),
            avg_duration_seconds=("duration_seconds", "mean"),
            min_duration_seconds=("duration_seconds", "min"),
            max_duration_seconds=("duration_seconds", "max"),
        )
        .reset_index()
    )
    metrics["avg_duration_label"] = metrics["avg_duration_seconds"].apply(fmt_duration)
    metrics["min_duration_label"] = metrics["min_duration_seconds"].apply(fmt_duration)
    metrics["max_duration_label"] = metrics["max_duration_seconds"].apply(fmt_duration)
    return transitions, metrics


def build_graph_json(routes: pd.DataFrame, transition_metrics: pd.DataFrame, trip_metrics: pd.DataFrame) -> dict:
    stop_routes = (
        routes.groupby(["stop_name", "stop_name_normalized"])["route_id"]
        .apply(lambda values: sorted(set(values)))
        .reset_index(name="routes")
    )
    nodes = [
        {"id": row.stop_name_normalized, "label": row.stop_name, "routes": row.routes}
        for row in stop_routes.itertuples(index=False)
    ]
    edges = []
    for row in transition_metrics.itertuples(index=False):
        edges.append(
            {
                "id": f"{row.route_id}:{row.from_stop_normalized}->{row.to_stop_normalized}",
                "route_id": row.route_id,
                "source": row.from_stop_normalized,
                "target": row.to_stop_normalized,
                "from_stop": row.from_stop,
                "to_stop": row.to_stop,
                "case_frequency": int(row.case_frequency),
                "avg_duration_seconds": float(row.avg_duration_seconds),
                "avg_duration_label": row.avg_duration_label,
            }
        )
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "routes": int(routes["route_id"].nunique()),
            "stops": int(routes["stop_name_normalized"].nunique()),
            "cases": int(trip_metrics["case_id"].nunique()),
            "events": int(len(routes)),
            "transitions": int(len(edges)),
        },
    }


def export_xes(event_log: pd.DataFrame) -> dict:
    xes_path = DATA_DIR / "cda_transit_event_log.xes"
    formatted = pm4py.format_dataframe(
        event_log,
        case_id="case:concept:name",
        activity_key="concept:name",
        timestamp_key="time:timestamp",
    )
    pm4py.write_xes(formatted, str(xes_path))
    xes_text = xes_path.read_text(encoding="utf-8")
    xes_text = xes_text.replace('xes.version="1849-2016"', 'xes.version="1.0"', 1)
    xes_path.write_text(xes_text, encoding="utf-8")
    imported = pm4py.read_xes(str(xes_path))
    if isinstance(imported, pd.DataFrame):
        num_events = len(imported)
        num_traces = imported["case:concept:name"].nunique()
    else:
        num_traces = len(imported)
        num_events = sum(len(trace) for trace in imported)
    return {
        "xes_path": str(xes_path),
        "valid_pm4py_import": True,
        "num_traces": int(num_traces),
        "num_events": int(num_events),
        "xes_version_required": "1.0",
    }


def build_all() -> dict:
    routes = pd.read_csv(DATA_DIR / "routes.csv")
    events = add_event_timestamps(routes)
    event_log = build_event_log(routes)
    transitions, transition_metrics = build_transition_metrics(events)
    trip_metrics = build_trip_metrics(events)
    global_transition_metrics = (
        transitions.groupby(["from_stop", "to_stop", "from_stop_normalized", "to_stop_normalized"], dropna=False)
        .agg(
            case_frequency=("case_id", "nunique"),
            avg_duration_seconds=("duration_seconds", "mean"),
            min_duration_seconds=("duration_seconds", "min"),
            max_duration_seconds=("duration_seconds", "max"),
            routes=("route_id", lambda values: ", ".join(sorted(set(values)))),
        )
        .reset_index()
    )
    global_transition_metrics["avg_duration_label"] = global_transition_metrics["avg_duration_seconds"].apply(fmt_duration)
    bottlenecks = global_transition_metrics.sort_values("avg_duration_seconds", ascending=False).head(25).copy()
    graph = build_graph_json(routes, transition_metrics, trip_metrics)
    xes_validation = export_xes(event_log)

    event_log.assign(**{"time:timestamp": event_log["time:timestamp"].map(lambda dt: dt.isoformat())}).to_csv(
        DATA_DIR / "event_log.csv", index=False
    )
    transitions.to_csv(DATA_DIR / "transition_events.csv", index=False)
    transition_metrics.to_csv(DATA_DIR / "transition_metrics.csv", index=False)
    global_transition_metrics.to_csv(DATA_DIR / "global_transition_metrics.csv", index=False)
    trip_metrics.to_csv(DATA_DIR / "trip_metrics.csv", index=False)
    bottlenecks.to_csv(DATA_DIR / "bottlenecks.csv", index=False)
    safe_json_dump(DATA_DIR / "process_graph.json", graph)
    safe_json_dump(DATA_DIR / "xes_validation.json", xes_validation)

    return {
        "event_rows": len(event_log),
        "case_count": len(trip_metrics),
        "transition_events": len(transitions),
        "transition_edges": len(transition_metrics),
        "global_edges": len(global_transition_metrics),
        "xes": xes_validation,
    }


if __name__ == "__main__":
    print(build_all())
