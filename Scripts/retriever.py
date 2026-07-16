import os
import sys
import chromadb
from mistralai.client import Mistral

# --- Configuration ---
CHROMA_DB_PATH = "chroma_data"
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

# Mistral Models
EMBED_MODEL = "mistral-embed"
CHAT_MODEL = "mistral-small-latest" 

if not MISTRAL_API_KEY:
    print("Error: MISTRAL_API_KEY environment variable not set.")
    sys.exit(1)

# Initialize clients
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

try:
    collection = chroma_client.get_collection(name="upazila_rag_collection")
except ValueError:
    print("Error: Collection 'upazila_rag_collection' not found.")
    sys.exit(1)

def retrieve_context(query, top_k=3):
    """Embeds the query and fetches the top matching chunks from ChromaDB."""
    print(f"Embedding query: '{query}'...")
    
    embed_response = mistral_client.embeddings.create(
        model=EMBED_MODEL,
        inputs=[query]
    )
    query_embedding = embed_response.data[0].embedding
    
    print(f"Searching ChromaDB for the top {top_k} matching chunks...")
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    return results

def generate_answer(query, context_chunks):
    """Feeds the retrieved context to the LLM to generate a factual answer."""
    print("Synthesizing response via Mistral LLM...\n")
    
    context_text = "\n\n---\n\n".join(context_chunks)
    
    prompt = f"""You are a helpful assistant with deep knowledge about Bangladesh Upazilas.
    
    The provided CONTEXT is written in Bengali, but the user's QUESTION may be in English or Bengali. 
    Map English names (like "Thakurgaon") to their corresponding Bengali names (like "ঠাকুরগাঁও") in the text.
    
    Answer the user's question accurately in English (or the language asked) using ONLY the facts present in the context below. 
    If the answer cannot be found or inferred from the context, say "I don't have enough information in my database to answer that."
    
    CONTEXT:
    {context_text}
    
    QUESTION:
    {query}
    """
    
    messages = [
        {"role": "system", "content": "You are a strict RAG assistant. Rely exclusively on the provided context."},
        {"role": "user", "content": prompt}
    ]
    
    # FIXED: Direct call to the v1.x+ SDK complete method
    chat_response = mistral_client.chat.complete(
        model=CHAT_MODEL,
        messages=messages
    )
    
    return chat_response.choices[0].message.content

def main():
    if len(sys.argv) < 2:
        print('Usage: python3 retrieve_rag.py "Your question here"')
        sys.exit(1)
        
    user_query = sys.argv[1]
    
    # Step 1: Retrieve
    results = retrieve_context(user_query, top_k=3)
    
    documents = results['documents'][0]
    metadatas = results['metadatas'][0]
    
    if not documents:
        print("No relevant context found in the database.")
        sys.exit(0)
        
    print("\n========================================")
    print("          RETRIEVED SOURCES             ")
    print("========================================")
    for i, (doc, meta) in enumerate(zip(documents, metadatas)):
        print(f"Source {i+1} | Upazila: {meta['title']} (WP ID: {meta['wp_id']})")
        print(f"Preview: {doc[:150].strip()}...\n")
        
    # Step 2: Generate
    answer = generate_answer(user_query, documents)
    
    print("========================================")
    print("             FINAL ANSWER               ")
    print("========================================")
    print(answer)
    print("\n")

if __name__ == "__main__":
    main()