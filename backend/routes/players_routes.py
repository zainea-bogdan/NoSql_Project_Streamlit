from fastapi import APIRouter

from backend.controllers import players_controller as players

router = APIRouter(prefix="/players", tags=["players"])

router.get("")(players.get_players)
router.patch("")(players.update_players)
router.post("/bulk")(players.bulk_update_players)
router.get("/{player_id}")(players.get_player_by_id)
router.get("/{player_id}/impact")(players.get_player_impact)
router.delete("/{player_id}")(players.delete_player)
