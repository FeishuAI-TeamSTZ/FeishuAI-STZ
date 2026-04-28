"""Baseline RAG Embedding模块 - sentence-transformers本地模型"""
from typing import Optional, List, Union

from sentence_transformers import SentenceTransformer

from .config import config


class EmbeddingModel:
    """sentence-transformers 本地Embedding模型"""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(
        self,
        model_name: Optional[str] = None,
        cache_dir: Optional[str] = "./baseline/models",
        device: Optional[str] = None,
    ):
        self.model_name = model_name or self.DEFAULT_MODEL
        self.cache_dir = cache_dir
        self.model = SentenceTransformer(
            self.model_name,
            cache_folder=cache_dir,
            device=device,
        )
        self.dimension = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """将文本转换为向量"""
        if isinstance(texts, str):
            texts = [texts]

        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()

    def encode_single(self, text: str) -> List[float]:
        """将单个文本转换为向量"""
        return self.encode(texts=[text])[0]

    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.dimension

    def close(self) -> None:
        """清理模型（sentence-transformers不需要显式close）"""
        pass


embedding_model = EmbeddingModel()