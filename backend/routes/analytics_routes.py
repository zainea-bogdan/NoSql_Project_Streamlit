from fastapi import APIRouter

from backend.controllers import analytics_controller as analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])

router.get("")(analytics.get_queries)
router.post("/{query_id}")(analytics.run_query)
