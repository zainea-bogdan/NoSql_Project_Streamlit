from fastapi import APIRouter

from backend.routes import analytics_routes, ingest_routes, matches_routes, players_routes, teams_routes

api_router = APIRouter()
api_router.include_router(ingest_routes.router)
api_router.include_router(matches_routes.router)
api_router.include_router(teams_routes.router)
api_router.include_router(players_routes.router)
api_router.include_router(analytics_routes.router)
