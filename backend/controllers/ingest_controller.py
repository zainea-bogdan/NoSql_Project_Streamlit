import json
from collections import defaultdict

from fastapi import File, HTTPException, UploadFile
from pymongo.errors import BulkWriteError

from backend.db import get_collection

# a record without these keys is rejected (ex: a players file dropped in the events zone)
REQUIRED_KEYS = {
    "teams": ["wyId", "name"],
    "players": ["wyId", "shortName"],
    "matches": ["wyId", "label"],
    "events": ["id", "matchId", "type"],
}


def ingest_files(entity: str, files: list[UploadFile] = File(...), dry_run: bool = True):
    if entity not in REQUIRED_KEYS:
        raise HTTPException(400, f"Unknown entity {entity}. Use one of: {', '.join(REQUIRED_KEYS)}")
    report = {"entity": entity, "dry_run": dry_run, "files": [], "accepted": 0, "skipped": 0,
              "rejected": 0, "inserted": 0, "errors": [], "warnings": []}

    records = read_records(entity, files, report)
    if entity == "events":
        docs = check_events(records, report)
    elif entity == "matches":
        docs = check_matches(records, report)
    else:
        docs = check_teams_or_players(entity, records, report)
    report["accepted"] = len(docs)

    if not dry_run and docs:
        try:
            result = get_collection(entity).insert_many(docs, ordered=False)
            report["inserted"] = len(result.inserted_ids)
        except BulkWriteError as error:
            report["inserted"] = error.details["nInserted"]
            report["errors"].append(f"{len(error.details['writeErrors'])} documents failed to insert")
    return report


def read_records(entity, files, report):
    """Accepts a list of objects, one object, or a wrapper like {"events": [...]}."""
    records = []
    for file in files:
        try:
            data = json.loads(file.file.read())
        except ValueError:
            report["errors"].append(f"{file.filename}: not valid JSON, file rejected")
            continue
        if isinstance(data, dict):
            data = data.get(entity, data)
        if not isinstance(data, list):
            data = [data]

        valid = [r for r in data if isinstance(r, dict) and all(r.get(key) is not None for key in REQUIRED_KEYS[entity])]
        invalid = len(data) - len(valid)
        if invalid:
            report["rejected"] += invalid
            report["errors"].append(f"{file.filename}: {invalid} record(s) without {REQUIRED_KEYS[entity]}. "
                                    f"Is this the right file for {entity}?")
        for record in valid:
            record.pop("imageDataURL", None)
        records += valid
        report["files"].append({"name": file.filename, "records": len(data), "valid": len(valid)})
    return records


def check_teams_or_players(entity, records, report):
    """Ids already stored (or repeated in the upload) are skipped."""
    ids = [r["wyId"] for r in records]
    stored = {doc["_id"] for doc in get_collection(entity).find({"_id": {"$in": ids}}, {"_id": 1})}
    docs, seen, skipped = [], set(), []
    for record in records:
        if record["wyId"] in stored or record["wyId"] in seen:
            skipped.append(record["wyId"])
        else:
            seen.add(record["wyId"])
            docs.append({"_id": record["wyId"], **record})
    if skipped:
        report["skipped"] = len(skipped)
        report["warnings"].append(f"{len(skipped)} {entity} already in the database or repeated, skipped: {skipped[:10]}")

    if entity == "players":
        team_ids = {team["_id"] for team in get_collection("teams").find({}, {"_id": 1})}
        outside = [d for d in docs if d.get("currentTeamId") not in team_ids]
        if outside:
            clubs = {d.get("currentTeamId") for d in outside}
            report["warnings"].append(f"{len(outside)} players belong to {len(clubs)} team(s) not in the teams "
                                      "collection (other clubs, or teams not ingested yet)")
    return docs


def check_matches(records, report):
    ids = [r["wyId"] for r in records]
    stored = {doc["_id"] for doc in get_collection("matches").find({"_id": {"$in": ids}}, {"_id": 1})}
    docs, seen = [], set()
    for match in records:
        if match["wyId"] in stored or match["wyId"] in seen:
            report["rejected"] += 1
            report["errors"].append(f"match {match['wyId']} ({match['label']}) already exists, rejected")
        else:
            seen.add(match["wyId"])
            docs.append({"_id": match["wyId"], **match})
    return docs


def check_events(records, report):
    """A match is accepted or rejected as a whole, so a match never ends up half-duplicated."""
    by_match = defaultdict(list)
    for event in records:
        by_match[event["matchId"]].append(event)
    match_ids = list(by_match)
    stored = set(get_collection("events").distinct("matchId", {"matchId": {"$in": match_ids}}))
    known = {m["_id"] for m in get_collection("matches").find({"_id": {"$in": match_ids}}, {"_id": 1})}

    docs = []
    for match_id, events in by_match.items():
        ids = [event["id"] for event in events]
        if match_id in stored:
            report["rejected"] += len(events)
            report["errors"].append(f"match {match_id}: its events are already in the database, "
                                    f"all {len(events)} rejected")
        elif len(ids) != len(set(ids)):
            report["rejected"] += len(events)
            report["errors"].append(f"match {match_id}: duplicate event ids in the upload, all {len(events)} rejected")
        else:
            if match_id not in known:
                report["warnings"].append(f"match {match_id} is not in the matches collection yet")
            docs += [{"_id": event["id"], **event} for event in events]
    return docs
