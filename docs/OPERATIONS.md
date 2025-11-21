# 运行与维护指南

本文档提供日常操作步骤，包括数据目录说明、爬虫与索引流水线以及常用维护命令。

## 数据目录与配置
后端主要路径在 `backend/app/config.py` 中定义，可根据需要修改：
- 原始数据：`data/raw_pdfs/`（PDF）、`data/metadata/papers.jsonl`（元数据）。【F:backend/app/config.py†L7-L16】
- 解析与切分：`data/parsed/` 下的文本与元信息，知识图谱存放在 `data/graph/`。【F:backend/app/config.py†L18-L25】
- 检索索引：`index/faiss/` 与 `index/bm25/`，包括向量索引、chunk JSONL 与稀疏 token。默认检索 TopK、重排与融合权重也在配置中可调。【F:backend/app/config.py†L27-L41】

修改路径后需确保目录存在并与前端配置一致。

## 论文抓取与增量更新
1. **单次抓取命令**：
   ```bash
   cd backend
   python paper_collector.py --query "your keywords" --max-per-source 50 --year-min 2019 --run-ingest
   ```
2. **接口触发**：前端或脚本可调用 `/crawl`，默认启用 `run_ingest`，完成后会热加载最新索引。路由会在 ingest 运行完成后调用 `reload_retriever()` 以刷新内存中的检索器实例。【F:backend/app/routes/crawl.py†L13-L47】
3. **流水线输出**：爬虫总结包含候选数量、成功下载数、元数据写入标记、知识图谱摘要、是否运行 ingest 及其返回信息，便于监控批处理效果。【F:backend/app/crawler/collector.py†L515-L577】

## 索引与检索维护
- **手动构建索引**：
  ```bash
  cd backend
  python -m app.ingest
  ```
  该命令会遍历 `data/raw_pdfs/`，生成 FAISS 和 BM25 索引，并将 chunk/metadata JSONL 写入 `index/faiss/`。

- **热加载**：若在运行中的服务手动重建索引，可在 Python shell 中调用：
  ```python
  from app.services import reload_retriever, reload_graph_index
  reload_retriever()
  reload_graph_index()
  ```
  这样无需重启即可让新索引与知识图谱生效。【F:backend/app/services/__init__.py†L1-L19】

## 故障排查
- **缺少索引文件**：确认已运行 ingest；若路径自定义，检查 `FAISS_INDEX_PATH`、`BM25_SERIALIZED` 指向的位置是否存在。【F:backend/app/config.py†L27-L35】
- **抓取被限流或下载失败**：可在 `app/crawler/collector.py` 中调整节流参数或超时时间（如 `REQ_TIMEOUT`），或减少 `max_per_source` 降低请求频率。【F:backend/app/crawler/collector.py†L33-L80】
- **模型调用异常**：检查环境变量 `OPENAI_API_BASE`、`OPENAI_API_KEY`、`OPENAI_MODEL` 是否正确；未配置时系统会默认回退到本地占位模型名并返回提取式答案。【F:backend/app/config.py†L43-L45】【F:backend/app/routes/ask.py†L10-L37】
