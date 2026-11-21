from fastapi import APIRouter

from backend.controllers import ingest_controller as ingest

router = APIRouter(prefix="/ingest", tags=["ingest"])

router.post("/{entity}")(ingest.ingest_files)
