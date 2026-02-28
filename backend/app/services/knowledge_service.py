import io
import logging
from typing import List
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Document, DocumentChunk
from backend.app.services.llm.embeddings import generate_embeddings

log = logging.getLogger(__name__)

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts all raw text from a PDF file."""
    reader = PdfReader(io.BytesIO(file_bytes))
    text_content = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_content.append(page_text)
    return "\n\n".join(text_content)

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Splits a long string into overlapping chunks of rough character lengths."""
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += (chunk_size - overlap)
        
    return [c for c in chunks if c]

async def process_document(document: Document, file_bytes: bytes, db: AsyncSession):
    """
    Extracts text from the document, chunks it, generates embeddings via Gemini,
    and saves the Vector(768) embeddings in the database.
    """
    try:
        if document.content_type == "application/pdf":
            raw_text = extract_text_from_pdf(file_bytes)
        else:
            # Assume plain text if not PDF
            raw_text = file_bytes.decode("utf-8")

        chunks = chunk_text(raw_text)
        if not chunks:
            log.warning(f"No text extracted from document {document.id}")
            document.status = "error"
            await db.commit()
            return

        # Generate vectors (Gemini text-embedding-004)
        embeddings = await generate_embeddings(chunks)

        # Batch insert chunks
        db_chunks = []
        for i, (chunk_str, embedding_vector) in enumerate(zip(chunks, embeddings)):
            db_chunks.append(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=i,
                    chunk_text=chunk_str,
                    embedding=embedding_vector
                )
            )
            
        db.add_all(db_chunks)
        document.status = "ready"
        await db.commit()
        log.info(f"Processed Document {document.id} into {len(chunks)} chunks.")

    except Exception as e:
        log.error(f"Error processing document {document.id}: {e}")
        document.status = "error"
        await db.commit()
        raise e

async def search_knowledge_base(kb_id: str, query: str, db: AsyncSession, limit: int = 3) -> str:
    """
    Embeds the user's query and finds the top 3 most relevant text chunks 
    from the pgvector database using Cosine Similarity (<=>).
    """
    # 1. Embed the search query
    try:
        response = await generate_embeddings([query])
        query_embedding = response[0]
    except Exception as e:
        log.error(f"Failed to embed RAG query: {e}")
        return ""

    # 2. Search pgvector using HNSW Exact Nearest Neighbor
    stmt = (
        select(DocumentChunk.chunk_text)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            Document.knowledge_base_id == kb_id,
            Document.status == 'ready'
        )
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    rows = result.scalars().all()
    
    if not rows:
        return "No relevant information found in the knowledge base."
        
    # Combine the top chunks into a single context string
    return "\n\n---\n\n".join(rows)
