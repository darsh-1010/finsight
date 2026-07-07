# RAG Integration API Documentation

## Status
✅ **RAG is fully integrated and always enabled**

Every chat request automatically includes document context from Weaviate when available.

---

## Endpoints

### 1. Upload & Scrape PDF
**Store a document for RAG retrieval**

```bash
POST /api/v1/scraper/rag/store
Content-Type: application/json
```

**Request Body**:
```json
{
  "url": "financial-report-q4.pdf",
  "content": "Q4 2024 Financial Report: Revenue increased 25%...",
  "metadata": {
    "title": "Q4 2024 Financial Report",
    "type": "financial_report",
    "date": "2024-12-31"
  }
}
```

**Response**:
```json
{
  "chunks_stored": 5,
  "document_id": "abc123..."
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/scraper/rag/store \
  -H "Content-Type: application/json" \
  -d '{
    "url": "report.pdf",
    "content": "Annual revenue grew to $1.2B...",
    "metadata": {"title": "Financial Report"}
  }'
```

---

### 2. Chat with RAG
**Stream chat response with financial + document context**

```bash
POST /api/v1/chat/stream
Content-Type: application/json
```

**Request Body**:
```json
{
  "user_message": "What was the revenue in Q4?",
  "session_id": "user-123",
  "is_new": true
}
```

**Response** (Server-Sent Events):
```
data: {"type": "session", "session_id": "user-123"}

data: {"type": "content", "delta": "Based on the Q4 report..."}

data: {"type": "citations", "citations": [
  {
    "source": "document",
    "title": "Q4 2024 Financial Report",
    "url": "report.pdf",
    "score": 0.89,
    "data_type": "document"
  },
  {
    "source": "yfinance",
    "ticker": "AAPL",
    "data_type": "financial_data"
  }
]}

data: {"type": "metadata", "tokens_used": 450, "latency_ms": 1200}

data: [DONE]
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "Summarize the financial report",
    "session_id": "test-123",
    "is_new": true
  }'
```

---

### 3. Retrieve Context
**Test RAG retrieval directly**

```bash
POST /api/v1/scraper/rag/retrieve
Content-Type: application/json
```

**Request Body**:
```json
{
  "query": "What was the revenue?",
  "limit": 5
}
```

**Response**:
```json
{
  "results": [
    {
      "content": "Revenue increased 25% to $1.2 billion...",
      "metadata": {"title": "Q4 Report"},
      "score": 0.89,
      "source_url": "report.pdf"
    }
  ]
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/scraper/rag/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "revenue growth", "limit": 3}'
```

---

### 4. RAG Statistics
**Get vector database statistics**

```bash
GET /api/v1/scraper/rag/stats
```

**Response**:
```json
{
  "total_documents": 15,
  "total_chunks": 245,
  "collections": ["FinancialDocuments"]
}
```

**Example**:
```bash
curl http://localhost:8000/api/v1/scraper/rag/stats
```

---

### 5. Delete Document
**Remove document from vector database**

```bash
DELETE /api/v1/scraper/rag/document?url=report.pdf
```

**Response**:
```json
{
  "deleted": true,
  "chunks_deleted": 5
}
```

**Example**:
```bash
curl -X DELETE "http://localhost:8000/api/v1/scraper/rag/document?url=report.pdf"
```

---

## Complete Flow Example

### Step 1: Store Document
```bash
curl -X POST http://localhost:8000/api/v1/scraper/rag/store \
  -H "Content-Type: application/json" \
  -d '{
    "url": "earnings-report-q4-2024.pdf",
    "content": "Q4 2024 Earnings: Revenue $1.2B (up 25% YoY). Net income $450M. Acquired 3 subsidiaries.",
    "metadata": {
      "title": "Q4 2024 Earnings Report",
      "company": "ACME Corp",
      "date": "2024-12-31",
      "type": "earnings_report"
    }
  }'
```

### Step 2: Chat and Get Combined Context
```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "What were the Q4 earnings and how did revenue change?",
    "session_id": "demo-001",
    "is_new": true
  }'
```

**Response includes**:
- ✅ Financial data from yFinance (if ticker mentioned)
- ✅ Document context from Weaviate
- ✅ Combined citations from both sources

---

## Environment Variables

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Weaviate
WEAVIATE_URL=http://localhost:8080
WEAVIATE_GRPC_URL=localhost:50051
WEAVIATE_API_KEY=  # Optional

# Redis
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=3600

# RAG Configuration
TOP_K_RETRIEVAL=10
RERANK_TOP_K=5
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

---

## Quick Start

### 1. Start Services
```bash
docker-compose up -d
```

### 2. Store Sample Document
```bash
curl -X POST http://localhost:8000/api/v1/scraper/rag/store \
  -H "Content-Type: application/json" \
  -d '{
    "url": "sample-doc.txt",
    "content": "This is a sample financial document with revenue information.",
    "metadata": {"title": "Sample Doc"}
  }'
```

### 3. Test Chat
```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "What does the document say?",
    "session_id": "test-001",
    "is_new": true
  }'
```

---

## Citation Format

### Document Citations
```json
{
  "source": "document",
  "title": "Q4 Report",
  "url": "report.pdf",
  "score": 0.85,
  "data_type": "document"
}
```

### Financial Data Citations
```json
{
  "source": "yfinance",
  "ticker": "AAPL",
  "data_type": "financial_data",
  "fields": ["price", "volume"]
}
```

---

## Troubleshooting

### Issue: No document context retrieved
**Check**:
1. Document was stored: `curl http://localhost:8000/api/v1/scraper/rag/stats`
2. Weaviate is running: `docker-compose ps weaviate`
3. Embeddings API key: `echo $OPENAI_API_KEY`

### Issue: Poor retrieval quality
**Tune parameters** in `.env`:
```bash
TOP_K_RETRIEVAL=15  # Increase initial retrieval
RERANK_TOP_K=7      # Get more results after reranking
```

### Issue: Weaviate connection failed
**Restart services**:
```bash
docker-compose restart weaviate
```

---

## Testing

Run end-to-end test:
```bash
./tests/test_rag_e2e.sh
```

Expected output:
- ✅ Document stored
- ✅ Context retrieved
- ✅ Chat response includes document citations

---

## Production Checklist

- [ ] Environment variables configured
- [ ] Weaviate persistent storage configured
- [ ] API rate limiting enabled
- [ ] Monitoring for RAG service
- [ ] Document upload limits set
- [ ] Vector database backups configured
