#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Modules - API 客户端 (v5.0 OpenAI 兼容接口)

支持三种 Rerank 模式：
1. openai: OpenAI 兼容的 /v1/rerank 接口 (Jina/Cohere)
2. modal: Modal 自定义接口格式
3. embedding: 使用 Embedding API 计算余弦相似度作为 rerank（无需额外 rerank 服务）

配置示例 (config.py):
    embed_api_type = "openai"
    embed_base_url = "https://api-inference.modelscope.cn/v1"
    embed_model = "Qwen/Qwen3-Embedding-8B"
    embed_api_key = "sk-xxx"

    rerank_api_type = "embedding"  # 使用 embedding 相似度替代专用 rerank API
"""

import asyncio
import aiohttp
import math
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .config import get_config


@dataclass
class APIStats:
    """API 调用统计"""
    total_calls: int = 0
    total_time: float = 0.0
    errors: int = 0


class EmbeddingAPIClient:
    """
    通用 Embedding API 客户端

    支持 OpenAI 兼容接口 (/v1/embeddings) 和 Modal 自定义接口
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self.sem = asyncio.Semaphore(self.config.embed_concurrency)
        self.stats = APIStats()
        self._warmed_up = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=200, limit_per_host=100)
            self._session = aiohttp.ClientSession(connector=connector, trust_env=False)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {"Content-Type": "application/json"}
        if self.config.embed_api_key:
            headers["Authorization"] = f"Bearer {self.config.embed_api_key}"
        return headers

    def _build_url(self) -> str:
        """构建请求 URL"""
        base_url = self.config.embed_base_url.rstrip("/")
        if self.config.embed_api_type == "openai":
            # OpenAI 兼容: /v1/embeddings
            if not base_url.endswith("/embeddings"):
                if base_url.endswith("/v1"):
                    return f"{base_url}/embeddings"
                return f"{base_url}/v1/embeddings"
            return base_url
        else:
            # Modal 自定义接口: 直接使用配置的 URL
            return base_url

    def _build_payload(self, texts: List[str]) -> Dict[str, Any]:
        """构建请求体"""
        if self.config.embed_api_type == "openai":
            return {
                "input": texts,
                "model": self.config.embed_model,
                "encoding_format": "float"
            }
        else:
            # Modal 格式
            return {
                "input": texts,
                "model": self.config.embed_model
            }

    def _parse_response(self, data: Dict[str, Any]) -> Optional[List[List[float]]]:
        """解析响应"""
        if self.config.embed_api_type == "openai":
            # OpenAI 格式: {"data": [{"embedding": [...], "index": 0}, ...]}
            if "data" in data:
                # 按 index 排序，确保顺序正确
                sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in sorted_data]
            return None
        else:
            # Modal 格式: {"data": [{"embedding": [...]}, ...]}
            if "data" in data:
                return [item["embedding"] for item in data["data"]]
            return None

    async def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """调用 Embedding 服务（带重试机制）"""
        if not texts:
            return []

        timeout = self.config.cold_start_timeout if not self._warmed_up else self.config.normal_timeout
        max_retries = getattr(self.config, 'api_max_retries', 3)
        base_delay = getattr(self.config, 'api_retry_delay', 1.0)

        async with self.sem:
            start = time.time()
            session = await self._get_session()

            for attempt in range(max_retries):
                try:
                    url = self._build_url()
                    headers = self._build_headers()
                    payload = self._build_payload(texts)

                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            import json as json_module
                            data = json_module.loads(text)
                            embeddings = self._parse_response(data)

                            if embeddings:
                                self.stats.total_calls += 1
                                self.stats.total_time += time.time() - start
                                self._warmed_up = True
                                return embeddings

                        # 可重试的状态码: 429 (限流), 500, 502, 503, 504
                        if resp.status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)  # 指数退避
                            print(f"[WARN] Embed {resp.status}, retrying in {delay:.1f}s ({attempt + 1}/{max_retries})")
                            await asyncio.sleep(delay)
                            continue

                        self.stats.errors += 1
                        err_text = await resp.text()
                        print(f"[ERR] Embed {resp.status}: {err_text[:200]}")
                        return None

                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"[WARN] Embed timeout, retrying in {delay:.1f}s ({attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    self.stats.errors += 1
                    print(f"[ERR] Embed: Timeout after {max_retries} attempts")
                    return None

                except Exception as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"[WARN] Embed error: {e}, retrying in {delay:.1f}s ({attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    self.stats.errors += 1
                    print(f"[ERR] Embed: {e}")
                    return None

            return None

    async def embed_batch(
        self, texts: List[str], *, skip_failures: bool = True
    ) -> List[Optional[List[float]]]:
        """
        分批 Embedding

        Args:
            texts: 要嵌入的文本列表
            skip_failures: True 时失败的文本返回 None；False 时任一失败则整体返回空列表

        Returns:
            与 texts 等长的列表，成功的位置是向量，失败的位置是 None
        """
        if not texts:
            return []

        all_embeddings: List[Optional[List[float]]] = []
        batch_size = self.config.embed_batch_size

        batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        tasks = [self.embed(batch) for batch in batches]
        results = await asyncio.gather(*tasks)

        for batch_idx, result in enumerate(results):
            actual_batch_size = len(batches[batch_idx])
            if result and len(result) == actual_batch_size:
                all_embeddings.extend(result)
            else:
                if not skip_failures:
                    print(f"[WARN] Embed batch {batch_idx} failed, aborting all")
                    return []
                print(f"[WARN] Embed batch {batch_idx} failed, marking {actual_batch_size} items as None")
                all_embeddings.extend([None] * actual_batch_size)

        return all_embeddings[:len(texts)]

    async def warmup(self):
        """预热服务"""
        await self.embed(["test"])
        self._warmed_up = True


