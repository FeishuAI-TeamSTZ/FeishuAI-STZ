# Baseline RAG Schema

本文件定义 Baseline RAG 系统的数据结构。

---

## 1. Chunk（文本块）

原始文本切分后的基本单元。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chunk_id | string | 是 | UUID，唯一标识 |
| content | string | 是 | 文本内容 |
| source_type | string | 是 | 来源类型：message / doc / calendar / task |
| source_id | string | 否 | 来源 ID，如消息 ID、文档 token |
| metadata | object | 否 | 附加信息，如发送者、时间 |
| created_at | datetime | 是 | 创建时间 |

示例：

```
chunk_id: "550e8400-e29b-41d4-a716-446655440000"
content: "项目A上线日期是5月15号"
source_type: "message"
source_id: "om_xxx"
metadata: {"chat_id": "oc_xxx", "sender": "ou_xxx"}
created_at: "2024-04-29T10:00:00"
```

---

## 2. TextChunk（文本切片）

包含向量 embedding 的完整切片，用于向量检索。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chunk_id | string | 是 | 继承自 Chunk |
| content | string | 是 | 继承自 Chunk |
| source_type | string | 是 | 继承自 Chunk |
| source_id | string | 否 | 继承自 Chunk |
| metadata | object | 否 | 继承自 Chunk |
| created_at | datetime | 是 | 继承自 Chunk |
| embedding | float[] | 是 | 384 维向量（all-MiniLM-L6-v2） |

示例：

```
chunk_id: "550e8400-e29b-41d4-a716-446655440000"
content: "项目A上线日期是5月15号"
source_type: "message"
embedding: [0.123, -0.456, 0.789, ...]  # 384 维
```

---

## 3. SearchResult（检索结果）

向量检索返回的结果。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chunk_id | string | 是 | 切片 ID |
| content | string | 是 | 切片内容 |
| source_type | string | 是 | 来源类型 |
| source_id | string | 否 | 来源 ID |
| metadata | object | 否 | 附加信息 |
| created_at | datetime | 是 | 创建时间 |
| similarity | float | 是 | 余弦相似度 [0-1]，越高越相关 |

示例：

```
{
  "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
  "content": "项目A上线日期是5月15号",
  "source_type": "message",
  "similarity": 0.723
}
```

---

## 4. Config（配置项）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| EMBEDDING_MODEL | string | "all-MiniLM-L6-v2" |  embedding 模型 |
| EMBEDDING_DIM | int | 384 | 向量维度 |
| EMBEDDING_CACHE_DIR | string | "./baseline/models" | 模型缓存路径 |
| CHUNK_SIZE | int | 1000 | 分块大小（字符数） |
| CHUNK_OVERLAP | int | 200 | 分块重叠（字符数） |
| SIMILARITY_THRESHOLD | float | 0.6 | 检索相似度阈值 |

---

## 5. 数据流

```
输入文本
    ↓
Chunker.chunk_text()  → [Chunk]
    ↓
Embedding.encode() → [embedding]
    ↓
VectorStore.insert() → TextChunk (持久化)
    ↓
检索时：
    ↓
Embedding.encode_single(query) → query_embedding
    ↓
VectorStore.search(query_embedding, top_k) → [SearchResult]
```

---

## 6. 存储选型

| 存储类型 | 使用场景 | 依赖 |
|----------|----------|------|
| InMemoryVectorStore | 开发调试、无 PostgreSQL | 无 |
| VectorStore | 生产环境、需要持久化 | PostgreSQL + pgvector |

切换方式：修改 baseline_rag.py 中的 use_memory 参数。