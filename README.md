# RAG Paper System

RAG Paper System 是一个端到端的论文检索与问答解决方案，整合了论文抓取、索引构建、知识图谱与混合检索能力，前后端开箱即用。

## 功能特性
- **论文抓取与增量更新**：支持 arXiv、OpenAlex、Semantic Scholar，可按关键词批量下载 PDF 并去重。
- **自动解析与索引**：内置文本切分、向量化与 BM25 稀疏索引，支持混合检索与重排。
- **问答决策路由**：根据问题在知识图谱、RAG 或混合策略之间自动切换。
- **可选 LLM 生成式回答**：兼容 OpenAI/vLLM 接口，未配置时返回提取式答案。
- **前端控制台**：基于 Vue 3 + Vite，可提交问答与抓取任务、配置后端地址与鉴权信息。

## 目录结构
```
RAG-Paper-System/
├─ backend/                  # Flask 后端与爬虫、索引、检索逻辑
│  ├─ app/                   # 模块化代码目录
│  ├─ data/                  # 原始 PDF、解析文本、图谱数据（运行时生成）
│  ├─ index/                 # FAISS/BM25 索引文件（运行时生成）
│  ├─ app.flask.py           # Flask 调试入口
│  ├─ paper_collector.py     # 爬虫脚本入口（包装 app.crawler.collector ）
│  └─ requirements.txt       # Python 依赖
├─ frontend/                 # Vue 3 + Vite 前端控制台
└─ README.md
```

## 环境要求
- Python 3.10+
- Node.js 18+
- 可选：GPU/CUDA（用于加速 embedding/重排）、已部署的 OpenAI 兼容大模型接口

## 快速开始
### 后端
1. **安装依赖**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **准备数据与构建索引**
   - 将 PDF 放入 `backend/data/raw_pdfs/`，或运行爬虫：
     ```bash
     python paper_collector.py --query "transformer" --max-per-source 50 --run-ingest
     ```
   - 手动构建索引可运行：
     ```bash
     python -m app.ingest
     ```

3. **启动 Flask API**
   ```bash
   # 开发模式
   python app.flask.py

   # 生产示例（需提前构建索引）
   gunicorn -w 2 -b 0.0.0.0:8000 app.flask:app
   ```

4. **配置可选的大模型**（未设置时返回提取式回答）
   ```bash
   export OPENAI_API_BASE="https://your-endpoint/v1"
   export OPENAI_API_KEY="sk-..."
   export OPENAI_MODEL="gpt-4o-mini"  # 或本地 vLLM 模型名称
   ```

### 前端
```bash
cd frontend
npm install
npm run dev -- --host
```
在浏览器打开终端输出的地址（默认 `http://localhost:5173`），填写后端 Base URL 与鉴权信息即可使用。

## 数据流与索引
- 原始 PDF 与元数据保存在 `backend/data/raw_pdfs/`、`backend/data/metadata/`。
- 文本解析与切分后的内容位于 `backend/data/parsed/`，知识图谱存放在 `backend/data/graph/`。
- 检索索引位于 `backend/index/`：`faiss/dense.faiss`、`faiss/chunks.jsonl`、`faiss/meta.jsonl` 与 `bm25/bm25.jsonl`。
- 详细的爬取、解析、索引与热加载流程见 [`docs/OPERATIONS.md`](docs/OPERATIONS.md)。

## API 文档
后端暴露 `/ask` 与 `/crawl` 两个主要接口，完整的字段说明、示例请求与响应请见 [`docs/API.md`](docs/API.md)。

## 常见问题
- **FAISS index not found**：运行 `python -m app.ingest` 或在爬虫命令中加入 `--run-ingest`。
- **无 GPU 环境**：系统会自动回退到 CPU，嵌入与重排速度会变慢。
- **PDF 解析乱码**：确认 PDF 为文本层文件；扫描件需先 OCR。
- **爬虫被限流**：可在 `app/crawler/collector.py` 中调整节流参数（如 `ARXIV_SLEEP`）。

欢迎根据数据源与部署环境定制检索策略、模型或前端交互。
