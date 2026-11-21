import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MONGO_URI = os.getenv("MONGO_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "").strip() or "wyscout_nosql"

COLLECTIONS = ["matches", "teams", "players", "events"]
INDEXES = {
    "matches": ["date"],
    "teams": ["name"],
    "players": ["currentTeamId", "shortName"],
    "events": ["matchId", "type.primary", "player.id", "team.id", "opponentTeam.id"],
}

client = None


def get_db():
    global client
    if not MONGO_URI:
        raise HTTPException(503, "MONGO_URI is not set. Put your Atlas connection string in .env and restart uvicorn.")
    if client is None:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    return client[DB_NAME]


def get_collection(name):
    return get_db()[name]


def create_indexes():
    for name, fields in INDEXES.items():
        for field in fields:
            get_collection(name).create_index(field)


def health():
    status = {"api": "ok", "db": DB_NAME, "counts": {}}
    if not MONGO_URI:
        return {**status, "mongo": "not_configured", "message": "MONGO_URI is not set in .env. Fill it in and restart uvicorn."}
    try:
        db = get_db()
        db.command("ping")
        counts = {name: db[name].estimated_document_count() for name in COLLECTIONS}
        return {**status, "mongo": "ok", "message": f"Connected, database '{DB_NAME}'.", "counts": counts}
    except PyMongoError as error:
        reason = str(error).split(", Timeout:")[0][:300]
        return {**status, "mongo": "error",
                "message": f"Cannot reach MongoDB: {reason}. Check MONGO_URI and Atlas Network Access."}
