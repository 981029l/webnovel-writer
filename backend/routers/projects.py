 
"""项目管理 API"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from services import projects_manager
from services.activity_logger import get_logger
from services.genre_catalog import canonical_genre_id, canonical_substyle_id, list_supported_genres
from services.project_prompt_store import (
    get_project_prompt_config,
    update_project_prompt_contents,
    reset_project_prompts,
    ensure_project_prompts,
    sync_project_prompts_for_profile_change,
    push_project_prompt_to_global,
)
from dependencies import get_project_root

router = APIRouter()


class ProjectStatus(BaseModel):
    """项目状态"""
    initialized: bool
    project_root: str
    current_chapter: int = 0
    total_chapters: int = 0
    total_words: int = 0
    target_words: Optional[int] = None  # 目标字数
    protagonist: Optional[dict] = None
    genre: Optional[str] = None
    substyle: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None  # 小说简介
    status: str = "连载中"  # 项目状态：连载中/已完结
    outline_invalidated: bool = False
    outline_invalidation_reason: Optional[str] = None


class ProjectConfig(BaseModel):
    """项目配置"""
    embed_api_key: Optional[str] = None
    rerank_api_key: Optional[str] = None
    ai_base_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None


class InitRequest(BaseModel):
    """项目初始化请求"""
    genre: str = "修仙"
    substyle: str = ""
    mode: str = "standard"


class PromptSlotUpdate(BaseModel):
    id: str
    content: str


class ProjectPromptConfigUpdate(BaseModel):
    prompts: List[PromptSlotUpdate]


class ProjectPromptResetRequest(BaseModel):
    slot_ids: Optional[List[str]] = None


# ======= 工具函数 =======

# get_project_root imported from dependencies



@router.get("/activities")
async def get_activities(root: Path = Depends(get_project_root)):
    """获取项目动态"""
    logger = get_logger(root)
    if logger:
        return {"activities": logger.get_activities()}
    return {"activities": []}


@router.get("/list")
async def list_projects():
    """获取项目列表和当前活动项目"""
    projects = projects_manager.list_projects()
    current = projects_manager.get_current_project()
    return {
        "projects": projects,
        "current": current
    }


@router.get("/status", response_model=ProjectStatus)
async def get_status(root: Path = Depends(get_project_root)):
    """获取项目状态"""
    webnovel_dir = root / ".webnovel"
    state_file = webnovel_dir / "state.json"
    chapters_dir = root / "正文"
    
    # 检查并读取状态
    state = {}
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except:
            pass
            
    initialized = state.get("initialized", True) if state else False
    
    status = ProjectStatus(
        initialized=initialized,
        project_root=str(root)
    )
    
    # 只要 state 存在，就提取基础元数据（确保重置后标题不丢）
    if state:
        status.current_chapter = state.get("current_chapter", 0)
        status.protagonist = state.get("protagonist_state") or state.get("protagonist")
        
        # Handle project_info (New Format)
        info = state.get("project_info", {})
        if info:
            status.genre = info.get("genre")
            status.substyle = info.get("substyle")
            status.title = info.get("title")
            status.target_words = info.get("target_words")
            status.description = info.get("description") or info.get("synopsis")
            status.status = info.get("status", "连载中")
            status.outline_invalidated = bool(info.get("outline_invalidated", False))
            status.outline_invalidation_reason = info.get("outline_invalidation_reason")
        else:
            status.genre = state.get("genre")
            status.substyle = state.get("substyle")
            status.title = state.get("title")
            status.target_words = state.get("target_words")
            status.description = state.get("description") or state.get("synopsis")
            status.status = state.get("status", "连载中")
    
    
    # 统计章节数和字数
    if chapters_dir.exists():
        chapter_files = list(chapters_dir.glob("第*章*.md"))
        status.total_chapters = len(chapter_files)
        total_words = 0
        for f in chapter_files:
            try:
                content = f.read_text(encoding="utf-8")
                total_words += len(content)  # 简单按字符计数
            except Exception:
                pass
        status.total_words = total_words
    
    return status


@router.get("/settings")
async def get_settings(root: Path = Depends(get_project_root)):
    """获取设定集内容（世界观、力量体系、主角卡）"""
    settings_dir = root / "设定集"
    
    def read_setting(filename: str) -> str:
        filepath = settings_dir / filename
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8")
                # 去掉标题行，只返回内容
                lines = content.split('\n')
                if lines and lines[0].startswith('#'):
                    return '\n'.join(lines[1:]).strip()
                return content.strip()
            except:
                return ""
        return ""
    
    return {
        "worldview": read_setting("世界观.md"),
        "power_system": read_setting("力量体系.md"),
        "protagonist": read_setting("主角卡.md"),
        "golden_finger": read_setting("金手指设计.md")
    }

@router.get("/config")
async def get_config(root: Path = Depends(get_project_root)):
    """获取项目配置"""
    env_file = root / ".env"
    
    config = {"genre": None, "embed_api_key": "", "rerank_api_key": ""}
    
    # 读取 state.json 获取题材
    state_file = root / ".webnovel" / "state.json"
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            # Handle nested project_info
            if "project_info" in state:
                config["genre"] = state["project_info"].get("genre")
            else:
                config["genre"] = state.get("genre")
                
        except Exception:
            pass
    
    # 读取 .env 获取 API 配置（隐藏实际值）
    if env_file.exists():
        try:
            content = env_file.read_text(encoding="utf-8")
            if "EMBED_API_KEY" in content:
                config["embed_api_key"] = "******"
            if "RERANK_API_KEY" in content:
                config["rerank_api_key"] = "******"
        except Exception:
            pass
    
    return config


@router.put("/config")
async def update_config(config: ProjectConfig, root: Path = Depends(get_project_root)):
    """更新项目配置"""
    env_file = root / ".env"
    
    # 更新 .env 文件
    env_content = ""
    if env_file.exists():
        env_content = env_file.read_text(encoding="utf-8")
    
    lines = env_content.split("\n") if env_content else []
    new_lines = []
    keys_updated = set()
    
    for line in lines:
        if line.startswith("EMBED_API_KEY=") and config.embed_api_key:
            new_lines.append(f"EMBED_API_KEY={config.embed_api_key}")
            keys_updated.add("EMBED_API_KEY")
        elif line.startswith("RERANK_API_KEY=") and config.rerank_api_key:
            new_lines.append(f"RERANK_API_KEY={config.rerank_api_key}")
            keys_updated.add("RERANK_API_KEY")
        else:
            new_lines.append(line)
    
    # 添加新的配置项
    if config.embed_api_key and "EMBED_API_KEY" not in keys_updated:
        new_lines.append(f"EMBED_API_KEY={config.embed_api_key}")
    if config.rerank_api_key and "RERANK_API_KEY" not in keys_updated:
        new_lines.append(f"RERANK_API_KEY={config.rerank_api_key}")
    
    env_file.write_text("\n".join(new_lines), encoding="utf-8")
    
    
    return {"success": True}


@router.get("/prompt-config")
async def get_prompt_config(root: Path = Depends(get_project_root)):
    """获取项目级 Prompt 配置"""
    state_file = root / ".webnovel" / "state.json"
    genre = "玄幻"
    substyle = ""

    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            info = state.get("project_info", {})
            if info:
                genre = info.get("genre") or state.get("genre") or genre
                substyle = info.get("substyle") or state.get("substyle") or ""
            else:
                genre = state.get("genre") or genre
                substyle = state.get("substyle") or ""
        except Exception:
            pass

    return get_project_prompt_config(root, genre, substyle)


@router.put("/prompt-config")
async def update_prompt_config(
    payload: ProjectPromptConfigUpdate,
    root: Path = Depends(get_project_root),
):
    """更新项目级 Prompt 配置"""
    update_project_prompt_contents(
        root,
        [{"id": item.id, "content": item.content} for item in payload.prompts],
    )
    return {"success": True}


@router.post("/prompt-config/reset")
async def reset_prompt_config(
    payload: ProjectPromptResetRequest,
    root: Path = Depends(get_project_root),
):
    """重置项目级 Prompt 配置为当前题材默认模板"""
    state_file = root / ".webnovel" / "state.json"
    genre = "玄幻"
    substyle = ""

    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            info = state.get("project_info", {})
            if info:
                genre = info.get("genre") or state.get("genre") or genre
                substyle = info.get("substyle") or state.get("substyle") or ""
            else:
                genre = state.get("genre") or genre
                substyle = state.get("substyle") or ""
        except Exception:
            pass

    reset_project_prompts(root, genre, substyle, slot_ids=payload.slot_ids)
    return get_project_prompt_config(root, genre, substyle)


class ProjectPromptPushRequest(BaseModel):
    """推送单个槽位模板到全局子风格包"""
    slot_id: str


@router.post("/prompt-config/push-global")
async def push_prompt_config_to_global(
    payload: ProjectPromptPushRequest,
    root: Path = Depends(get_project_root),
):
    """把当前项目的槽位模板回写到全局子风格包。

    只影响新项目与「恢复默认/题材切换」，不主动改动其他现有项目的快照。
    目标路径由服务端从槽位与项目题材推导，客户端不传路径。
    """
    state_file = root / ".webnovel" / "state.json"
    genre = "玄幻"
    substyle = ""

    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            info = state.get("project_info", {})
            if info:
                genre = info.get("genre") or state.get("genre") or genre
                substyle = info.get("substyle") or state.get("substyle") or ""
            else:
                genre = state.get("genre") or genre
                substyle = state.get("substyle") or ""
        except Exception:
            pass

    try:
        result = push_project_prompt_to_global(root, payload.slot_id, genre, substyle)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "slot_id": result["slot_id"],
        "target_path": result["target_path"],
        "backup_path": result["backup_path"],
        "config": get_project_prompt_config(root, genre, substyle),
    }


class ProjectInfoUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    substyle: Optional[str] = None
    description: Optional[str] = None
    target_words: Optional[int] = None


@router.put("/info")
async def update_info(info: ProjectInfoUpdate, root: Path = Depends(get_project_root)):
    """更新项目基本信息"""
    state_file = root / ".webnovel" / "state.json"
    
    if not state_file.exists():
        raise HTTPException(status_code=404, detail="项目未初始化")
        
    try:
        import json
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        # 兼容旧版和新版结构
        if "project_info" not in state:
            state["project_info"] = {
                "title": state.pop("title", ""),
                "genre": state.pop("genre", ""),
                "substyle": state.pop("substyle", ""),
                "description": state.pop("description", "")
            }

        previous_genre = canonical_genre_id(state["project_info"].get("genre") or state.get("genre") or "修仙")
        previous_substyle = canonical_substyle_id(
            previous_genre,
            state["project_info"].get("substyle") or state.get("substyle") or "",
        )

        if info.title is not None:
            state["project_info"]["title"] = info.title
        if info.genre is not None:
            normalized_genre = canonical_genre_id(info.genre)
            state["project_info"]["genre"] = normalized_genre
            state["genre"] = normalized_genre
        else:
            normalized_genre = canonical_genre_id(state["project_info"].get("genre") or state.get("genre") or "修仙")
            state["project_info"]["genre"] = normalized_genre

        if info.substyle is not None:
            normalized_substyle = canonical_substyle_id(normalized_genre, info.substyle)
            state["project_info"]["substyle"] = normalized_substyle
            state["substyle"] = normalized_substyle
        else:
            normalized_substyle = canonical_substyle_id(
                normalized_genre,
                state["project_info"].get("substyle") or state.get("substyle") or "",
            )
            state["project_info"]["substyle"] = normalized_substyle
            state["substyle"] = normalized_substyle

        if info.description is not None:
            state["project_info"]["description"] = info.description
        if info.target_words is not None:
            if info.target_words <= 0:
                raise HTTPException(status_code=400, detail="目标字数必须大于 0")
            state["project_info"]["target_words"] = info.target_words
            # 兼容旧版读取逻辑
            state["target_words"] = info.target_words

        changed_fields = []
        if normalized_genre != previous_genre:
            changed_fields.append("题材")
        if normalized_substyle != previous_substyle:
            changed_fields.append("子风格")

        should_invalidate_outline = bool(state.get("initialized"))

        preserved_custom_prompt_slots: List[str] = []
        if changed_fields:
            # 全部槽位内容都来自题材/子风格独立包（含大纲、提取、连摘模板），
            # 题材或子风格变更后必须全量同步；已自定义的槽位由
            # sync_project_prompts_for_profile_change 自动保留。
            sync_result = sync_project_prompts_for_profile_change(
                root,
                normalized_genre,
                normalized_substyle,
            )
            preserved_custom_prompt_slots = sync_result.get("preserved_customized_slots", [])
            if should_invalidate_outline:
                state["project_info"]["outline_invalidated"] = True
                state["project_info"]["outline_invalidation_reason"] = (
                    f"{'、'.join(changed_fields)}已变更，现有总纲与分卷大纲仍基于旧方向，请先重新生成总纲/卷纲。"
                )
                state["project_info"]["outline_invalidated_at"] = datetime.now().isoformat()
        else:
            ensure_project_prompts(root, normalized_genre, normalized_substyle)
            
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            
        return {
            "success": True,
            "preserved_custom_prompt_slots": preserved_custom_prompt_slots,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/init")
async def init_project(request: InitRequest, root: Path = Depends(get_project_root)):
    """初始化项目"""
    genre = canonical_genre_id(request.genre)
    substyle = canonical_substyle_id(genre, request.substyle)
    
    # 计算项目内路径
    webnovel_dir = root / ".webnovel"
    state_file = webnovel_dir / "state.json"
    
    # 创建目录结构
    dirs = [
        webnovel_dir,
        root / "正文",
        root / "大纲",
        root / "设定集",
        root / "设定集" / "角色",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    # 创建初始 state.json
    # 读取现有状态以保留标题
    current_state = {}
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                current_state = json.load(f)
        except:
            pass

    state = {
        "title": current_state.get("title", current_state.get("project_info", {}).get("title", root.name)),
        "genre": genre,
        "substyle": substyle,
        "mode": request.mode,
        "current_chapter": 0,
        "protagonist": None,
        "created_at": datetime.now().isoformat(),
        "initialized": True
    }
    
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    ensure_project_prompts(root, genre, substyle)
    
    # 创建总纲模板
    outline_file = root / "大纲" / "总纲.md"
    if not outline_file.exists():
        outline_file.write_text(f"""# 小说总纲

