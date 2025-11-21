# API 文档

后端默认监听 `http://localhost:8000`，支持 CORS。当前暴露两个主要接口：问答 `/ask` 与爬虫 `/crawl`。

## 通用说明
- 请求体统一使用 `application/json`。
- 未提供可选参数时使用后端默认值（如检索 TopK、爬虫数据源）。
- 接口返回 `application/json`，错误时包含 `error` 或 `message` 字段与相应的 HTTP 状态码。

## 问答接口 `/ask`
- **方法**：`GET` 或 `POST`
- **功能**：根据问题自动在知识图谱、RAG 或混合策略之间路由，返回答案及引用。
- **参数**：
  - `q`（字符串，必填）：问题内容，`GET` 可用 query string，`POST` 可放在 JSON 中。
  - `k`（整数，可选）：检索返回的片段数量，默认值由后端 `DEFAULT_TOPK` 提供（当前为 10）。【F:backend/app/routes/ask.py†L10-L49】【F:backend/app/config.py†L36-L41】

- **响应字段**：
  - `answer`：最终答案文本，可能包含 Markdown 与参考片段标题。
  - `references`：命中的文档元数据数组，对应检索到的片段。
  - `graph`：知识图谱事实列表（当命中时）。
  - `strategy`：决策使用的策略，`kg`、`rag` 或 `hybrid`。
  - `reason`：策略判定原因描述。
  - `cues`：决策时使用的关键词/线索列表。
  【F:backend/app/routes/ask.py†L27-L70】

- **示例请求**：
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"q": "What is Retrieval-Augmented Generation?", "k": 6}'
```

- **示例成功响应（部分字段）**：
```json
{
  "answer": "RAG 将检索与生成结合...",
  "references": [
    {"title": "RAG Paper", "source": "arxiv", "chunk_id": 12}
  ],
  "graph": [
    {"subject": "RAG", "predicate": "related_to", "object": "retrieval"}
  ],
  "strategy": "hybrid",
  "reason": "question mentions retrieval and relation keywords",
  "cues": ["retrieval", "relation"]
}
```

- **错误响应示例**：
  - 缺少问题：`400 {"error": "q (question) is required"}`。

## 爬虫接口 `/crawl`
- **方法**：`POST`
- **功能**：按关键词触发论文抓取，支持多数据源与可选的索引构建。
- **请求字段**（JSON）：
  - `query`（字符串，必填）：关键词，多个关键词使用分号分隔。
  - `providers`（字符串，可选）：数据源列表，默认 `arxiv,openalex,semanticscholar`。
  - `max_per_source`（整数，可选）：每个数据源的最大抓取数量，默认 50。
  - `year_min` / `year_max`（整数，可选）：限定年份区间。
  - `out`（字符串，可选）：PDF 输出目录，默认 `backend/data/raw_pdfs/`。
  - `meta`（字符串，可选）：元数据 JSONL 路径，默认 `backend/data/metadata/papers.jsonl`。
  - `run_ingest`（布尔，可选）：抓取后是否立即解析与构建索引，接口默认 `true`。
  【F:backend/app/routes/crawl.py†L13-L46】【F:backend/app/crawler/collector.py†L33-L80】【F:backend/app/config.py†L7-L30】【F:backend/app/crawler/collector.py†L515-L577】

- **响应字段**：
  - `status`：`ok` 或 `error`。
  - `summary`：当成功时包含以下字段：
    - `queries`：实际运行的关键词列表。
    - `providers`：启用的数据源数组。
    - `candidates`：抓取到的候选论文数量。
    - `downloaded`：成功下载的 PDF 数量。
    - `metadata_written`：是否追加了元数据文件。
    - `knowledge_graph`：知识图谱构建摘要。
    - `ingest_ran`：是否执行了解析与索引构建。
    - `ingest_summary`：索引构建返回的细节（若启用）。【F:backend/app/crawler/collector.py†L515-L577】
  - 出错时返回 `{ "status": "error", "message": "..." }` 并附带 500 状态码。 【F:backend/app/routes/crawl.py†L43-L47】

- **示例请求**：
```bash
curl -X POST http://localhost:8000/crawl \
  -H "Content-Type: application/json" \
  -d '{"query": "retrieval augmented generation;transformer", "max_per_source": 30, "year_min": 2019, "run_ingest": true}'
```

- **示例响应（摘要）**：
```json
{
  "status": "ok",
  "summary": {
    "queries": ["retrieval augmented generation", "transformer"],
    "providers": ["arxiv", "openalex", "semanticscholar"],
    "candidates": 120,
    "downloaded": 98,
    "metadata_written": true,
    "knowledge_graph": {"nodes": 300, "edges": 420},
    "ingest_ran": true,
    "ingest_summary": {"chunks": 5500, "faiss_index": "index/faiss/dense.faiss"}
  }
}
```
