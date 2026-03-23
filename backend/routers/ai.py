 
"""AI 写作 API - 使用 SkillExecutor 完整复用 .claude/skills 工作流"""

import json
import sys
import re
from pathlib import Path
from typing import List, Optional, Union
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dependencies import get_project_root
from services.genre_catalog import canonical_genre_id, canonical_substyle_id, list_supported_genres

router = APIRouter()

# 添加 scripts 目录到路径
SCRIPTS_PATH = Path(__file__).parent.parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))


class AIConfig(BaseModel):
    base_url: str = "http://localhost:8317"
    api_key: Optional[str] = ""
    model: str = "gpt-4"


class InitRequest(BaseModel):
    title: str
    genre: str
    substyle: str = ""
    protagonist_name: str = ""
    golden_finger_name: str = ""
    golden_finger_type: str = ""
    additional_info: str = ""  # 新增：用户补充设定
    target_words: Optional[int] = None
    mode: str = "standard"


class PlanRequest(BaseModel):
    volume: int
    chapters_count: int = 30
    guidance: str = ""


class WriteRequest(BaseModel):
    chapter: int
    word_count: int = 3500


class ReviewRequest(BaseModel):
    content: Optional[str] = None


# get_project_root imported from dependencies


def get_skill_executor(project_root: Path):
    from services.skill_executor import SkillExecutor
    from services.ai_service import get_ai_service
    return SkillExecutor(project_root, get_ai_service())


def _find_chapter_files(chapters_dir: Path, chapter_id: int):
    exact = sorted(chapters_dir.glob(f"第{chapter_id}章*.md"))
    if exact:
        return exact
    matches = []
    for f in chapters_dir.glob("第*章*.md"):
        m = re.search(r"第0*(\d+)章", f.stem)
        if not m:
            continue
        try:
            if int(m.group(1)) == chapter_id:
                matches.append(f)
        except ValueError:
            continue
    return sorted(matches)


@router.get("/config")
async def get_config():
    from services.ai_service import get_ai_service
    service = get_ai_service()
    return {"base_url": service.base_url, "model": service.model, "has_api_key": bool(service.api_key)}


@router.put("/config")
async def update_config(config: AIConfig):
    from services.ai_service import configure_ai_service
    configure_ai_service(config.base_url, config.api_key, config.model)
    return {"success": True}


@router.post("/init")
async def init_project_api(request: InitRequest, root: Path = Depends(get_project_root)):
    """执行 webnovel-init Skill 完整工作流"""
    if request.target_words is not None and request.target_words <= 0:
        raise HTTPException(status_code=400, detail="目标字数必须大于 0")

    executor = get_skill_executor(root)
    genre = canonical_genre_id(request.genre)
    substyle = canonical_substyle_id(genre, request.substyle)

    try:
        result = await executor.execute_init(
            title=request.title,
            genre=genre,
            substyle=substyle,
            protagonist_name=request.protagonist_name,
            golden_finger_name=request.golden_finger_name,
            golden_finger_type=request.golden_finger_type,
            additional_info=request.additional_info,
            target_words=request.target_words,
            mode=request.mode
        )
        return {"success": result["success"], "steps": result["steps"], "message": f"项目 '{request.title}' 初始化完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/init-stream")
async def init_project_stream_api(request: InitRequest, root: Path = Depends(get_project_root)):
    """启动后台初始化任务，立即返回让前端跳转"""
    if request.target_words is not None and request.target_words <= 0:
        raise HTTPException(status_code=400, detail="目标字数必须大于 0")

    executor = get_skill_executor(root)
    genre = canonical_genre_id(request.genre)
    substyle = canonical_substyle_id(genre, request.substyle)
    async def event_generator():
        try:
            # 流式执行初始化
            async for update in executor.execute_init_stream(
                title=request.title,
                genre=genre,
                substyle=substyle,
                protagonist_name=request.protagonist_name,
                golden_finger_name=request.golden_finger_name,
                golden_finger_type=request.golden_finger_type,
                mode=request.mode,
                additional_info=request.additional_info,
                target_words=request.target_words
            ):
                # SSE 格式: data: <json>\n\n
                yield f"data: {update}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/plan")
async def plan_volume_api(request: PlanRequest, root: Path = Depends(get_project_root)):
    """执行 webnovel-plan Skill 完整工作流"""
    executor = get_skill_executor(root)

    try:
        # 如果 volume 为 0，则规划总纲
        if request.volume == 0:
            result = await executor.execute_replan_outline(guidance=request.guidance)
            return {
                "success": result["success"],
                "steps": [{"step": 1, "name": "AI 规划总纲", "success": result["success"]}],
                "volume": 0,
                "content": result.get("content", ""),
                "path": str(root / "大纲" / "总纲.md")
            }
        else:
            result = await executor.execute_plan(volume=request.volume, chapters_count=request.chapters_count)
            return {
                "success": result["success"],
                "steps": result["steps"],
                "volume": request.volume,
                "content": result.get("content", ""),
                "path": result.get("path", "")
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/plan-stream")
async def plan_volume_stream_api(request: PlanRequest, root: Path = Depends(get_project_root)):
    """流式执行 webnovel-plan Skill"""
    executor = get_skill_executor(root)
    
    async def event_generator():
        try:
            if request.volume == 0:
                generator = executor.execute_replan_outline_stream(guidance=request.guidance)
            else:
                generator = executor.execute_plan_stream(volume=request.volume, chapters_count=request.chapters_count)

            async for update in generator:
                yield f"data: {update}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")



@router.post("/generate-synopsis")
async def generate_synopsis_api(root: Path = Depends(get_project_root)):
    """AI 生成/更新小说简介"""
    executor = get_skill_executor(root)
    try:
        result = await executor.execute_generate_synopsis()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-titles")
