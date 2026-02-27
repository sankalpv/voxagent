"""
Do Not Call (DNC) list checker.

Pre-dial compliance check: verifies a phone number is not on the tenant's DNC list
before initiating a call. Required for TCPA compliance.
"""

import logging
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Contact

log = logging.getLogger(__name__)


async def check_dnc(tenant_id: UUID, phone_number: str, db: AsyncSession) -> bool:
    """
    Check if a phone number is on the DNC list.
    Checks both the dnc_numbers table and the contact's is_dnc flag.
    Returns True if the number should NOT be called.
    """
    # Check dedicated DNC table
    from sqlalchemy import text
    result = await db.execute(
        text(
            "SELECT 1 FROM dnc_numbers WHERE tenant_id = :tid AND phone_number = :phone LIMIT 1"
        ),
        {"tid": str(tenant_id), "phone": phone_number},
    )
    if result.scalar():
        log.info("dnc_blocked", tenant_id=str(tenant_id), phone=phone_number, source="dnc_table")
        return True

    # Check contact's is_dnc flag
    result = await db.execute(
        select(Contact.is_dnc).where(
            Contact.tenant_id == tenant_id,
            Contact.phone_number == phone_number,
        )
    )
    contact_dnc = result.scalar_one_or_none()
    if contact_dnc is True:
        log.info("dnc_blocked", tenant_id=str(tenant_id), phone=phone_number, source="contact_flag")
        return True

    return False