import asyncio
from backend.app.db.database import create_tables

if __name__ == "__main__":
    asyncio.run(create_tables())
    print("Database tables created successfully alongside pgvector.")
