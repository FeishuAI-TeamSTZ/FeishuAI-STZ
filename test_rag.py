#!/usr/bin/env python3
"""快速测试RAG检索"""
from baseline import BaselineRAG
import numpy as np

rag = BaselineRAG()

texts = [
    '周报每周五发给李四',
    '项目A上线日期是5月15号',
    '周会改到周三下午3点',
]

for t in texts:
    rag.add_text(t)

store = rag.vector_store
print(f'Store chunks: {len(store.chunks)}')
print(f'Store dim: {store.embedding_dim}')

for i, c in enumerate(store.chunks):
    print(f'Chunk {i}: dim={len(c.embedding) if c.embedding else None}')

query = '周报发给谁？'
query_emb = rag.embedding.encode_single(query)
print(f'Query dim: {len(query_emb)}')

print('\nManual similarity:')
for i, c in enumerate(store.chunks):
    v1 = np.array(c.embedding)
    vq = np.array(query_emb)
    sim = np.dot(v1, vq) / (np.linalg.norm(v1) * np.linalg.norm(vq))
    print(f'  "{c.content}": {sim:.4f}')

print('\nStore search:')
results = rag.retriever.search(query, 5)
for r in results:
    print(f'  "{r["content"]}": {r["similarity"]:.4f}')