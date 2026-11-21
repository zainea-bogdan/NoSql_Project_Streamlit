from fastapi import APIRouter

from backend.controllers import teams_controller as teams

router = APIRouter(prefix="/teams", tags=["teams"])

router.get("")(teams.get_teams)
router.patch("")(teams.update_teams)
router.get("/{team_id}")(teams.get_team_by_id)
router.get("/{team_id}/impact")(teams.get_team_impact)
router.delete("/{team_id}")(teams.delete_team)
