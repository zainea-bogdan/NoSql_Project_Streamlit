from backend.services.query_runner import run_find


def r1_missed_big_chances(match_id, xg_min, from_minute):
    query = {
        "type.primary": "shot",
        "shot.xg": {"$gt": xg_min},
        "shot.isGoal": False,
        "minute": {"$gte": from_minute},
    }
    if match_id is not None:  # None = all matches
        query = {"matchId": match_id, **query}
    projection = {"_id": 0, "matchId": 1, "minute": 1, "player.name": 1, "team.name": 1,
                  "shot.xg": 1, "shot.onTarget": 1, "location": 1}
    return run_find("events", query, projection, sort={"shot.xg": -1}, limit=20)


def r2_scouting_shortlist(born_from, role_regex):
    query = {
        "foot": "left",
        "role.code2": {"$ne": "GK"},
        "birthDate": {"$gte": born_from},
    }
    if role_regex:
        query["role.name"] = {"$regex": role_regex, "$options": "i"}
    query["currentNationalTeamId"] = {"$exists": True, "$ne": None}
    projection = {"_id": 0, "shortName": 1, "birthDate": 1, "role.name": 1, "foot": 1,
                  "height": 1, "currentTeamId": 1, "currentNationalTeamId": 1}
    return run_find("players", query, projection, sort={"birthDate": -1, "shortName": 1})


def r3_box_defending(match_id):
    query = {
        "matchId": match_id,
        "$and": [
            {"location.x": {"$gte": 0, "$lte": 16}},
            {"location.y": {"$gt": 19, "$lt": 81}},
        ],
        "$or": [
            {"type.primary": {"$in": ["clearance", "interception"]}},
            {"type.primary": "duel", "type.secondary": "defensive_duel"},
        ],
    }
    projection = {"_id": 0, "minute": 1, "team.name": 1, "player.name": 1, "type.primary": 1, "location": 1}
    return run_find("events", query, projection, sort={"minute": 1})