## 基本信息
- **题材**: {genre}
- **子风格**: {substyle}
- **预计字数**: 待定
- **核心卖点**: 待定

## 故事概要
（请在此处填写故事概要）

## 主要角色
（请在此处填写主要角色）

## 卷纲规划
- 第一卷：待定
""", encoding="utf-8")
    
    return {"success": True, "message": f"项目已初始化，题材：{genre} / {substyle}"}


@router.get("/genres")
async def get_genres():
    """获取可用题材列表"""
    return {"genres": list_supported_genres()}


@router.delete("/reset")
async def reset_project(root: Path = Depends(get_project_root)):
    """重置项目数据 - 保留基本信息与配置，清空内容与进度"""
    state_file = root / ".webnovel" / "state.json"
    
    # 1. 备份关键信息 (灵魂)
    metadata = {}
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                metadata = {
                    "genre": state.get("genre"),
                    "mode": state.get("mode"),
                    "protagonist": state.get("protagonist"),
                    "project_info": state.get("project_info"),
                    "created_at": state.get("created_at")
                }
        except Exception:
            pass

    # 2. 清空内容目录 (肉体)
    dirs_to_clean = ["正文", "大纲", "设定集"]
    for dir_name in dirs_to_clean:
        dir_path = root / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # 3. 重置状态文件 (清空进度，注入备份的灵魂)
    state_dir = root / ".webnovel"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    new_state = {
        **metadata,
        "current_chapter": 0,
        "protagonist_state": {},  # 修复：初始化为字典而非 None，防止 init_project.py 崩溃
        "initialized": False,  # 明确标记为未初始化，触发设置页
        "last_reset": datetime.now().isoformat() if "datetime" in globals() else None
    }
    
    # 兜底：如果 metadata 里没有 genre/title，尝试从当前项目名恢复
    if not new_state.get("genre"): new_state["genre"] = "修仙"
    if not new_state.get("project_info"):
        new_state["project_info"] = {"title": root.name, "genre": new_state["genre"]}

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(new_state, f, ensure_ascii=False, indent=2)

    # 4. 创建初始总纲模板
    outline_file = root / "大纲" / "总纲.md"
    outline_file.write_text(f"# 小说总纲\n\n## 基本信息\n- **题材**: {new_state['genre']}\n", encoding="utf-8")
    
    return {"success": True, "message": "项目已重置，标题与配置已保留。"}


class ProjectSwitchRequest(BaseModel):
    path: str


@router.post("/switch")
async def switch_project(request: ProjectSwitchRequest):
    """切换当前活动项目"""
    path = Path(request.path).expanduser().resolve()
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"项目路径不存在: {path}")
        
    projects_manager.set_current_project(path)
    
    # 重新加载配置
    try:
        from data_modules.config import set_project_root
        set_project_root(path)
    except:
        pass
        
    return {
        "success": True, 
        "current_project": str(path),
        "message": f"已切换到项目: {path.name}"
    }


class ProjectCreateRequest(BaseModel):
    name: str
    path: str
    genre: str = "修仙"
    substyle: str = ""


@router.post("/create")
async def create_project_api(request: ProjectCreateRequest):
    """创建新项目"""
    result = projects_manager.create_project(request.name, request.path, request.genre, request.substyle)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class ImportRequest(BaseModel):
    path: str


@router.post("/import")
async def import_project_api(request: ImportRequest):
    """导入现有项目"""
    result = projects_manager.import_project(request.path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/{project_id}")
async def delete_project_api(project_id: str, delete_files: bool = False):
    """删除项目记录"""
    result = projects_manager.delete_project(project_id, delete_files)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
