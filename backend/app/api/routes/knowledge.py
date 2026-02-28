from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from backend.app.db.database import get_db
from backend.app.db.models import KnowledgeBase, Tenant, Document
from backend.app.services.knowledge_service import process_document

router = APIRouter()

# In a real app, this dependency would extract the tenant from the API Key or JWT.
# For now, we mock it by fetching the first dev tenant.
async def get_current_tenant(db: AsyncSession = Depends(get_db)) -> Tenant:
    tenant = await db.scalar(select(Tenant).where(Tenant.tier == 'standard'))
    if not tenant:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return tenant

@router.post("/", response_model=dict)
async def create_knowledge_base(
    name: str,
    description: str = "",
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Create a new logical Knowledge Base container for this Tenant."""
    kb = KnowledgeBase(
        tenant_id=tenant.id,
        name=name,
        description=description
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return {"id": str(kb.id), "name": kb.name, "status": "created"}

@router.post("/{kb_id}/documents", response_model=dict)
async def upload_document(
    kb_id: uuid.UUID,
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document (PDF or Text) to a Knowledge Base.
    The document will be chunked and vectorized asynchronously.
    """
    # Verify KB belongs to tenant
    kb = await db.scalar(select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id, 
        KnowledgeBase.tenant_id == tenant.id
    ))
    
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge Base not found")
        
    if file.content_type not in ["application/pdf", "text/plain"]:
        raise HTTPException(status_code=400, detail="Only PDF and Text files are supported")

    # Read bytes into memory
    file_bytes = await file.read()
    
    # 1. Create Document record in 'processing' status
    doc = Document(
        knowledge_base_id=kb.id,
        filename=file.filename,
        content_type=file.content_type,
        status="processing"
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    # 2. Process document synchronously (in production, use Celery/BackgroundTasks)
    # We do it directly here for the demo
    try:
        await process_document(doc, file_bytes, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")
        
    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status
    }
