# scripts/check_chroma.py
from app.services import vector_store

try:
    collection = vector_store.get_or_create_collection()
    total_records = collection.count()
    print(f"\n=========================================")
    print(f"📊 CHROMA DB DIAGNOSTIC CHECK")
    print(f"=========================================")
    print(f"✅ Total vectors inside collection: {total_records}")
    
    if total_records > 0:
        sample = collection.peek(limit=1)
        print(f"🔗 Sample Chunk ID in store: {sample['ids'][0] if sample['ids'] else 'None'}")
    print(f"=========================================\n")
except Exception as e:
    print(f"❌ Failed to connect to ChromaDB: {e}")