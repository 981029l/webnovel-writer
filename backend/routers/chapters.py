# Copyright (c) 2026 左岚. All rights reserved.
"""章节管理 API"""

import re
import time
from pathlib import Path
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from services import projects_manager
from services.activity_logger import get_logger
from dependencies import get_project_root

router = APIRouter()
_extract_ok: set[int] = set() # 追踪已成功提取的章节，避免重复提取
_tasks: Dict[str, Dict[str, Any]] = {}  # 模块级任务存储


class ChapterInfo(BaseModel):
    """章节信息"""
    id: int
    title: str
    word_count: int
    path: str


class ChapterContent(BaseModel):
    """章节内容"""
    id: int
    title: str
    content: str
    word_count: int
    summary: Optional[str] = None


class ChapterUpdate(BaseModel):
    """章节更新请求"""
    title: Optional[str] = None
    content: str
    trigger_extraction: bool = False
    review_raw: Optional[str] = None
    force_extract: bool = False


class ExtractApplyRequest(BaseModel):
    """提取确认写入请求"""
    extraction: dict
    content: Optional[str] = None  # 前端编辑器内容，章节未保存时兜底


class ExtractPreviewRequest(BaseModel):
    """提取预览请求"""
    content: Optional[str] = None  # 前端编辑器内容，为空时回退读磁盘


class WriteRequest(BaseModel):
    """AI 创作请求"""
    chapter: int
    outline: Optional[str] = None  # 章节大纲


class ReviewRequest(BaseModel):
    """审查请求"""
    chapters: List[int]


# get_project_root imported from dependencies


def _find_chapter_files(chapters_dir: Path, chapter_id: int) -> List[Path]:
    """按章节号查找文件，兼容 `第002章` 这类前导零命名。"""
    exact = sorted(chapters_dir.glob(f"第{chapter_id}章*.md"))
    if exact:
        return exact

    matches: List[Path] = []
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


def parse_chapter_file(file_path: Path) -> dict:
    """解析章节文件"""
    name = file_path.stem
    match = re.search(r"第(\d+)章[：:\-\s]*(.+)?", name)

    if match:
        chapter_id = int(match.group(1))
        title = match.group(2) or ""
    else:
        chapter_id = 0
        title = name

    content = file_path.read_text(encoding="utf-8")

    # 提取摘要（如果有）
    summary = None
    summary_match = re.search(r"<!--\s*summary:\s*(.+?)\s*-->", content, re.DOTALL)
    if summary_match:
        summary = summary_match.group(1).strip()

    return {
        "id": chapter_id,
        "title": title.strip(),
        "content": content,
        "word_count": len(content),
        "summary": summary,
        "path": str(file_path)
    }


def _safe_title_for_filename(title: str) -> str:
    text = (title or "").strip()
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or "无标题"


def _has_blocking_review_issues(review_text: str) -> tuple[bool, str]:
    """
    根据审查文本判定是否拦截自动提取。

    策略：先检查"通过信号"（无需修改/质量良好等），有则直接放行，
    避免分类标题中的关键词（如"设定一致性"）误触发拦截。
    """
    text = (review_text or "").strip()
    if not text:
        return False, ""

    # 1. 通过信号：审查明确表示没问题 → 直接放行
    pass_signals = re.compile(
        r"(无需修改|可直接采用|质量良好|无明显问题|无问题|整体优秀|完美契合|"
        r"无设定冲突|无冲突|设定一致|无矛盾|无需改动|无修改意见|可直接发布)",
        re.IGNORECASE
    )
    if pass_signals.search(text):
        return False, ""

    upper_text = text.upper()

    # 2. P0/P1：必须有 "P0:" + 实际问题描述才算命中
    p0_problem = re.search(r"P0\s*[:：]\s*(?!无|没有|未发现|不存在|0|零)", text, re.IGNORECASE)
    if p0_problem:
        return True, "审查命中 P0 问题，已拦截自动提取"

    p1_problem = re.search(r"P1\s*[:：]\s*(?!无|没有|未发现|不存在|0|零)", text, re.IGNORECASE)
    if p1_problem:
        return True, "审查命中 P1 问题，已拦截自动提取"

    # 3. 严重问题模式（前后 8 字有否定词就跳过）
    negation = re.compile(r"(无|没有|未发现|未检出|不存在|不|零|未)")
    severe_patterns = [
        (r"设定(?:一致性)?(?:冲突|错误|不一致)", "审查提示设定冲突，已拦截自动提取"),
        (r"地点(?:冲突|错误|不一致)", "审查提示地点冲突，已拦截自动提取"),
        (r"角色名(?:错误|冲突|不一致|漂移)", "审查提示角色名冲突，已拦截自动提取"),
        (r"(?:严重|高危).{0,6}BUG", "审查提示严重 BUG，已拦截自动提取"),
        (r"(?:需|必须)\s*(?:立即|尽快)?\s*修改", "审查标记需修改，已拦截自动提取"),
    ]
    for pattern, reason in severe_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            prefix = text[max(0, m.start() - 8):m.start()]
            suffix = text[m.end():min(len(text), m.end() + 8)]
            if negation.search(prefix) or negation.search(suffix):
                continue  # 前后有否定词，跳过
            return True, reason

    return False, ""


