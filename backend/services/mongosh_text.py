"""Turns the Python query (the one that runs) into display text: mongosh chained style and PyMongo."""
import json
import re
from datetime import datetime

WIDTH = 78
JS_KEY = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def value_text(value, js):
    if value is None:
        return "null" if js else "None"
    if isinstance(value, bool):
        return ("true" if value else "false") if js else str(value)
    if isinstance(value, datetime):
        return f'new Date("{value.isoformat()}")' if js else f"datetime.fromisoformat({value.isoformat()!r})"
    if isinstance(value, (int, float)):
        return repr(value)
    return json.dumps(str(value), ensure_ascii=False)


def key_text(key, js):
    return key if js and JS_KEY.match(key) else json.dumps(key, ensure_ascii=False)


def one_line(value, js):
    if isinstance(value, dict):
        return "{" + ", ".join(f"{key_text(k, js)}: {one_line(v, js)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(one_line(v, js) for v in value) + "]"
    return value_text(value, js)


def pretty(value, js=True, indent=0, used=0):
    """Short dicts/lists stay on one line, long ones are split (2 spaces for JS, 4 for Python)."""
    text = one_line(value, js)
    if not isinstance(value, (dict, list)) or not value or indent + used + len(text) <= WIDTH:
        return text
    step = 2 if js else 4
    pad = " " * (indent + step)
    if isinstance(value, dict):
        lines = [f"{pad}{key_text(k, js)}: {pretty(v, js, indent + step, len(k) + 4)}" for k, v in value.items()]
        return "{\n" + ",\n".join(lines) + "\n" + " " * indent + "}"
    lines = [pad + pretty(v, js, indent + step) for v in value]
    return "[\n" + ",\n".join(lines) + "\n" + " " * indent + "]"


def find_text(collection, query, projection, sort=None, limit=None):
    mongosh = f"db.{collection}.find({pretty(query, used=20)})\n.projection({pretty(projection, used=12)})"
    python = f"query = {pretty(query, False, used=8)}\nprojection = {pretty(projection, False, used=13)}\n"
    chain = f"    db.{collection}.find(query, projection)"
    if sort:
        mongosh += f"\n.sort({pretty(sort)})"
        chain += "\n    .sort([" + ", ".join(f'("{k}", {v})' for k, v in sort.items()) + "])"
    if limit:
        mongosh += f"\n.limit({limit})"
        chain += f"\n    .limit({limit})"
    python += f"rows = list(\n{chain}\n)"
    return mongosh, python


def aggregate_text(collection, pipeline, var="pipeline", rows="rows"):
    stages = [f"db.{collection}.aggregate()"]
    for stage in pipeline:
        operator, body = next(iter(stage.items()))
        stages.append(f".{operator[1:]}({pretty(body, used=len(operator) + 2)})")
    python = f"{var} = {pretty(pipeline, False, used=len(var) + 3)}\n{rows} = list(db.{collection}.aggregate({var}))"
    return "\n".join(stages), python


def command_text(collection, method, query, update=None):
    """Display text for updateOne / updateMany / deleteOne / deleteMany."""
    if update is None:
        return f"db.{collection}.{method}({pretty(query)})"
    return f"db.{collection}.{method}(\n  {pretty(query, indent=2)},\n  {pretty(update, indent=2)}\n)"
