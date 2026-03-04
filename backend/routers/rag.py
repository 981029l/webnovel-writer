# Copyright (c) 2026 左岚. All rights reserved.
"""RAG 检索 API"""

import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
# from services import projects_manager  <-- Removed to be safe, though module import should be enhancing
from services.activity_logger import get_logger
from dependencies import get_project_root
import re

print("[RAG] Loading rag.py (v2.0) - Import fixed")

router = APIRouter()


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    mode: str = "hybrid"  # vector/bm25/hybrid
    top_k: int = 10


# get_project_root imported from dependencies


def get_rag_adapter(project_root: Path):
    """获取 RAGAdapter 实例"""
    try:
        from data_modules.config import DataModulesConfig
        from data_modules.rag_adapter import RAGAdapter
        config = DataModulesConfig.from_project_root(project_root)
        return RAGAdapter(config)
    except Exception as e:
        return None


@router.post("/search")
async def search(request: SearchRequest, root: Path = Depends(get_project_root)):
    """执行 RAG 搜索"""
    adapter = get_rag_adapter(root)
    
    if not adapter:
        return {"results": [], "error": "RAG 适配器未初始化"}
    
    try:
        if request.mode == "vector":
            results = await adapter.vector_search(request.query, request.top_k)
        elif request.mode == "bm25":
            results = adapter.bm25_search(request.query, request.top_k)
        else:  # hybrid
            results = await adapter.hybrid_search(request.query, rerank_top_n=request.top_k)
        
        # 转换为可序列化格式
        formatted = []
        for r in results:
            formatted.append({
                "chunk_id": r.chunk_id,
                "chapter": r.chapter,
                "scene_index": r.scene_index,
                "content": r.content,
                "score": round(r.score, 4),
                "source": r.source
            })
        
        # 记录活动
        logger = get_logger(root)
        if logger:
            logger.log(
                type="rag",
                action="generated",
                title=f"RAG 检索：{request.query[:20]}..."
            )

        return {"results": formatted, "query": request.query, "mode": request.mode}
    except Exception as e:
        return {"results": [], "error": str(e)}


@router.get("/stats")
async def get_rag_stats(root: Path = Depends(get_project_root)):
    """获取 RAG 统计信息"""
    adapter = get_rag_adapter(root)
    
    if not adapter:
        return {"stats": None, "error": "RAG 适配器未初始化"}
    
    try:
        stats = adapter.get_stats()
        return {"stats": stats}
    except Exception as e:
        return {"stats": None, "error": str(e)}


@router.get("/test")
async def test_rag(
    query: str = Query(..., description="测试查询"),
    root: Path = Depends(get_project_root)
):
    """测试 RAG 检索"""
    adapter = get_rag_adapter(root)
    
    if not adapter:
        return {"success": False, "error": "RAG 适配器未初始化"}
    
    try:
        # 测试 BM25（不需要 API）
        bm25_results = adapter.bm25_search(query, 5)
        
        return {
            "success": True,
            "bm25_count": len(bm25_results),
            "sample": bm25_results[0].content[:200] if bm25_results else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/index/all")
async def index_all_chapters(root: Path = Depends(get_project_root)):
    """扫描并索引所有章节"""
    adapter = get_rag_adapter(root)
    if not adapter:
        return {"success": False, "error": "RAG 适配器未初始化"}

    try:
        print("[RAG] Starting index_all_chapters (v2.0)...")
        # import re -> moved to top level
        
        # 获取所有章节文件
        chapters_dir = root / "正文"
        if not chapters_dir.exists():
            return {"success": False, "error": "找不到正文目录"}
            
        files = sorted(list(chapters_dir.glob("第*章*.md")))
        total_chunks = 0
        
        for file_path in files:
            content = file_path.read_text(encoding="utf-8")
            
            # 解析章节号
            match = re.search(r"第(\d+)章", file_path.name)
            chapter_num = int(match.group(1)) if match else 0
            
            # 简单分场景：按 ## 场景X 或 --- 分割
            # 如果没有明显标记，则按固定长度切分
            scenes = []
            if "## 场景" in content:
                parts = re.split(r"(## 场景\d+.*)", content)
                current_scene = ""
                idx = 1
                for part in parts:
                    if part.startswith("## 场景"):
                        if current_scene.strip():
                            scenes.append({"index": idx, "content": current_scene.strip()})
                            idx += 1
                        current_scene = part + "\n"
                    else:
                        current_scene += part
                if current_scene.strip():
                    scenes.append({"index": idx, "content": current_scene.strip()})
            else:
                # 按长度切分 (每 800 字)
                text = content
                idx = 1
                while text:
                    scenes.append({"index": idx, "content": text[:800]})
                    text = text[800:]
                    idx += 1
            
            # 构造 chunks
            chunks = [
                {
                    "chapter": chapter_num,
                    "scene_index": s["index"],
                    "content": s["content"]
                }
                for s in scenes
            ]
            
            if chunks:
                stored = await adapter.store_chunks(chunks)
                total_chunks += stored
                
        return {"success": True, "indexed_files": len(files), "total_chunks": total_chunks}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