@router.get("")
async def get_chapters(root: Path = Depends(get_project_root)):
    """获取章节列表"""
    chapters_dir = root / "正文"

    if not chapters_dir.exists():
        return {"chapters": []}

    chapters = []
    for f in sorted(chapters_dir.glob("第*章*.md")):
        info = parse_chapter_file(f)
        chapters.append({
            "id": info["id"],
            "title": info["title"],
            "word_count": info["word_count"],
            "path": info["path"]
        })

    # 按章节号排序
    chapters.sort(key=lambda x: x["id"])

    return {"chapters": chapters, "total": len(chapters)}


@router.get("/stats")
async def get_chapter_stats(root: Path = Depends(get_project_root)):
    """获取章节统计（必须在 /{chapter_id} 之前定义）"""
    chapters_dir = root / "正文"

    if not chapters_dir.exists():
        return {"total_chapters": 0, "total_words": 0, "avg_words": 0}

    chapter_files = list(chapters_dir.glob("第*章*.md"))
    total_words = 0

    for f in chapter_files:
        content = f.read_text(encoding="utf-8")
        total_words += len(content)

    total_chapters = len(chapter_files)
    avg_words = total_words // total_chapters if total_chapters > 0 else 0

    return {
        "total_chapters": total_chapters,
        "total_words": total_words,
        "avg_words": avg_words
    }


@router.get("/{chapter_id}")
async def get_chapter(chapter_id: int, root: Path = Depends(get_project_root)):
    """获取章节内容"""
    chapters_dir = root / "正文"

    # 查找章节文件
    files = _find_chapter_files(chapters_dir, chapter_id)

    if not files:
        raise HTTPException(status_code=404, detail=f"未找到第{chapter_id}章")

    return parse_chapter_file(files[0])


