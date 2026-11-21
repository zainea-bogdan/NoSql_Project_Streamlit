from fastapi import Body, HTTPException

from backend.controllers import aggregate_controller as aggregate
from backend.controllers import find_controller as find
from backend.db import get_collection

MATCH = {"name": "match_id", "label": "Match", "type": "match"}

QUERIES = {
    "R1": {
        "kind": "find", "collection": "events", "viz": "shot_map", "run": find.r1_missed_big_chances,
        "title": "Missed big chances, late in the game",
        "question": "Which big chances were missed late in the game?",
        "why": "High-xG misses after minute 75 are the moments that decide results; coaches review them first.",
        "params": [
            {**MATCH, "allow_all": True},
            {"name": "xg_min", "label": "Minimum xG", "type": "float", "default": 0.25, "min": 0.0, "max": 1.0, "step": 0.05},
            {"name": "from_minute", "label": "From minute", "type": "int", "default": 75, "min": 0, "max": 120, "step": 1},
        ],
    },
    "R2": {
        "kind": "find", "collection": "players", "viz": "table", "run": find.r2_scouting_shortlist,
        "title": "Scouting shortlist",
        "question": "Left-footed outfield players, born 2003 or later, already with a national team.",
        "why": "Young left-footers with international experience are scarce, so they are a classic scouting filter.",
        "params": [
            {"name": "born_from", "label": "Born on or after", "type": "date", "default": "2003-01-01"},
            {"name": "role_regex", "label": "Role contains (regex, optional)", "type": "str", "default": "",
             "help": "e.g. 'def' or 'mid|forw'. Case-insensitive."},
        ],
    },
    "R3": {
        "kind": "find", "collection": "events", "viz": "pitch_scatter", "run": find.r3_box_defending,
        "title": "Defending the own box",
        "question": "How does each team defend its own box?",
        "why": "Shows who clears, intercepts and wins duels inside the penalty area, and from where.",
        "params": [MATCH],
    },
    "A1": {
        "kind": "aggregate", "collection": "events", "viz": "zone_heatmap", "run": aggregate.a1_danger_zones,
        "title": "Danger zones",
        "question": "Where does each team create danger?",
        "why": "Shots and key passes per 3x3 zone reveal whether a team attacks through the centre or the flanks.",
        "params": [
            MATCH,
            {"name": "min_actions", "label": "Minimum actions per zone", "type": "int", "default": 1, "min": 1, "max": 50, "step": 1},
        ],
    },
    "A2": {
        "kind": "aggregate", "collection": "events", "viz": "heat_table", "run": aggregate.a2_control_by_phase,
        "title": "Control by 15-minute phase",
        "question": "In which 15-minute phases did each team control the match, and did control turn into threat?",
        "why": "Possession without final-third entries or xG is sterile; the phases show when momentum really shifted.",
        "params": [MATCH],
    },
    "A3": {
        "kind": "aggregate", "collection": "events", "viz": "scatter_profile", "run": aggregate.a3_ball_progressors,
        "title": "Ball progressors",
        "question": "Who actually moves the ball forward, and what's their profile?",
        "why": "Progressive passers break lines; joining events with player profiles adds role, foot and age.",
        "params": [
            MATCH,
            {"name": "min_passes", "label": "Minimum passes", "type": "int", "default": 15, "min": 1, "max": 200, "step": 1},
            {"name": "progressive_gain", "label": "Progressive if gain >= (pitch %)", "type": "int", "default": 15, "min": 1, "max": 60, "step": 1},
        ],
    },
    "A4": {
        "kind": "aggregate", "collection": "events", "viz": "styled_table", "run": aggregate.a4_attack_types,
        "title": "Attack types and outcomes",
        "question": "How does each team build attacks, and how do they end?",
        "why": "Counterattacks vs. positional attacks vs. set pieces: which possession types produce shots and xG.",
        "params": [
            MATCH,
            {"name": "min_possessions", "label": "Minimum possessions per type", "type": "int", "default": 3, "min": 1, "max": 100, "step": 1},
        ],
    },
    "A5": {
        "kind": "aggregate", "collection": "events", "viz": "pressing", "run": aggregate.a5_pressing,
        "title": "Pressing intensity (PPDA)",
        "question": "How intensely does each team press (PPDA), and where does it win the ball back?",
        "why": "PPDA = opponent passes allowed per defensive action; lower means a more aggressive press.",
        "params": [MATCH],
    },
    "A6": {
        "kind": "aggregate", "collection": "teams", "viz": "stacked_bar", "run": aggregate.a6_young_players,
        "title": "Use of young players",
        "question": "Does the squad actually use its young players?",
        "why": "Squad lists say who is registered; event involvement says who really plays.",
        "params": [],
    },
}


def get_queries():
    return [{"id": query_id, **{k: v for k, v in query.items() if k != "run"}} for query_id, query in QUERIES.items()]


def run_query(query_id: str, params: dict | None = Body(None)):
    query = QUERIES.get(query_id.upper())
    if query is None:
        raise HTTPException(404, f"Unknown query {query_id}")
    params = params or {}
    values = {p["name"]: params.get(p["name"], p.get("default")) for p in query["params"]}

    match_id = values.get("match_id")
    needs_match = any(p["type"] == "match" and not p.get("allow_all") for p in query["params"])
    if needs_match and match_id is None:
        raise HTTPException(400, "Pick a match: match_id is required for this query")
    if match_id is not None and get_collection("events").count_documents({"matchId": match_id}, limit=1) == 0:
        raise HTTPException(422, f"No events for match {match_id}. Ingest its events first.")

    result = query["run"](**values)
    info = {k: v for k, v in query.items() if k not in ("run", "params")}
    return {"id": query_id.upper(), **info, "params": values, **result}