async def generate_titles_api(root: Path = Depends(get_project_root)):
    """AI 根据现有设定灵感起名"""
    executor = get_skill_executor(root)
    try:
        result = await executor.execute_generate_titles()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write")
async def write_chapter_api(request: WriteRequest, root: Path = Depends(get_project_root)):
    """执行 webnovel-write Skill 完整工作流"""
    executor = get_skill_executor(root)

    try:
        result = await executor.execute_write(chapter=request.chapter, word_count=request.word_count)
        return {
            "success": result["success"],
            "steps": result.get("steps", []),
            "chapter": request.chapter,
            "title": result.get("title", ""),
            "content": result.get("content", ""),
            "summary": result.get("summary", ""),
            "review": result.get("review", {}),
            "word_count": len(result.get("content", "")),
            "path": result.get("path", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/write-stream")
async def write_chapter_stream_api(request: WriteRequest, root: Path = Depends(get_project_root)):
    """流式执行 webnovel-write Skill"""
    executor = get_skill_executor(root)
    
    async def event_generator():
        try:
            async for update in executor.execute_write_stream(chapter=request.chapter, word_count=request.word_count):
                yield f"data: {update}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


class PolishRequest(BaseModel):
    chapter_id: int
    content: str
    suggestions: Union[List[str], str]  # Support both list and string
    mode: str = "rewrite"


@router.post("/polish")
async def polish_chapter_api(request: PolishRequest, root: Path = Depends(get_project_root)):
    """AI 根据建议润色章节"""
    executor = get_skill_executor(root)
    
    # Format suggestions if it's a list
    suggestions_str = request.suggestions
    if isinstance(request.suggestions, list):
        suggestions_str = "\n".join([f"- {s}" for s in request.suggestions])
        
    try:
        result = await executor.execute_polish(
            chapter_id=request.chapter_id,
            content=request.content,
            suggestions=suggestions_str,
            mode=request.mode,
        )
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Polish failed"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 

@router.post("/polish-stream")
async def polish_chapter_stream_api(request: PolishRequest, root: Path = Depends(get_project_root)):
    """流式执行 AI 润色"""
    executor = get_skill_executor(root)
    
    # Format suggestions if it's a list
    suggestions_str = request.suggestions
    if isinstance(request.suggestions, list):
        suggestions_str = "\n".join([f"- {s}" for s in request.suggestions])

    async def event_generator():
        try:
             async for update in executor.execute_polish_stream(
                chapter_id=request.chapter_id,
                content=request.content,
                suggestions=suggestions_str,
                mode=request.mode,
             ):
                # 兼容两种返回：JSON 字符串（新版）或 dict（旧版）
                if isinstance(update, str):
                    yield f"data: {update}\n\n"
                else:
                    import json
                    yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


class PolishOutlineRequest(BaseModel):
    volume: int
    content: str
    requirements: str


@router.post("/polish-outline-stream")
async def polish_outline_stream_api(request: PolishOutlineRequest, root: Path = Depends(get_project_root)):
    """流式执行大纲润色"""
    executor = get_skill_executor(root)
    
    async def event_generator():
        try:
            async for update in executor.execute_polish_outline_stream(
                volume=request.volume,
                content=request.content,
                requirements=request.requirements
            ):
                yield f"data: {update}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/review")
async def review_chapter_api(chapter: int, request: Optional[ReviewRequest] = None, root: Path = Depends(get_project_root)):
    """AI 审查章节（五维评分）"""
    content = (request.content if request and request.content else "").strip()
    if not content:
        chapters_dir = root / "正文"
        files = _find_chapter_files(chapters_dir, chapter)
        if not files:
            raise HTTPException(status_code=404, detail=f"未找到第{chapter}章")
        content = files[0].read_text(encoding="utf-8")

    if len(content.strip()) < 100:
        raise HTTPException(status_code=400, detail="章节内容过少（<100字），无法进行 AI 审查。请先生成或撰写正文。")

    executor = get_skill_executor(root)
    try:
        # 使用 SkillExecutor 执行审查 (自动加载 review.md Skill)
        result = await executor.execute_review(chapter_id=chapter, content=content)
        return {"success": True, "chapter": chapter, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/genres")
async def get_genres():
    """获取支持的题材列表"""
    return {"genres": list_supported_genres()}


@router.get("/skills")
async def list_skills():
    """列出所有可用的 Skills"""
    skills_dir = SCRIPTS_PATH.parent / "skills"
    skills = []
    if skills_dir.exists():
        for d in skills_dir.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                skill_md = (d / "SKILL.md").read_text(encoding="utf-8")[:500]
                skills.append({"id": d.name, "preview": skill_md[:200]})
    return {"skills": skills}


class EndingPlanRequest(BaseModel):
    remaining_chapters: int = 5


@router.post("/ending-plan")
async def generate_ending_plan(
    request: EndingPlanRequest,
    root: Path = Depends(get_project_root)
):
    """生成收尾规划"""
    executor = get_skill_executor(root)

    try:
        result = await executor.execute_generate_ending_plan(request.remaining_chapters)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
async def list_models_api():
    """获取可用模型列表"""
    from services.ai_service import get_ai_service
    service = get_ai_service()
    try:
        models = await service.list_models()
        return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "error": str(e), "models": []}


@router.get("/test")
async def test_connection():
    from services.ai_service import get_ai_service
    try:
        service = get_ai_service()
        result = await service.chat([{"role": "user", "content": "回复'连接成功'"}], temperature=0, max_tokens=20)
        return {"success": True, "response": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
