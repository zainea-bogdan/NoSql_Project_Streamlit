from backend.db import get_collection


def get_matches():
    rows = []
    for match in get_collection("matches").find({}, {"label": 1, "dateutc": 1}).sort("date", 1):
        rows.append({"_id": match["_id"], "label": match.get("label"), "date": match.get("dateutc")})
    return rows
