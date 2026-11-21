from datetime import datetime, timezone

from fastapi import HTTPException

from backend.db import get_collection
from backend.schemas import BulkRequest, UpdateItem
from backend.services.edit_history import flatten, update_with_history
from backend.services.mongosh_text import command_text


def get_players(team_id: int | None = None):
    team_names = {team["_id"]: team["name"] for team in get_collection("teams").find({}, {"name": 1})}
    query = {"currentTeamId": team_id} if team_id is not None else {}
    rows = []
    for player in get_collection("players").find(query).sort("shortName", 1):
        rows.append({
            "id": player["_id"],
            "shortName": player.get("shortName"),
            "role": (player.get("role") or {}).get("name"),
            "birthDate": player.get("birthDate"),
            "foot": player.get("foot"),
            "height": player.get("height"),
            "team": team_names.get(player.get("currentTeamId")),
            "currentTeamId": player.get("currentTeamId"),
            "nationalTeamId": player.get("currentNationalTeamId"),
            "marketValueEUR": player.get("marketValueEUR"),
            "tags": player.get("tags", []),
            "verifiedAt": player.get("verifiedAt"),
        })
    return rows


def get_player_by_id(player_id: int):
    player = get_collection("players").find_one({"_id": player_id})
    if player is None:
        raise HTTPException(404, f"Player {player_id} not found")
    return {"id": player_id, "doc": player, "flat": flatten(player)}


def update_players(items: list[UpdateItem]):
    players = get_collection("players")
    return [update_with_history(players, item.id, item.changes) for item in items]


def bulk_update_players(body: BulkRequest):
    value = body.value
    if body.op in ("set_value", "mul_value") and not isinstance(value, (int, float)):
        raise HTTPException(400, "value must be a number")
    if body.op in ("push_tag", "pull_tag") and not (isinstance(value, str) and value.strip()):
        raise HTTPException(400, "value must be a tag (text)")
    if body.op == "push_tags" and not (isinstance(value, list) and value):
        raise HTTPException(400, "value must be a list of tags")

    updates = {
        "set_verified": {"$set": {"verifiedAt": datetime.now(timezone.utc)}},
        "unset_verified": {"$unset": {"verifiedAt": ""}},
        "set_value": {"$set": {"marketValueEUR": value}},
        "mul_value": {"$mul": {"marketValueEUR": value}},
        "push_tag": {"$push": {"tags": value}},
        "push_tags": {"$push": {"tags": {"$each": value}}},
        "pull_tag": {"$pull": {"tags": value}},
    }
    query = {"currentTeamId": body.team_id}
    update = updates[body.op]
    result = get_collection("players").update_many(query, update)
    return {
        "op": body.op,
        "team_id": body.team_id,
        "matched_count": result.matched_count,
        "modified_count": result.modified_count,
        "mongosh": command_text("players", "updateMany", query, update),
    }


def get_player_impact(player_id: int):
    if get_collection("players").count_documents({"_id": player_id}) == 0:
        raise HTTPException(404, f"Player {player_id} not found")
    return {"id": player_id, "events": get_collection("events").count_documents({"player.id": player_id})}


def delete_player(player_id: int):
    impact = get_player_impact(player_id)
    result = get_collection("players").delete_one({"_id": player_id})
    return {
        "id": player_id,
        "deleted": result.deleted_count,
        "events_kept": impact["events"],
        "mongosh": command_text("players", "deleteOne", {"_id": player_id}),
    }
