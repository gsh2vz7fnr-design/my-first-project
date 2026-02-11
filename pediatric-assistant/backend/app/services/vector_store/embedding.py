"""
Embedding 服务模块 - 提供文本向量化能力

支持两种模式：
- SiliconFlowEmbedding: 远程 API 调用（主路径）
- LocalEmbedding: 本地 sentence-transformers（降级备选）
"""
import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

import httpx
from loguru import logger
from pydantic import BaseModel

from app.config import settings


class EmbeddingResult(BaseModel):
    """Embedding 结果模型"""
    embedding: List[float]
    model: str
    tokens_used: int = 0


class EmbeddingService(ABC):
    """
    Embedding 服务抽象基类

    定义了所有 Embedding 服务必须实现的接口。
    """

    @abstractmethod
    async def embed(self, text: str) -> Optional[List[float]]:
        """
        将单个文本转换为向量

        Args:
            text: 待转换的文本

        Returns:
            Optional[List[float]]: 向量表示，失败返回 None
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量将文本转换为向量

        Args:
            texts: 待转换的文本列表

        Returns:
            List[Optional[List[float]]]: 向量列表，失败的项为 None
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回当前使用的模型名称"""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """检查服务是否可用"""
        pass


class SiliconFlowEmbedding(EmbeddingService):
    """
    SiliconFlow Embedding 服务实现

    使用硅基流动 API 进行文本向量化，支持 BGE-M3 等中文模型。

    Features:
        - 远程 API 调用
        - 本地 LRU 缓存
        - 自动重试机制
        - 失败冷却机制
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        cache_size: int = 1000,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> None:
        """
        初始化 SiliconFlow Embedding 服务

        Args:
            api_key: API 密钥，默认使用配置
            base_url: API 基础 URL，默认使用配置
            model: 模型名称，默认使用配置
            cache_size: 缓存大小
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self._api_key = api_key or settings.SILICONFLOW_API_KEY
        self._base_url = base_url or settings.SILICONFLOW_BASE_URL
        self._model = model or settings.SILICONFLOW_EMBEDDING_MODEL
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        # 缓存相关
        self._cache: Dict[str, List[float]] = {}
        self._cache_size = cache_size
        self._cache_order: List[str] = []  # LRU 顺序

        # 可用性控制
        self._available = bool(self._api_key)
        self._cooldown_until: float = 0.0
        self._last_error: Optional[str] = None

        # HTTP 客户端（延迟创建）
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def model_name(self) -> str:
        """返回模型名称"""
        return self._model

    @property
    def is_available(self) -> bool:
        """
        检查服务是否可用

        Returns:
            bool: 可用返回 True
        """
        if not self._api_key:
            return False
        return time.time() >= self._cooldown_until

    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{self._model}:{text}".encode()).hexdigest()

    def _get_from_cache(self, text: str) -> Optional[List[float]]:
        """从缓存获取"""
        key = self._get_cache_key(text)
        if key in self._cache:
            # 更新 LRU 顺序
            self._cache_order.remove(key)
            self._cache_order.append(key)
            return self._cache[key]
        return None

    def _add_to_cache(self, text: str, embedding: List[float]) -> None:
        """添加到缓存"""
        key = self._get_cache_key(text)

        # 如果已存在，更新
        if key in self._cache:
            self._cache[key] = embedding
            self._cache_order.remove(key)
            self._cache_order.append(key)
            return

        # 检查缓存大小，淘汰最旧的
        while len(self._cache) >= self._cache_size:
            oldest_key = self._cache_order.pop(0)
            del self._cache[oldest_key]

        self._cache[key] = embedding
        self._cache_order.append(key)

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client

    async def embed(self, text: str) -> Optional[List[float]]:
        """
        将单个文本转换为向量

        Args:
            text: 待转换的文本

        Returns:
            Optional[List[float]]: 向量表示，失败返回 None
        """
        # 检查缓存
        cached = self._get_from_cache(text)
        if cached is not None:
            return cached

        # 调用 API
        results = await self.embed_batch([text])
        return results[0] if results else None

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量将文本转换为向量

        Args:
            texts: 待转换的文本列表

        Returns:
            List[Optional[List[float]]]: 向量列表
        """
        if not texts:
            return []

        # 检查可用性
        if not self.is_available:
            logger.warning(f"SiliconFlow Embedding 不可用: {self._last_error}")
            return [None] * len(texts)

        # 分离已缓存和未缓存的文本
        results: List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        for i, text in enumerate(texts):
            cached = self._get_from_cache(text)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        # 如果全部命中缓存，直接返回
        if not uncached_texts:
            return results

        # 调用 API 获取未缓存的向量
        embeddings = await self._call_api(uncached_texts)

        # 填充结果并更新缓存
        for i, embedding in enumerate(embeddings):
            original_index = uncached_indices[i]
            results[original_index] = embedding
            if embedding is not None:
                self._add_to_cache(uncached_texts[i], embedding)

        return results

    async def _call_api(
        self,
        texts: List[str],
        retry_count: int = 0
    ) -> List[Optional[List[float]]]:
        """
        调用 SiliconFlow API

        Args:
            texts: 文本列表
            retry_count: 当前重试次数

        Returns:
            List[Optional[List[float]]]: 向量列表
        """
        try:
            client = await self._get_client()

            response = await client.post(
                f"{self._base_url}/embeddings",
                json={
                    "model": self._model,
                    "input": texts,
                    "encoding_format": "float"
                }
            )

            if response.status_code == 200:
                data = response.json()
                # 按 index 排序
                embeddings_data = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                return [item.get("embedding") for item in embeddings_data]

            elif response.status_code == 429:
                # 速率限制，等待后重试
                if retry_count < self._max_retries:
                    wait_time = self._retry_delay * (2 ** retry_count)
                    logger.warning(f"SiliconFlow 速率限制，等待 {wait_time}s 后重试")
                    await asyncio.sleep(wait_time)
                    return await self._call_api(texts, retry_count + 1)
                else:
                    self._set_cooldown(60)
                    return [None] * len(texts)

            else:
                error_msg = f"API 错误: {response.status_code} - {response.text}"
                logger.error(error_msg)
                self._last_error = error_msg

                if retry_count < self._max_retries:
                    await asyncio.sleep(self._retry_delay)
                    return await self._call_api(texts, retry_count + 1)

                return [None] * len(texts)

        except httpx.TimeoutException:
            error_msg = "API 超时"
            logger.error(error_msg)
            self._last_error = error_msg

            if retry_count < self._max_retries:
                await asyncio.sleep(self._retry_delay)
                return await self._call_api(texts, retry_count + 1)

            self._set_cooldown(30)
            return [None] * len(texts)

        except Exception as e:
            error_msg = f"API 调用异常: {e}"
            logger.error(error_msg, exc_info=True)
            self._last_error = error_msg

            if retry_count < self._max_retries:
                await asyncio.sleep(self._retry_delay)
                return await self._call_api(texts, retry_count + 1)

            self._set_cooldown(60)
            return [None] * len(texts)

    def _set_cooldown(self, seconds: int) -> None:
        """设置冷却时间"""
        self._cooldown_until = time.time() + seconds
        logger.warning(f"SiliconFlow Embedding 进入冷却状态，{seconds}s 后恢复")

    async def close(self) -> None:
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class LocalEmbedding(EmbeddingService):
    """
    本地 Embedding 服务实现

    使用 sentence-transformers 进行本地文本向量化。
    作为远程 API 不可用时的降级方案。

    Features:
        - 无网络依赖
        - 延迟初始化（首次使用时加载模型）
        - 支持 GPU 加速（如果可用）
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        device: Optional[str] = None,
        cache_size: int = 1000
    ) -> None:
        """
        初始化本地 Embedding 服务

        Args:
            model_name: 模型名称
            device: 计算设备 ("cpu", "cuda", "mps")，None 自动选择
            cache_size: 缓存大小
        """
        self._model_name = model_name
        self._device = device
        self._cache_size = cache_size

        # 延迟加载
        self._model: Optional[Any] = None
        self._initialized = False

        # 缓存
        self._cache: Dict[str, List[float]] = {}
        self._cache_order: List[str] = []

    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        import hashlib
        return hashlib.md5(f"{self._model_name}:{text}".encode()).hexdigest()

    async def _ensure_initialized(self) -> bool:
        """确保模型已初始化"""
        if self._initialized:
            return self._model is not None

        try:
            # 在线程池中加载模型（避免阻塞）
            def _load_model():
                from sentence_transformers import SentenceTransformer

                device = self._device
                if device is None:
                    import torch
                    if torch.cuda.is_available():
                        device = "cuda"
                    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                        device = "mps"
                    else:
                        device = "cpu"

                model = SentenceTransformer(self._model_name, device=device)
                logger.info(f"本地 Embedding 模型加载完成: {self._model_name} (device={device})")
                return model

            self._model = await asyncio.get_event_loop().run_in_executor(None, _load_model)
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"本地 Embedding 模型加载失败: {e}", exc_info=True)
            self._initialized = True  # 标记为已尝试，避免重复加载
            return False

    @property
    def model_name(self) -> str:
        """返回模型名称"""
        return self._model_name

    @property
    def is_available(self) -> bool:
        """检查服务是否可用"""
        if not self._initialized:
            return True  # 尚未初始化，假设可用
        return self._model is not None

    async def embed(self, text: str) -> Optional[List[float]]:
        """
        将单个文本转换为向量

        Args:
            text: 待转换的文本

        Returns:
            Optional[List[float]]: 向量表示
        """
        # 检查缓存
        key = self._get_cache_key(text)
        if key in self._cache:
            return self._cache[key]

        results = await self.embed_batch([text])
        return results[0] if results else None

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量将文本转换为向量

        Args:
            texts: 待转换的文本列表

        Returns:
            List[Optional[List[float]]]: 向量列表
        """
        if not texts:
            return []

        if not await self._ensure_initialized():
            return [None] * len(texts)

        try:
            # 在线程池中执行编码
            def _encode():
                embeddings = self._model.encode(texts, normalize_embeddings=True)
                return [emb.tolist() for emb in embeddings]

            embeddings = await asyncio.get_event_loop().run_in_executor(None, _encode)

            # 更新缓存
            for text, embedding in zip(texts, embeddings):
                key = self._get_cache_key(text)
                if len(self._cache) >= self._cache_size and key not in self._cache:
                    # 淘汰最旧
                    oldest = self._cache_order.pop(0)
                    del self._cache[oldest]
                if key not in self._cache:
                    self._cache[key] = embedding
                    self._cache_order.append(key)

            return embeddings

        except Exception as e:
            logger.error(f"本地 Embedding 编码失败: {e}", exc_info=True)
            return [None] * len(texts)


class HybridEmbeddingService(EmbeddingService):
    """
    混合 Embedding 服务

    优先使用远程 API，失败时自动降级到本地模型。

    Example:
        >>> service = HybridEmbeddingService()
        >>> embedding = await service.embed("宝宝发烧怎么办")
    """

    def __init__(
        self,
        remote_service: Optional[SiliconFlowEmbedding] = None,
        local_service: Optional[LocalEmbedding] = None
    ) -> None:
        """
        初始化混合服务

        Args:
            remote_service: 远程服务实例
            local_service: 本地服务实例
        """
        self._remote = remote_service or SiliconFlowEmbedding()
        self._local = local_service or LocalEmbedding()
        self._use_remote = True

    @property
    def model_name(self) -> str:
        """返回当前使用的模型名称"""
        if self._use_remote and self._remote.is_available:
            return f"remote:{self._remote.model_name}"
        return f"local:{self._local.model_name}"

    @property
    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self._remote.is_available or self._local.is_available

    async def embed(self, text: str) -> Optional[List[float]]:
        """
        将单个文本转换为向量

        Args:
            text: 待转换的文本

        Returns:
            Optional[List[float]]: 向量表示
        """
        # 尝试远程服务
        if self._use_remote and self._remote.is_available:
            result = await self._remote.embed(text)
            if result is not None:
                return result
            else:
                logger.warning("远程 Embedding 失败，切换到本地模型")
                self._use_remote = False

        # 降级到本地
        return await self._local.embed(text)

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量将文本转换为向量

        Args:
            texts: 待转换的文本列表

        Returns:
            List[Optional[List[float]]]: 向量列表
        """
        # 尝试远程服务
        if self._use_remote and self._remote.is_available:
            results = await self._remote.embed_batch(texts)
            if all(r is not None for r in results):
                return results
            else:
                logger.warning("部分远程 Embedding 失败，切换到本地模型")
                self._use_remote = False

        # 降级到本地
        return await self._local.embed_batch(texts)

    def reset_remote(self) -> None:
        """重置远程服务状态（重新尝试使用远程服务）"""
        self._use_remote = True
        logger.info("已重置为优先使用远程 Embedding 服务")
