from fastapi import APIRouter

from backend.controllers import matches_controller as matches

router = APIRouter(prefix="/matches", tags=["matches"])

router.get("")(matches.get_matches)
