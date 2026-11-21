from backend.db import get_collection
from backend.services.mongosh_text import aggregate_text, find_text


def run_find(collection, query, projection, sort=None, limit=None):
    cursor = get_collection(collection).find(query, projection)
    if sort:
        cursor = cursor.sort(list(sort.items()))
    if limit:
        cursor = cursor.limit(limit)
    mongosh, python = find_text(collection, query, projection, sort, limit)
    return {"rows": list(cursor), "mongosh": mongosh, "python": python, "extra": {}}


def run_aggregate(collection, pipeline, extra_pipelines=None):
    """extra_pipelines, e.g. {"baseline": [...]}: second pipelines whose rows are shown next to the main ones."""
    rows = list(get_collection(collection).aggregate(pipeline))
    mongosh, python = aggregate_text(collection, pipeline)
    extra = {}
    for name, extra_pipeline in (extra_pipelines or {}).items():
        extra[name] = list(get_collection(collection).aggregate(extra_pipeline))
        extra_mongosh, extra_python = aggregate_text(collection, extra_pipeline, f"{name}_pipeline", name)
        mongosh += f"\n\n// {name}_pipeline\n{extra_mongosh}"
        python += f"\n\n# {name}_pipeline\n{extra_python}"
    return {"rows": rows, "mongosh": mongosh, "python": python, "extra": extra}
