# Tutor RAG with Neon pgvector

The Django tutor keeps document retrieval separate from document ingestion. Its
`RAGEngine` singleton is shared by the `kb_search` and `search_document` tools
within each Django worker. Search combines pgvector cosine similarity with
BM25 lexical ranks using reciprocal-rank fusion. Search never indexes the
platform knowledge base. Bundled platform Markdown/text files are checked and
indexed when a web worker starts; new or changed user uploads should be indexed
as part of their upload flow.

## Indexing

Apply the tutor migration first so Django enables the `vector` extension and
creates the document/chunk tables:

```powershell
cd backend
python manage.py migrate
```

Index a directory of PDFs, PowerPoint `.pptx`, Markdown, and text files
(directories are scanned recursively):

```powershell
python manage.py index_rag_documents .\rag_sources
```

Index active public Materials records as well:

```powershell
python manage.py index_rag_documents --materials
```

Both sources can be indexed in one run:

```powershell
python manage.py index_rag_documents .\rag_sources --materials
```

The command extracts PDF pages, PowerPoint slides, or UTF-8 text, splits text into
800-character chunks with 120-character overlap, embeds them with
`text-embedding-3-small`, and stores source/page metadata with each vector.
Rerunning skips unchanged content and unchanged indexing configuration. Changed
files replace their prior chunks. Use `--force` to rebuild unchanged files.

The command should only index a corpus intended to be available to all tutor
users. The current pgvector tool searches that shared corpus and does not apply
per-user document permissions.

## Storage and retrieval

- `TutorDocument` tracks each indexed source, content checksum, and indexing
  version.
- `TutorDocumentChunk` stores text, page/slide number, metadata, and a
  1536-dimensional embedding.
- An HNSW cosine index supports nearest-neighbor search.
- The tutor tool retrieves the top passages and returns source, page, and
  similarity information to the agent. Exact duplicate passages are removed
  from indexing and retrieval output.

The older FastAPI chatbot path still has its own session-scoped Upstash indexing
flow until that caller is migrated separately.
