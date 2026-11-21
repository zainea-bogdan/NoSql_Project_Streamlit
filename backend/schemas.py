from typing import Any, Literal

from pydantic import BaseModel


class UpdateItem(BaseModel):
    id: int
    changes: dict[str, Any]  # {"dotted.path": new value}, empty value = $unset


class BulkRequest(BaseModel):
    team_id: int
    op: Literal["set_verified", "unset_verified", "set_value", "mul_value", "push_tag", "push_tags", "pull_tag"]
    value: Any = None
