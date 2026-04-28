# Baseline RAG

传统向量检索系统，作为主架构的对照组。

## 文件说明

- `config.py` - 配置项
- `embedding.py` - 向量化，用 sentence-transformers/all-MiniLM-L6-v2
- `chunker.py` - 文本分块
- `in_memory_store.py` - 内存存储，无需数据库
- `retriever.py` - 检索逻辑
- `baseline_rag.py` - 主入口

## 运行

```bash
source .venv/bin/activate
python test_rag.py
```

## 数据流

```
add_text() → chunker → embedding → in_memory_store
query() → embedding → in_memory_store.search() → 返回结果
```

## 依赖

```
sentence-transformers
numpy
httpx
sqlalchemy
pydantic
```

## 模型

用 sentence-transformers 的 all-MiniLM-L6-v2，下载后缓存在 `baseline/models/`，已加入 .gitignore。