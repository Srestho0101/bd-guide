import os
import sqlite3
import time
import sys
import chromadb
from mistralai.client import Mistral

# --- Configuration ---
# Updated to match the current project directory structure
SQLITE_DB_PATH = "../DB/upazila_text.db" 
CHROMA_DB_PATH = "chroma_data"

# Mistral Configuration
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    print("Error: MISTRAL_API_KEY environment variable not set.")
    sys.exit(1)

EMBED_MODEL = "mistral-embed"

# Chunking Configuration
CHUNK_SIZE = 1000 
CHUNK_OVERLAP = 200 # Prevents context loss between chunks

# Initialize clients
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

# Using cosine similarity which is standard for RAG
collection = chroma_client.get_or_create_collection(
    name="upazila_rag_collection",
    metadata={"hnsw:space": "cosine"} 
)

def chunk_text(text, chunk_size, overlap):
    """Splits text using a sliding window to maintain overlapping context."""
    chunks = []
    start = 0
    text_length = len(text)
    
    if not text.strip():
        return chunks
        
    while start < text_length:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
        
    return chunks

def main():
    print(f"Connecting to SQLite database at {SQLITE_DB_PATH}...")
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"Error: Could not find database at {SQLITE_DB_PATH}.")
        sys.exit(1)

    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        sys.exit(1)
    
    # Executing the recommended concatenated RAG query
    query = """
        SELECT 
            wp_id,
            title,
            'History: ' || IFNULL(history_info, '') || 
            ' Geography: ' || IFNULL(geographic_info, '') || 
            ' Travel: ' || IFNULL(travel_info, '') || 
            ' Development: ' || IFNULL(development_info, '') AS full_context
        FROM upazilas;
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    print(f"Fetched {len(rows)} highly informative upazilas from SQLite.")

    # Process each upazila record
    for row in rows:
        wp_id = row[0]
        title = row[1]
        full_context = row[2]
        
        print(f"Processing wp_id: {wp_id} | Title: {title}")
        
        if not full_context.strip():
            continue
            
        # 1. Chunk the massive concatenated text
        chunks = chunk_text(full_context, CHUNK_SIZE, CHUNK_OVERLAP)
        
        if not chunks:
            continue
            
        # 2. Prepare batch lists for Mistral and ChromaDB
        doc_ids = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            doc_ids.append(f"wp_{wp_id}_chunk_{i}")
            metadatas.append({
                "wp_id": wp_id,
                "title": title,
                "chunk_index": i
            })
            
        try:
            # 3. Batch API Call to Mistral (Embeds all chunks for this upazila at once)
            embed_response = mistral_client.embeddings.create(
                model=EMBED_MODEL,
                inputs=chunks
            )
            
            # Extract the raw embedding vectors from the response
            embeddings = [item.embedding for item in embed_response.data]
            
            # 4. Batch Insert into ChromaDB
            collection.add(
                ids=doc_ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas
            )
            
            # 5. Pause to respect Mistral Free Tier rate limits
            time.sleep(1.5) 
            
        except Exception as e:
            print(f"Error processing {title} (wp_id: {wp_id}): {e}")

    print("\nDatabase vectorization complete. ChromaDB is fully populated and ready for retrieval.")

if __name__ == "__main__":
    main()