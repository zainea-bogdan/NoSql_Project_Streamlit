from fastapi import HTTPException

from backend.db import get_collection
from backend.services.query_runner import run_aggregate

# 3x3 pitch grid. location.x goes from own goal (0) to the opponent goal (100)
ZONE_FIELDS = {
    "third": {"$switch": {
        "branches": [
            {"case": {"$lt": ["$location.x", 33]}, "then": "DEF"},
            {"case": {"$and": [{"$gte": ["$location.x", 33]}, {"$lt": ["$location.x", 66]}]}, "then": "MID"},
        ],
        "default": "ATT",
    }},
    "lane": {"$switch": {
        "branches": [
            {"case": {"$lt": ["$location.y", 33]}, "then": "LEFT"},
            {"case": {"$lt": ["$location.y", 66]}, "then": "CENTER"},
        ],
        "default": "RIGHT",
    }},
}


def a1_danger_zones(match_id, min_actions):
    pipeline = [
        {"$match": {"matchId": match_id, "$or": [{"type.primary": "shot"}, {"type.secondary": "key_pass"}]}},
        {"$addFields": ZONE_FIELDS},
        {"$group": {
            "_id": {"team": "$team.name", "third": "$third", "lane": "$lane"},
            "actions": {"$sum": 1},
            "xg": {"$sum": {"$ifNull": ["$shot.xg", 0]}},
        }},
        {"$match": {"actions": {"$gte": min_actions}}},
        {"$project": {
            "_id": 0,
            "team": "$_id.team",
            "teamCode": {"$toUpper": "$_id.team"},
            "zone": {"$concat": ["$_id.third", "-", "$_id.lane"]},
            "third": "$_id.third",
            "lane": "$_id.lane",
            "actions": 1,
            "xg": {"$round": ["$xg", 2]},
        }},
        {"$sort": {"team": 1, "xg": -1}},
    ]
    return run_aggregate("events", pipeline)


# 0 = minutes 0-15, 1 = 15-30, ... 5 = 75-90+
PHASE = {"$toInt": {"$min": [{"$floor": {"$divide": ["$minute", 15]}}, 5]}}
IS_PASS = {"$eq": ["$type.primary", "pass"]}
PHASE_METRICS = {
    "events": {"$sum": 1},
    "passes": {"$sum": {"$cond": [IS_PASS, 1, 0]}},
    "accurate": {"$sum": {"$cond": [{"$eq": ["$pass.accurate", True]}, 1, 0]}},
    "finalThirdEntries": {"$sum": {"$cond": [
        {"$and": [IS_PASS, {"$lt": ["$location.x", 66]}, {"$gte": ["$pass.endLocation.x", 66]}]}, 1, 0]}},
    "xg": {"$sum": {"$ifNull": ["$shot.xg", 0]}},
    "avgPassLength": {"$avg": "$pass.length"},
}
PASS_ACCURACY = {"$cond": [
    {"$gt": ["$passes", 0]},
    {"$round": [{"$multiply": [{"$divide": ["$accurate", "$passes"]}, 100]}, 1]},
    0,
]}


def a2_control_by_phase(match_id):
    pipeline = [
        {"$match": {"matchId": match_id}},
        {"$addFields": {"phase": PHASE}},
        {"$addFields": {"phaseLabel": {"$cond": [
            {"$eq": ["$phase", 5]},
            "75-90+",
            {"$concat": [
                {"$toString": {"$multiply": ["$phase", 15]}},
                "-",
                {"$toString": {"$multiply": [{"$add": ["$phase", 1]}, 15]}},
            ]},
        ]}}},
        {"$group": {"_id": {"team": "$team.name", "phase": "$phase", "label": "$phaseLabel"}, **PHASE_METRICS}},
        {"$project": {
            "_id": 0,
            "team": "$_id.team",
            "phase": "$_id.phase",
            "phaseLabel": "$_id.label",
            "events": 1,
            "passes": 1,
            "passAccuracy": PASS_ACCURACY,
            "finalThirdEntries": 1,
            "xg": {"$round": ["$xg", 2]},
            "avgPassLength": {"$round": [{"$ifNull": ["$avgPassLength", 0]}, 1]},
        }},
        {"$sort": {"team": 1, "phase": 1}},
    ]
    # match average for one team in one phase = match totals / number of (team, phase) cells
    baseline = [
        {"$match": {"matchId": match_id}},
        {"$addFields": {"phase": PHASE}},
        {"$group": {"_id": None, "cells": {"$addToSet": {"team": "$team.name", "phase": "$phase"}}, **PHASE_METRICS}},
        {"$addFields": {"cellCount": {"$size": "$cells"}}},
        {"$project": {
            "_id": 0,
            "team": {"$literal": "Match average"},
            "events": {"$round": [{"$divide": ["$events", "$cellCount"]}, 1]},
            "passes": {"$round": [{"$divide": ["$passes", "$cellCount"]}, 1]},
            "passAccuracy": PASS_ACCURACY,
            "finalThirdEntries": {"$round": [{"$divide": ["$finalThirdEntries", "$cellCount"]}, 1]},
            "xg": {"$round": [{"$divide": ["$xg", "$cellCount"]}, 2]},
            "avgPassLength": {"$round": ["$avgPassLength", 1]},
        }},
    ]
    return run_aggregate("events", pipeline, {"baseline": baseline})


