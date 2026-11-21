from datetime import datetime, timezone

from fastapi import HTTPException

from backend.services.mongosh_text import command_text

NOT_EDITABLE = {"_id", "wyId", "editHistory", "imageDataURL"}


def flatten(doc, prefix=""):
    """{"role": {"name": "Defender"}} -> {"role.name": "Defender"}. Lists are skipped."""
    flat = {}
    for key, value in doc.items():
        if key in NOT_EDITABLE or isinstance(value, list):
            continue
        if isinstance(value, dict):
            flat.update(flatten(value, prefix + key + "."))
        else:
            flat[prefix + key] = value
    return flat


def is_empty(value):
    return value is None or value == ""


def update_with_history(collection, doc_id, changes):
    """$set changed fields, $unset emptied fields, $push every change into editHistory."""
    doc = collection.find_one({"_id": doc_id})
    if doc is None:
        raise HTTPException(404, f"Document {doc_id} not found")
    current = flatten(doc)

    to_set, to_unset, diff = {}, {}, []
    for field, new in changes.items():
        if field.split(".")[0] in NOT_EDITABLE:
            raise HTTPException(400, f"{field} cannot be edited")
        old = current.get(field)
        if isinstance(new, str):
            new = new.strip()
        if old == new or (is_empty(old) and is_empty(new)):
            continue
        if is_empty(new):
            to_unset[field] = ""
            new = None
        else:
            to_set[field] = new
        diff.append({"field": field, "old": old, "new": new})

    if not diff:
        return {"id": doc_id, "modified": 0, "diff": [], "editHistory": doc.get("editHistory", [])[-5:]}

    now = datetime.now(timezone.utc)
    update = {}
    if to_set:
        update["$set"] = to_set
    if to_unset:
        update["$unset"] = to_unset
    update["$push"] = {"editHistory": {"$each": [{**change, "at": now} for change in diff]}}

    result = collection.update_one({"_id": doc_id}, update)
    history = collection.find_one({"_id": doc_id})["editHistory"][-5:]
    return {
        "id": doc_id,
        "modified": result.modified_count,
        "diff": diff,
        "editHistory": history,
        "mongosh": command_text(collection.name, "updateOne", {"_id": doc_id}, update),
    }
