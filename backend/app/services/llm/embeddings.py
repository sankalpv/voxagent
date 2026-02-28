import httpx
import logging
from typing import List

from backend.app.core.config import settings

log = logging.getLogger(__name__)

async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate 768-dimensional embeddings for a list of text chunks
    using Google's gemini-embedding-001 model via direct REST API to avoid SDK/gRPC hangs.
    """
    if not texts:
        return []

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents?key={settings.gemini_api_key}"
    
    requests = []
    for text in texts:
        requests.append({
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": text}]}
        })
        
    payload = {"requests": requests}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            embeddings = []
            for item in data.get("embeddings", []):
                # Ensure it is exactly 768 dimensions for pgvector
                # (Google embeddings have Matryoshka properties making slicing valid)
                vector = item["values"][:768]
                embeddings.append(vector)
                
            return embeddings
        except Exception as e:
            log.error(f"Failed to generate embeddings via REST API: {e}")
            if hasattr(e, "response") and getattr(e, "response"):
                log.error(f"Response: {e.response.text}")
            raise
