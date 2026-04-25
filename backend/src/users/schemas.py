from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserSchema(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    is_active: bool
    email: str
    additional_emails: Optional[list]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
