 
"""FastAPI 入口文件 - Webnovel Writer 后端服务 (v1.0.1)"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 添加 scripts 目录到 Python 路径，复用现有 data_modules
scripts_path = Path(__file__).parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(scripts_path))

from routers import projects, outlines, chapters, entities, rag, ai, characters, fanqie

app = FastAPI(
    title="Webnovel Writer API",
    description="长篇网文辅助创作系统 API",
    version="1.0.0"
)

# CORS 配置，允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(projects.router, prefix="/api/projects", tags=["项目管理"])
app.include_router(outlines.router, prefix="/api/outlines", tags=["大纲管理"])
app.include_router(chapters.router, prefix="/api/chapters", tags=["章节管理"])
app.include_router(entities.router, prefix="/api/entities", tags=["实体管理"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG检索"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI写作"])
app.include_router(characters.router)
app.include_router(fanqie.router, prefix="/api/fanqie", tags=["番茄自动上传"])


@app.get("/")
async def root():
    return {"message": "Webnovel Writer API", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}
