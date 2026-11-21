"""EVERY HTTP call of the frontend lives here. Pages never talk to MongoDB directly."""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API_URL = (os.getenv("API_URL", "").strip() or "http://localhost:8000").rstrip("/")
START_HINT = "uvicorn backend.main:app --reload"


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message

    def __str__(self) -> str:
        return self.message


def _request(method: str, path: str, timeout: int = 60, **kwargs):
    try:
        response = requests.request(method, API_URL + path, timeout=timeout, **kwargs)
    except requests.ConnectionError:
        raise ApiError(0, f"Cannot reach the API at {API_URL}. Start it with: {START_HINT}") from None
    except requests.Timeout:
        raise ApiError(0, f"The API at {API_URL} did not answer within {timeout}s.") from None
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        if isinstance(detail, list):  # FastAPI request validation errors
            detail = "; ".join(f"{'.'.join(map(str, d.get('loc', [])))}: {d.get('msg')}" for d in detail)
        raise ApiError(response.status_code, str(detail))
    return response.json()


# ---------------------------------------------------------------- health / ingest
def health() -> dict:
    return _request("GET", "/health", timeout=15)


def ingest(entity: str, files: list[tuple[str, bytes]], dry_run: bool = True) -> dict:
    multipart = [("files", (name, data, "application/json")) for name, data in files]
    return _request("POST", f"/ingest/{entity}", params={"dry_run": str(dry_run).lower()},
                    files=multipart, timeout=300)


# ---------------------------------------------------------------- matches / teams
def matches() -> list[dict]:
    return _request("GET", "/matches")


def teams() -> list[dict]:
    return _request("GET", "/teams")


def team(team_id: int) -> dict:
    return _request("GET", f"/teams/{team_id}")


def patch_teams(items: list[dict]) -> list[dict]:
    return _request("PATCH", "/teams", json=items)


def team_impact(team_id: int) -> dict:
    return _request("GET", f"/teams/{team_id}/impact")


def delete_team(team_id: int, cascade_players: bool = False) -> dict:
    return _request("DELETE", f"/teams/{team_id}", params={"cascade_players": str(cascade_players).lower()})


# ---------------------------------------------------------------- players
def players(team_id: int | None = None) -> list[dict]:
    params = {"team_id": team_id} if team_id is not None else None
    return _request("GET", "/players", params=params)


def player(player_id: int) -> dict:
    return _request("GET", f"/players/{player_id}")


def patch_players(items: list[dict]) -> list[dict]:
    return _request("PATCH", "/players", json=items)


def bulk_players(team_id: int, op: str, value=None) -> dict:
    return _request("POST", "/players/bulk", json={"team_id": team_id, "op": op, "value": value})


def player_impact(player_id: int) -> dict:
    return _request("GET", f"/players/{player_id}/impact")


def delete_player(player_id: int) -> dict:
    return _request("DELETE", f"/players/{player_id}")


# ---------------------------------------------------------------- analytics
def analytics_catalog() -> list[dict]:
    return _request("GET", "/analytics")


def run_query(query_id: str, params: dict) -> dict:
    return _request("POST", f"/analytics/{query_id}", json=params, timeout=120)
