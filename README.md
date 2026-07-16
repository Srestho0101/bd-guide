# Documentation: Cross-Lingual RAG Backend Pipeline & Deployment

**Project Objective:**
Build a production-grade, high-performance Retrieval-Augmented Generation (RAG) backend API using FastAPI and ChromaDB. The pipeline takes the cleaned, high-density Bengali upazila database (`DB/upazila_text.db`), vectorizes it via Mistral AI embeddings, exposes a query endpoint, handles cross-lingual semantic matching, and deploys as a cloud service on Render.

---

## 1. Overview of the Architecture

The backend infrastructure expands the static SQLite dataset into an interactive, intelligent knowledge system through three main architectural components:

1. **`vectorize_rag.py`**: A batch-optimized ingestion script that extracts text documents using a concatenated multi-field schema query, splits texts with a sliding-window character chunker, generates embeddings via `mistral-embed`, and populates a localized persistent vector store.


2. **`main.py` (FastAPI Application)**: The core production web application that instantiates the persistent ChromaDB client, intercepts incoming JSON payloads, fetches the top-K relevant chunks, and coordinates the LLM answer synthesis.


3. **Render Cloud Infrastructure**: A containerized Linux web service hosting the live REST API, complete with environment variable sandboxing for secure LLM credential access.

---

## 2. The Pitfalls (And How We Solved Them)

Moving the processing architecture from local text parsing scripts into an operational cloud API revealed several critical challenges across vector spaces, dependency versions, and cloud network layer specifications.

### Pitfall 1: The Phantom Database (`no such table: upazilas`)

* **The Issue:** Attempting to verify or run queries against the SQLite database threw a fatal `sqlite3.OperationalError: no such table: upazilas`.


* **The Cause:** When SQLite is invoked against a path where a database file doesn't exist, it implicitly generates a completely empty database file in that directory rather than failing out. Because the source database had been reorganized into a subfolder (`DB/`), executing root directory commands caused SQLite to read blank ghost files.
* **The Fix:** Hardcoded the structural path mapping directly to the nested directory (`DB/upazila_text.db`) and systematically purged the unintended zero-byte database files generated in the root directory.

### Pitfall 2: The Mistral SDK Version Overhaul (`Chat object is not callable`)

* **The Issue:** The local retrieval pipeline abruptly crashed during chat synthesis with a `ModuleNotFoundError: No module named 'mistralai.models'` followed by a `TypeError: 'Chat' object is not callable`.
* **The Cause:** The development environment was running the overhauled Mistral Python SDK (v1.0.0+). The legacy implementation relied on structured `ChatMessage` object casting and functional syntax (`client.chat()`), which were entirely deprecated in the modern client class architecture.
* **The Fix:** Completely decoupled the data models from specific SDK abstractions by transforming the payload construction into raw Python dictionaries and routing calls through the updated class structure (`client.chat.complete()`).

### Pitfall 3: The Cross-Lingual System Lockout

* **The Issue:** Querying the database in English (e.g., "Tell me about Thakurgaon") returned a systematic system refusal: *"I don't have enough information in my database to answer that."*
* **The Cause:** While the underlying embedding models successfully performed cross-lingual semantic matching (locating the Bengali vector chunks for `ঠাকুরগাঁও`), the safety guardrails in the prompt were too strict. The prompt explicitly instructed the LLM to rely *only* on facts in the context. Because the LLM saw English letters in the query and Bengali script in the database context, it refused to assume they were identical to avoid hallucination rules.
* **The Fix:** Restructured the prompt engineering matrix to grant the LLM explicit linguistic translation permissions. The updated system prompt instructs the model to actively map English phonetic terms to their native Bengali counterparts in the text block before executing semantic parsing.

### Pitfall 4: The Render SQLite Version Crash (`sqlite3 >= 3.35.0`)

* **The Issue:** Upon initial deployment to Render, the build completed smoothly, but the service remained stuck on an infinite "Application Loading" screen. The underlying container logs exposed a fatal startup crash: `RuntimeError: Your system has an unsupported version of sqlite3. Chroma requires sqlite3 >= 3.35.0`.
* **The Cause:** Render's default native base Linux environment utilizes older system-level libraries that fall behind the modern SQLite specifications enforced by ChromaDB's underlying architecture.
* **The Fix:** Added `pysqlite3-binary` to the environment's `requirements.txt` file and injected a runtime system override at the absolute entry point of `main.py` before loading ChromaDB:
```python
import sys
try:
    import pysqlite3
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

```



### Pitfall 5: The Localhost Isolation Loop (`No open ports detected on 0.0.0.0`)

* **The Issue:** Even with the SQLite patch operational, Render's health check scanner threw repetitive timeouts: `Port scan timeout reached, no open ports detected on 0.0.0.0. Detected open ports on localhost`.
* **The Cause:** By default, Uvicorn initializes and binds explicitly to the local loopback interface (`127.0.0.1`). Inside a cloud network or Docker container architecture, this prevents Render's internal reverse proxy from routing public web traffic to the application.
* **The Fix:** Configured the platform start parameters to force Uvicorn to bind to all available network interfaces (`0.0.0.0`) using the designated dynamic runtime port environment variable:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT

```



---

## 3. Directory Layout

```text
.
├── DB/
│   └── upazila_text.db          # Sanitized, clean text-dense SQLite source
├── chroma_data/                 # Local persistent vector database storage
├── main.py                      # Production FastAPI production API script
├── vectorize_rag.py             # Sliding-window ingestion & embedding script
├── requirements.txt             # Strict version lock for dependencies
└── README.md                    # System documentation

```

---

## 4. Production API Specification

### Endpoint: `POST /api/query`

The primary endpoint to pass user text inputs directly to the extraction matrix.

#### Request Payload Structure

```json
{
  "query": "Which upazilas have notable rivers in their geographic info?",
  "top_k": 3
}

```

#### Response Structure

```json
{
  "answer": "Based on the provided geographical data, Debiganj Upazila features an extensive network of rivers running through it, including the Karatoya, Pathraj, Chatnai, Buri Teesta, Kalidaha, Banga, Kharkharia, and Kurum...",
  "sources": [
    {
      "wp_id": 751,
      "title": "পঞ্চগড় দেবীগঞ্জ",
      "snippet": "দেবীগঞ্জ উপজেলার বুক চিরে জালের মতো ছড়িয়ে আছে করতোয়া, পাথরাজ, ছাতনাই, বুড়ি তিস্তা..."
    }
  ]
}

```

---

## 5. System State & Verification Metrics

* **Total Clean Base Records Ingested:** 40 high-density records.


* **Sliding Window Chunk Profile:** 1,000 character maximum limit with a rolling 200 character safety overlap to maintain semantic continuity across sentences.
* **Average Production Round-Trip Latency:** ~4.0 seconds total response time (covers vector generation, semantic lookups, cloud API latency, and complete natural language generation synthesis).
* **System Health Status:** Online, fully verified, and actively accepting secure cross-origin requests (CORS).