# RAG Paper System

RAG Paper System 是一个端到端的论文检索与问答解决方案，包含：

- **后端（Python / Flask）**：负责论文抓取、PDF 解析、向量/稀疏索引构建以及混合检索 + 重排的问答接口。
- **前端（Vue 3 + Vite）**：提供简洁的管理控制台，可提交问题、触发论文抓取，并配置 API 访问参数。

该项目适用于希望在本地或自建环境中快速搭建论文型 RAG（Retrieval-Augmented Generation）系统的场景。

## 仓库结构

```
RAG-Paper-System/
├─ backend/
│  ├─ app/                 # Flask 应用、检索与爬取逻辑
│  ├─ data/                # PDF 与文本缓存目录（运行时生成）
│  ├─ index/               # FAISS、BM25 索引文件（运行时生成）
│  ├─ app.flask.py         # Flask 开发入口
│  ├─ paper_collector.py   # 论文抓取脚本入口（包装 app.crawler.collector ）
│  └─ requirements.txt     # Python 依赖
├─ frontend/               # Vue 3 控制台（Vite 工程）
└─ README.md
```

> **提示**：`backend/app/config.py` 中定义了所有路径和检索参数，可根据需要调整。

## 后端快速上手

1. **创建虚拟环境并安装依赖**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   > ⚠️ `torch` 建议按照 [PyTorch 官方指引](https://pytorch.org/get-started/locally/) 安装与硬件匹配的版本；如需 CUDA 支持，请使用对应的 GPU whl 包。

2. **准备 PDF 数据**
   - 将已有 PDF 放入 `backend/data/pdf/`；或
   - 使用项目自带的抓取脚本（见下文 `论文抓取与增量更新`）。

3. **构建索引**
   ```bash
   cd backend
   python -m app.ingest
   ```
   该步骤会读取 `data/pdf/` 下的 PDF，解析文本并生成：
   - `index/faiss/dense.faiss` 及 `chunks.jsonl`、`meta.jsonl`
   - `index/bm25/bm25.jsonl`（稀疏检索 token）

4. **启动 Flask API**
   ```bash
   # 开发调试
   cd backend
   python app.flask.py

   # 生产部署示例（需提前创建索引）
   gunicorn -w 2 -b 0.0.0.0:8000 app.flask:app
   ```

5. **API 说明**（默认 base URL：`http://localhost:8000`）
   - `POST /ask`：混合检索 + LLM（可选）问答
     ```json
     {
       "q": "Retrieval-Augmented Generation 的关键步骤是什么？",
       "k": 8
     }
     ```
   - `POST /crawl`：触发论文抓取（支持多关键词，用分号分隔）
     ```json
     {
       "query": "transformer;retrieval augmented generation",
       "providers": "arxiv,openalex",
       "max_per_source": 50,
       "year_min": 2019,
       "run_ingest": true
     }
     ```
   `run_ingest=true` 时会在抓取完成后自动构建索引，并通过 `reload_retriever()` 热加载至内存。

## 论文抓取与增量更新

`backend/app/crawler/collector.py` 集成了 arXiv、OpenAlex、Semantic Scholar 三个开放源，可按照关键词批量下载开源 PDF，同时维护 `data/metadata/papers.jsonl`。常用命令：

```bash
cd backend
python paper_collector.py --query "transformer" --max-per-source 100
python paper_collector.py --query "RAG;retrieval augmented generation" --year-min 2019 --providers arxiv,openalex
python paper_collector.py --query "multimodal LLM" --out data/pdf --run-ingest
```

脚本会自动去重（基于标题和内容哈希）、缓存已解析文本，并在需要时触发向量化与索引构建。

## LLM 集成（可选）

当未配置大模型时，`/ask` 会返回基于检索片段的提取式答案。若需要生成式回答，可提供任意 OpenAI 兼容接口：

```bash
export OPENAI_API_BASE="https://your-endpoint/v1"
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"  # 或本地 vLLM 模型名称
```

设置环境变量后，后端会自动调用对应模型生成最终答案，并附带来源引用信息。

## 前端控制台

前端位于 `frontend/`，基于 Vue 3 + Vite，实现了以下功能：
- 配置后端 Base URL 与鉴权信息（保存在 Local Storage）；
- 提交 `/ask` 请求并渲染 Markdown 答案与引用；
- 提交 `/crawl` 任务并展示执行摘要。

本地开发步骤：

```bash
cd frontend
npm install
npm run dev -- --host
```

在浏览器打开终端输出的地址（默认 `http://localhost:5173`），按提示填写 API 配置即可开始使用。

## 常见问题

- **首次启动报错 “FAISS index not found”**：需要先运行 `python -m app.ingest` 或在抓取时加上 `--run-ingest`。
- **无 GPU 环境**：系统会自动回退到 CPU 推理，但嵌入与重排会更慢。
- **PDF 解析为乱码**：确认 PDF 为文本层文件；扫描件需先 OCR 处理。
- **爬虫请求被限制**：可在 `collector.py` 内调整 `ARXIV_SLEEP` 等节流参数。

欢迎根据自己的数据源与部署环境定制检索策略、模型选择或前端交互。