def a3_ball_progressors(match_id, min_passes, progressive_gain):
    pipeline = [
        {"$match": {"matchId": match_id, "type.primary": "pass", "pass.endLocation": {"$exists": True}}},
        {"$addFields": {"gain": {"$subtract": ["$pass.endLocation.x", "$location.x"]}}},
        {"$addFields": {"progressive": {"$cond": [{"$gte": ["$gain", progressive_gain]}, 1, 0]}}},
        {"$group": {
            "_id": "$player.id",
            "name": {"$first": "$player.name"},
            "team": {"$first": "$team.name"},
            "passes": {"$sum": 1},
            "accurate": {"$sum": {"$cond": [{"$eq": ["$pass.accurate", True]}, 1, 0]}},
            "progressive": {"$sum": "$progressive"},
            "avgGain": {"$avg": "$gain"},
        }},
        {"$match": {"passes": {"$gte": min_passes}}},
        {"$lookup": {"from": "players", "localField": "_id", "foreignField": "_id", "as": "profile"}},
        {"$unwind": {"path": "$profile", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 0,
            "playerId": "$_id",
            "fullName": {"$ifNull": [{"$concat": ["$profile.firstName", " ", "$profile.lastName"]}, "$name"]},
            "team": 1,
            "role": {"$ifNull": ["$profile.role.name", "unknown"]},
            "foot": "$profile.foot",
            "age": {"$dateDiff": {"startDate": {"$toDate": "$profile.birthDate"}, "endDate": "$$NOW", "unit": "year"}},
            "passes": 1,
            "progressive": 1,
            "accuracy": {"$round": [{"$multiply": [{"$divide": ["$accurate", "$passes"]}, 100]}, 1]},
            "progressiveShare": {"$round": [{"$multiply": [{"$divide": ["$progressive", "$passes"]}, 100]}, 1]},
            "avgGain": {"$round": ["$avgGain", 1]},
        }},
        {"$sort": {"progressive": -1}},
    ]
    return run_aggregate("events", pipeline)


def a4_attack_types(match_id, min_possessions):
    if get_collection("events").count_documents({"matchId": match_id, "possession.id": {"$exists": True}}, limit=1) == 0:
        raise HTTPException(422, f"Match {match_id} has no possession data (possession.id), so A4 cannot run.")
    pipeline = [
        {"$match": {"matchId": match_id, "possession.id": {"$exists": True}}},
        # one document per possession
        {"$group": {
            "_id": "$possession.id",
            "team": {"$first": "$possession.team.name"},
            "types": {"$first": "$possession.types"},
            "withShot": {"$max": {"$cond": [{"$eq": ["$possession.attack.withShot", True]}, 1, 0]}},
            "xg": {"$max": {"$ifNull": ["$possession.attack.xg", 0]}},
        }},
        {"$unwind": "$types"},
        {"$group": {
            "_id": {"team": "$team", "type": "$types"},
            "possessions": {"$count": {}},
            "withShot": {"$sum": "$withShot"},
            "xg": {"$sum": "$xg"},
        }},
        {"$match": {"possessions": {"$gte": min_possessions}}},
        {"$project": {
            "_id": 0,
            "team": "$_id.team",
            "type": "$_id.type",
            "possessions": 1,
            "withShot": 1,
            "shotRate": {"$round": [{"$multiply": [{"$divide": ["$withShot", "$possessions"]}, 100]}, 1]},
            "xg": {"$round": ["$xg", 2]},
            "xgPerPossession": {"$round": [{"$divide": ["$xg", "$possessions"]}, 3]},
        }},
        {"$sort": {"team": 1, "possessions": -1}},
    ]
    return run_aggregate("events", pipeline)