@router.put("/{chapter_id}")
async def update_chapter(chapter_id: int, data: ChapterUpdate, root: Path = Depends(get_project_root)):
    """更新章节内容"""
    chapters_dir = root / "正文"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    # 查找或创建章节文件
    files = _find_chapter_files(chapters_dir, chapter_id)

    # 检查内容是否有变化（用于决定是否需要重新提取角色）
    old_content = ""
    if files:
        chapter_file = files[0]
        old_content = chapter_file.read_text(encoding="utf-8")
        # 如果提供了新标题，重命名文件
        if data.title:
            safe_title = _safe_title_for_filename(data.title)
            new_file = chapters_dir / f"第{chapter_id}章-{safe_title}.md"
            if new_file != chapter_file:
                chapter_file.rename(new_file)
                chapter_file = new_file
    else:
        title = _safe_title_for_filename(data.title)
        chapter_file = chapters_dir / f"第{chapter_id}章-{title}.md"

    # 判断内容是否有实质变化
    content_changed = data.content.strip() != old_content.strip()

    chapter_file.write_text(data.content, encoding="utf-8")

    # 记录活动
    logger = get_logger(root)
    if logger:
        logger.log(
            type="write",
            action="updated" if files else "created",
            title=f"第{chapter_id}章：{data.title or '无标题'}"
        )

    # 保存即提取：内容有变化、或前次提取未成功 → 触发提取
    prev_ok = chapter_id in _extract_ok
    should_extract = (
        data.trigger_extraction
        and bool(data.content.strip())
        and (content_changed or data.force_extract or not prev_ok)
    )
    extract_blocked = False
    extract_block_reason = ""

    if should_extract and not data.force_extract:
        blocked, reason = _has_blocking_review_issues(data.review_raw or "")
        if blocked:
            should_extract = False
            extract_blocked = True
            extract_block_reason = reason

    task_id = None

    if should_extract:
        import asyncio
        import uuid
        from services.skill_executor import SkillExecutor
        from services.ai_service import get_ai_service

        # 生成任务 ID
        task_id = str(uuid.uuid4())[:8]

        _tasks[task_id] = {"status": "running", "message": "角色档案更新中..."}

        async def extract_characters_background():
            nonlocal task_id
            try:
                print(f"[角色系统] 开始提取第{chapter_id}章角色...")
                ai_service = get_ai_service()
                executor = SkillExecutor(project_root=root, ai_service=ai_service)
                await executor._update_character_state(chapter_id, data.content)
                _tasks[task_id] = {"status": "completed", "message": "角色档案更新完成", "_done_at": time.time()}
                _extract_ok.add(chapter_id) # 标记提取成功
                print(f"[角色系统] 第{chapter_id}章角色提取完成")
            except Exception as e:
                import traceback
                _tasks[task_id] = {"status": "error", "message": str(e)[:100], "_done_at": time.time()}
                _extract_ok.discard(chapter_id) # 失败时清除标记，下次保存可重试
                print(f"[角色系统] 第{chapter_id}章角色提取失败: {e}")
                traceback.print_exc()

        asyncio.create_task(extract_characters_background())

    return {
        "success": True,
        "path": str(chapter_file),
        "word_count": len(data.content),
        "task_id": task_id,
        "content_changed": content_changed,
        "extract_triggered": should_extract,
        "extract_blocked": extract_blocked,
        "extract_block_reason": extract_block_reason
    }

@router.post("/{chapter_id}/extract")
async def force_extract_chapter(chapter_id: int, root: Path = Depends(get_project_root)):
    """强制触发章节的角色/世界观提取（一步到位，CLI 后门）"""
    chapters_dir = root / "正文"
    files = _find_chapter_files(chapters_dir, chapter_id)

    if not files:
        raise HTTPException(status_code=404, detail="章节不存在")

    chapter_file = files[0]
    content = chapter_file.read_text(encoding="utf-8")

    import asyncio
    import uuid
    from services.skill_executor import SkillExecutor
    from services.ai_service import get_ai_service

    task_id = str(uuid.uuid4())[:8]

    _tasks[task_id] = {"status": "running", "message": "正在强制分析世界观..."}

    async def extract_background():
        try:
            print(f"[世界观系统] 强制提取第{chapter_id}章数据...")
            ai_service = get_ai_service()
            executor = SkillExecutor(project_root=root, ai_service=ai_service)
            await executor._update_character_state(chapter_id, content)
            _tasks[task_id] = {"status": "completed", "message": "世界观提取完成", "_done_at": time.time()}
            print(f"[世界观系统] 第{chapter_id}章强制提取完成")
        except Exception as e:
            _tasks[task_id] = {"status": "error", "message": str(e)[:100], "_done_at": time.time()}
            print(f"[世界观系统] 强制提取失败: {e}")
            import traceback
            traceback.print_exc()

    asyncio.create_task(extract_background())

    return {"success": True, "task_id": task_id}


@router.post("/{chapter_id}/extract-preview")
async def extract_preview(chapter_id: int, req: ExtractPreviewRequest = None, root: Path = Depends(get_project_root)):
    """提取预览：仅 AI 分析，不写入磁盘。前端轮询 task 状态获取结果。"""
    # 优先用前端传来的编辑器内容，没有则回退读磁盘
    content = (req.content if req and req.content else None)
    if not content:
        chapters_dir = root / "正文"
        files = _find_chapter_files(chapters_dir, chapter_id)
        if not files:
            raise HTTPException(status_code=404, detail="章节不存在")
        content = files[0].read_text(encoding="utf-8")

    if not content.strip():
        raise HTTPException(status_code=400, detail="章节内容为空，无法提取")

    import asyncio
    import uuid
    from services.skill_executor import SkillExecutor
    from services.ai_service import get_ai_service

    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "running", "message": "AI 正在分析设定数据..."}

    async def preview_background():
        try:
            print(f"[世界观系统] 开始预览提取第{chapter_id}章...")
            ai_service = get_ai_service()
            executor = SkillExecutor(project_root=root, ai_service=ai_service)
            result = await executor._extract_chapter_entities(chapter_id, content)
            if result is None:
                _tasks[task_id] = {
                    "status": "completed",
                    "message": "未提取到新设定",
                    "result": None,
                    "_done_at": time.time(),
                }
            else:
                _tasks[task_id] = {
                    "status": "completed",
                    "message": "设定同步预览就绪",
                    "result": result,
                    "_done_at": time.time(),
                }
            print(f"[世界观系统] 第{chapter_id}章预览提取完成")
        except Exception as e:
            _tasks[task_id] = {"status": "error", "message": str(e)[:100], "_done_at": time.time()}
            print(f"[世界观系统] 预览提取失败: {e}")
            import traceback
            traceback.print_exc()

    asyncio.create_task(preview_background())

    return {"success": True, "task_id": task_id}


