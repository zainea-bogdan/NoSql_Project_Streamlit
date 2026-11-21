from fastapi import HTTPException

from backend.db import get_collection
from backend.schemas import UpdateItem
from backend.services.edit_history import flatten, update_with_history
from backend.services.mongosh_text import command_text


def get_teams():
    squad_sizes = get_collection("players").aggregate([{"$group": {"_id": "$currentTeamId", "n": {"$sum": 1}}}])
    squad_sizes = {row["_id"]: row["n"] for row in squad_sizes}
    rows = []
    for team in get_collection("teams").find().sort("name", 1):
        rows.append({
            "id": team["_id"],
            "name": team.get("name"),
            "officialName": team.get("officialName"),
            "city": team.get("city"),
            "area": (team.get("area") or {}).get("name"),
            "type": team.get("type"),
            "category": team.get("category"),
            "players": squad_sizes.get(team["_id"], 0),
        })
    return rows


def get_team_by_id(team_id: int):
    team = get_collection("teams").find_one({"_id": team_id})
    if team is None:
        raise HTTPException(404, f"Team {team_id} not found")
    return {"id": team_id, "doc": team, "flat": flatten(team)}


def update_teams(items: list[UpdateItem]):
    teams = get_collection("teams")
    return [update_with_history(teams, item.id, item.changes) for item in items]


def get_team_impact(team_id: int):
    if get_collection("teams").count_documents({"_id": team_id}) == 0:
        raise HTTPException(404, f"Team {team_id} not found")
    return {
        "id": team_id,
        "players": get_collection("players").count_documents({"currentTeamId": team_id}),
        "events": get_collection("events").count_documents({"team.id": team_id}),
    }


def delete_team(team_id: int, cascade_players: bool = False):
    """Events are never deleted: they are the match history."""
    impact = get_team_impact(team_id)
    result = get_collection("teams").delete_one({"_id": team_id})
    commands = [command_text("teams", "deleteOne", {"_id": team_id})]
    deleted_players = 0
    if cascade_players:
        deleted_players = get_collection("players").delete_many({"currentTeamId": team_id}).deleted_count
        commands.append(command_text("players", "deleteMany", {"currentTeamId": team_id}))
    return {
        "id": team_id,
        "deleted": result.deleted_count,
        "deleted_players": deleted_players,
        "players_kept": impact["players"] - deleted_players,
        "events_kept": impact["events"],
        "mongosh": "\n".join(commands),
    }