def a5_pressing(match_id):
    pipeline = [
        {"$match": {"matchId": match_id}},
        {"$addFields": {
            "isPass": {"$eq": ["$type.primary", "pass"]},
            "isDefensive": {"$or": [
                {"$in": ["$type.primary", ["interception", "infraction", "clearance"]]},
                {"$and": [
                    {"$eq": ["$type.primary", "duel"]},
                    {"$in": ["defensive_duel", {"$ifNull": ["$type.secondary", []]}]},
                ]},
            ]},
        }},
        # a pass counts for its opponent: the team that is pressing it
        {"$addFields": {"pressTeam": {"$cond": ["$isPass", "$opponentTeam.name", "$team.name"]}}},
        {"$group": {
            "_id": "$pressTeam",
            "oppPassesOwn60": {"$sum": {"$cond": [{"$and": ["$isPass", {"$lte": ["$location.x", 60]}]}, 1, 0]}},
            "defActionsHigh": {"$sum": {"$cond": [{"$and": ["$isDefensive", {"$gte": ["$location.x", 40]}]}, 1, 0]}},
            "highRecoveries": {"$sum": {"$cond": [
                {"$and": [
                    {"$in": ["recovery", {"$ifNull": ["$type.secondary", []]}]},
                    {"$gte": ["$location.x", 60]},
                ]}, 1, 0]}},
        }},
        {"$match": {"_id": {"$ne": None}}},
        # PPDA: opponent passes allowed per defensive action, lower = more intense pressing
        {"$project": {
            "_id": 0,
            "team": "$_id",
            "ppda": {"$round": [{"$divide": ["$oppPassesOwn60", {"$max": ["$defActionsHigh", 1]}]}, 2]},
            "oppPassesOwn60": 1,
            "defActionsHigh": 1,
            "highRecoveries": 1,
        }},
        {"$sort": {"ppda": 1}},
    ]
    zones = [
        {"$match": {
            "matchId": match_id,
            "$or": [
                {"type.primary": {"$in": ["interception", "infraction", "clearance"]}},
                {"type.primary": "duel", "type.secondary": "defensive_duel"},
                {"type.secondary": "recovery"},
            ],
        }},
        {"$addFields": ZONE_FIELDS},
        {"$group": {
            "_id": {"team": "$team.name", "third": "$third", "lane": "$lane"},
            "defActions": {"$sum": 1},
            "recoveries": {"$sum": {"$cond": [{"$in": ["recovery", {"$ifNull": ["$type.secondary", []]}]}, 1, 0]}},
        }},
        {"$project": {"_id": 0, "team": "$_id.team", "third": "$_id.third", "lane": "$_id.lane",
                      "defActions": 1, "recoveries": 1}},
        {"$sort": {"team": 1, "recoveries": -1}},
    ]
    return run_aggregate("events", pipeline, {"zones": zones})


def a6_young_players():
    pipeline = [
        {"$lookup": {"from": "players", "localField": "_id", "foreignField": "currentTeamId", "as": "players"}},
        {"$addFields": {"squadSize": {"$size": "$players"}, "listaJucatori": "$players.shortName"}},
        {"$unwind": "$players"},
        {"$lookup": {
            "from": "events",
            "localField": "players._id",
            "foreignField": "player.id",
            "pipeline": [{"$project": {"_id": 1}}],
            "as": "ev",
        }},
        {"$addFields": {
            "age": {"$dateDiff": {"startDate": {"$toDate": "$players.birthDate"}, "endDate": "$$NOW", "unit": "year"}},
            "involvement": {"$size": "$ev"},
        }},
        {"$addFields": {"ageBand": {"$switch": {
            "branches": [
                {"case": {"$eq": [{"$ifNull": ["$age", "unknown"]}, "unknown"]}, "then": "unknown"},
                {"case": {"$lt": ["$age", 21]}, "then": "U21"},
                {"case": {"$lte": ["$age", 29]}, "then": "21-29"},
            ],
            "default": "30+",
        }}}},
        {"$group": {
            "_id": {"team": "$name", "band": "$ageBand"},
            "squadSize": {"$first": "$squadSize"},
            "players": {"$sum": 1},
            "names": {"$push": "$players.shortName"},
            "events": {"$sum": "$involvement"},
            "avgAge": {"$avg": "$age"},
        }},
        # second group: team total, so every age band becomes a share of it
        {"$group": {
            "_id": "$_id.team",
            "teamEvents": {"$sum": "$events"},
            "bands": {"$push": {"band": "$_id.band", "squadSize": "$squadSize", "players": "$players",
                                "names": "$names", "events": "$events", "avgAge": "$avgAge"}},
        }},
        {"$match": {"teamEvents": {"$gt": 0}}},  # only teams that played in the ingested matches
        {"$unwind": "$bands"},
        {"$project": {
            "_id": 0,
            "team": "$_id",
            "band": "$bands.band",
            "players": "$bands.players",
            "squadSize": "$bands.squadSize",
            "avgAge": {"$round": ["$bands.avgAge", 1]},
            "events": "$bands.events",
            "eventShare": {"$round": [{"$multiply": [{"$divide": ["$bands.events", "$teamEvents"]}, 100]}, 1]},
            "names": "$bands.names",
        }},
        {"$sort": {"team": 1, "band": 1}},
    ]
    return run_aggregate("teams", pipeline)