@router.post("/{chapter_id}/extract-apply")
async def extract_apply(chapter_id: int, req: ExtractApplyRequest, root: Path = Depends(get_project_root)):
    """将用户确认后的提取结果写入磁盘。"""
    # 优先读磁盘文件，没有则用前端传来的 content
    content = None
    chapters_dir = root / "正文"
    files = _find_chapter_files(chapters_dir, chapter_id)
    if files:
        content = files[0].read_text(encoding="utf-8")
    elif req.content:
        content = req.content
    else:
        raise HTTPException(status_code=404, detail="章节不存在且未提供内容")

    from services.skill_executor import SkillExecutor
    from services.ai_service import get_ai_service

    try:
        ai_service = get_ai_service()
        executor = SkillExecutor(project_root=root, ai_service=ai_service)
        summary = await executor._apply_extraction_results(chapter_id, content, req.extraction)
        _extract_ok.add(chapter_id)
        return {"success": True, **summary}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)[:200])


_TASK_TTL = 600  # 已完成任务保留 10 分钟


def _purge_stale_tasks():
    """清理超过 TTL 的已完成/已失败任务。"""
    now = time.time()
    stale = [
        tid for tid, t in _tasks.items()
        if t.get("_done_at") and now - t["_done_at"] > _TASK_TTL
    ]
    for tid in stale:
        del _tasks[tid]


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """获取后台任务状态（含 result 字段用于预览数据传递）。

    已完成/失败的任务不会立即删除，需客户端 DELETE /tasks/{task_id} 确认，
    或等待 10 分钟自动过期。
    """
    _purge_stale_tasks()

    task = _tasks.get(task_id)
    if not task:
        return {"status": "unknown", "message": "任务不存在"}

    return dict(task)


@router.delete("/tasks/{task_id}")
async def ack_task(task_id: str):
    """客户端确认已收到任务结果，删除任务记录。"""
    removed = _tasks.pop(task_id, None)
    return {"success": removed is not None}


@router.delete("/{chapter_id}")
async def delete_chapter(chapter_id: int, root: Path = Depends(get_project_root)):
    """删除章节"""
    chapters_dir = root / "正文"

    files = _find_chapter_files(chapters_dir, chapter_id)

    if not files:
        raise HTTPException(status_code=404, detail=f"未找到第{chapter_id}章")

    files[0].unlink()

    # 记录活动
    logger = get_logger(root)
    if logger:
        logger.log(
            type="write",
            action="deleted",
            title=f"第{chapter_id}章"
        )

    return {"success": True}


@router.post("/write")
async def write_chapter(request: WriteRequest, project_root: Optional[str] = Query(None)):
    """AI 创作章节（占位接口，需要集成 AI 服务）"""
    # TODO: 集成 Context Agent 和写作流程
    return {
        "success": False,
        "message": "AI 创作功能需要配置 AI 服务后使用",
        "chapter": request.chapter
    }


@router.post("/review")
async def review_chapters(request: ReviewRequest, project_root: Optional[str] = Query(None)):
    """审查章节（占位接口）"""
    # TODO: 集成五维审查 Agents
    results = []
    for chapter in request.chapters:
        results.append({
            "chapter": chapter,
            "scores": {
                "high_point": 0,  # 爽点
                "consistency": 0,  # 一致性
                "pacing": 0,  # 节奏
                "ooc": 0,  # OOC
                "continuity": 0  # 连贯性
            },
            "issues": [],
            "suggestions": []
        })

    return {"results": results, "message": "审查功能需要配置 AI 服务后使用"}
