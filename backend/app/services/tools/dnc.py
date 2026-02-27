"""
Do Not Call (DNC) list checker.
Pre-dial compliance check.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Contact

log = logging.getLogger(__name__)


async def check_dnc(tenant_id: UUID, phone_number: str, db: AsyncSession) -> bool:
    """
    Check if a phone number is on the DNC list.
    Returns True if the number should NOT be called.
    """
    try:
        result = await db.execute(
            select(Contact.is_dnc).where(
                Contact.tenant_id == tenant_id,
                Contact.phone_number == phone_number,
            )
        )
        contact_dnc = result.scalar_one_or_none()
        if contact_dnc is True:
            return True
    except Exception:
        pass

    return False