class RerankAPIClient:
    """
    通用 Rerank API 客户端

    支持三种模式：
    1. openai: OpenAI 兼容接口 (Jina/Cohere 格式)
    2. modal: Modal 自定义接口
    3. embedding: 使用 Embedding API 计算余弦相似度（无需专用 rerank 服务）
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self.sem = asyncio.Semaphore(self.config.rerank_concurrency)
        self.stats = APIStats()
        self._warmed_up = False
        self._session: Optional[aiohttp.ClientSession] = None
        # embedding 模式下复用 Embedding 客户端
        if self.config.rerank_api_type == "embedding":
            self._embed_client = EmbeddingAPIClient(self.config)
        else:
            self._embed_client = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=200, limit_per_host=100)
            self._session = aiohttp.ClientSession(connector=connector, trust_env=False)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        if self._embed_client:
            await self._embed_client.close()

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {"Content-Type": "application/json"}
        if self.config.rerank_api_key:
            headers["Authorization"] = f"Bearer {self.config.rerank_api_key}"
        return headers

    def _build_url(self) -> str:
        """构建请求 URL"""
        base_url = self.config.rerank_base_url.rstrip("/")
        if self.config.rerank_api_type == "openai":
            # Jina/Cohere 兼容: /v1/rerank
            if not base_url.endswith("/rerank"):
                if base_url.endswith("/v1"):
                    return f"{base_url}/rerank"
                return f"{base_url}/v1/rerank"
            return base_url
        else:
            # Modal 自定义接口
            return base_url

    def _build_payload(self, query: str, documents: List[str], top_n: Optional[int]) -> Dict[str, Any]:
        """构建请求体"""
        if self.config.rerank_api_type == "openai":
            # Jina/Cohere 格式
            payload: Dict[str, Any] = {
                "query": query,
                "documents": documents,
                "model": self.config.rerank_model
            }
            if top_n:
                payload["top_n"] = top_n
            return payload
        else:
            # Modal 格式
            payload = {"query": query, "documents": documents}
            if top_n:
                payload["top_n"] = top_n
            return payload

    def _parse_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析响应"""
        if self.config.rerank_api_type == "openai":
            # Jina/Cohere 格式: {"results": [{"index": 0, "relevance_score": 0.9}, ...]}
            return data.get("results", [])
        else:
            # Modal 格式: {"results": [...]}
            return data.get("results", [])

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def _rerank_via_embedding(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """使用 Embedding 余弦相似度进行 rerank"""
        if not self._embed_client:
            print("[ERR] Rerank(embedding): embed_client not initialized")
            return None

        start = time.time()
        try:
            # 将 query 和所有 documents 一次性 embed
            all_texts = [query] + documents
            embeddings = await self._embed_client.embed(all_texts)

            if not embeddings or len(embeddings) < 2:
                print("[ERR] Rerank(embedding): embedding failed or returned too few results")
                self.stats.errors += 1
                return None

            query_emb = embeddings[0]
            doc_embs = embeddings[1:]

            # 计算余弦相似度
            scores = []
            for i, doc_emb in enumerate(doc_embs):
                if doc_emb is None:
                    scores.append({"index": i, "relevance_score": 0.0})
                else:
                    sim = self._cosine_similarity(query_emb, doc_emb)
                    scores.append({"index": i, "relevance_score": sim})

            # 按分数降序排序
            scores.sort(key=lambda x: x["relevance_score"], reverse=True)

            if top_n:
                scores = scores[:top_n]

            self.stats.total_calls += 1
            self.stats.total_time += time.time() - start
            self._warmed_up = True
            return scores

        except Exception as e:
            self.stats.errors += 1
            print(f"[ERR] Rerank(embedding): {e}")
            return None

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """调用 Rerank 服务（带重试机制）"""
        if not documents:
            return []

        # embedding 模式：使用余弦相似度
        if self.config.rerank_api_type == "embedding":
            return await self._rerank_via_embedding(query, documents, top_n)

        timeout = self.config.cold_start_timeout if not self._warmed_up else self.config.normal_timeout
        max_retries = getattr(self.config, 'api_max_retries', 3)
        base_delay = getattr(self.config, 'api_retry_delay', 1.0)

        async with self.sem:
            start = time.time()
            session = await self._get_session()

            for attempt in range(max_retries):
                try:
                    url = self._build_url()
                    headers = self._build_headers()
                    payload = self._build_payload(query, documents, top_n)

                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()

                            self.stats.total_calls += 1
                            self.stats.total_time += time.time() - start
                            self._warmed_up = True

                            return self._parse_response(data)

                        # 可重试的状态码
                        if resp.status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            print(f"[WARN] Rerank {resp.status}, retrying in {delay:.1f}s ({attempt + 1}/{max_retries})")
                            await asyncio.sleep(delay)
                            continue

                        self.stats.errors += 1
                        err_text = await resp.text()
                        print(f"[ERR] Rerank {resp.status}: {err_text[:200]}")
                        return None

                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"[WARN] Rerank timeout, retrying in {delay:.1f}s ({attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    self.stats.errors += 1
                    print(f"[ERR] Rerank: Timeout after {max_retries} attempts")
                    return None

                except Exception as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"[WARN] Rerank error: {e}, retrying in {delay:.1f}s ({attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    self.stats.errors += 1
                    print(f"[ERR] Rerank: {e}")
                    return None

            return None

    async def warmup(self):
        """预热服务"""
        if self.config.rerank_api_type == "embedding":
            if self._embed_client:
                await self._embed_client.warmup()
                self._warmed_up = True
        else:
            await self.rerank("test", ["doc1", "doc2"])
            self._warmed_up = True


class ModalAPIClient:
    """
    统一 API 客户端 (兼容旧接口)

    整合 Embedding + Rerank 客户端，保持向后兼容
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self._embed_client = EmbeddingAPIClient(self.config)
        self._rerank_client = RerankAPIClient(self.config)

        # 兼容旧代码的信号量
        self.sem_embed = self._embed_client.sem
        self.sem_rerank = self._rerank_client.sem

        self._warmed_up = {"embed": False, "rerank": False}
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def stats(self) -> Dict[str, APIStats]:
        return {
            "embed": self._embed_client.stats,
            "rerank": self._rerank_client.stats
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        # 复用 embed client 的 session
        return await self._embed_client._get_session()

    async def close(self):
        await self._embed_client.close()
        await self._rerank_client.close()

    # ==================== 预热 ====================

    async def warmup(self):
        """预热 Embedding 和 Rerank 服务"""
        print("[WARMUP] Warming up Embed + Rerank...")
        start = time.time()

        tasks = [self._warmup_embed(), self._warmup_rerank()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(["Embed", "Rerank"], results):
            if isinstance(result, Exception):
                print(f"  [FAIL] {name}: {result}")
            else:
                print(f"  [OK] {name} ready")

        print(f"[WARMUP] Done in {time.time() - start:.1f}s")

    async def _warmup_embed(self):
        await self._embed_client.warmup()
        self._warmed_up["embed"] = True

    async def _warmup_rerank(self):
        await self._rerank_client.warmup()
        self._warmed_up["rerank"] = True

    # ==================== Embedding API ====================

    async def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """调用 Embedding 服务"""
        return await self._embed_client.embed(texts)

    async def embed_batch(
        self, texts: List[str], *, skip_failures: bool = True
    ) -> List[Optional[List[float]]]:
        """分批 Embedding"""
        return await self._embed_client.embed_batch(texts, skip_failures=skip_failures)

    # ==================== Rerank API ====================

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """调用 Rerank 服务"""
        return await self._rerank_client.rerank(query, documents, top_n)

    # ==================== 统计 ====================

    def print_stats(self):
        print("\n[API STATS]")
        for name, stats in self.stats.items():
            if stats.total_calls > 0:
                avg_time = stats.total_time / stats.total_calls
                print(f"  {name.upper()}: {stats.total_calls} calls, "
                      f"{stats.total_time:.1f}s total, "
                      f"{avg_time:.2f}s avg, "
                      f"{stats.errors} errors")


# 全局客户端
_client: Optional[ModalAPIClient] = None


def get_client(config=None) -> ModalAPIClient:
    global _client
    if _client is None or config is not None:
        _client = ModalAPIClient(config)
    return _client
