from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from dependencies import get_project_root

router = APIRouter()

def get_index_manager(project_root: Path):
    """获取 IndexManager 实例"""
    try:
        from data_modules.config import DataModulesConfig
        from data_modules.index_manager import IndexManager
        config = DataModulesConfig.from_project_root(project_root)
        return IndexManager(config)
    except Exception as e:
        return None


@router.get("")
async def get_entities(
    entity_type: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    root: Path = Depends(get_project_root)
):
    """获取实体列表"""
    manager = get_index_manager(root)
    
    if not manager:
        return {"entities": [], "error": "索引管理器未初始化"}
    
    try:
        if entity_type:
            entities = manager.get_entities_by_type(entity_type)
        elif tier:
            entities = manager.get_entities_by_tier(tier)
        else:
            # 获取所有核心实体
            entities = manager.get_core_entities()
        
        return {"entities": entities}
    except Exception as e:
        return {"entities": [], "error": str(e)}


@router.get("/types")
async def get_entity_types():
    """获取实体类型列表"""
    return {
        "types": [
            {"id": "character", "name": "角色", "icon": "👤"},
            {"id": "location", "name": "地点", "icon": "📍"},
            {"id": "item", "name": "物品", "icon": "🎁"},
            {"id": "skill", "name": "招式/技能", "icon": "⚔️"},
            {"id": "faction", "name": "势力", "icon": "🏰"},
            {"id": "foreshadowing", "name": "伏笔", "icon": "🔮"},
        ]
    }


@router.get("/tiers")
async def get_entity_tiers():
    """获取实体重要度列表"""
    return {
        "tiers": [
            {"id": "core", "name": "核心", "color": "#FF4444"},
            {"id": "major", "name": "重要", "color": "#FF8800"},
            {"id": "minor", "name": "次要", "color": "#44AA44"},
            {"id": "decor", "name": "装饰", "color": "#888888"},
        ]
    }


@router.get("/type/{entity_type}")
async def get_entities_by_type(entity_type: str, root: Path = Depends(get_project_root)):
    """按类型获取实体"""
    manager = get_index_manager(root)

    if not manager:
        return {"entities": [], "error": "索引管理器未初始化"}

    try:
        entities = manager.get_entities_by_type(entity_type)
        return {"entities": entities, "type": entity_type}
    except Exception as e:
        return {"entities": [], "error": str(e)}


@router.get("/search")
async def search_entities(
    q: str = Query(..., description="搜索关键词"),
    root: Path = Depends(get_project_root)
):
    """搜索实体"""
    manager = get_index_manager(root)

    if not manager:
        return {"results": [], "error": "索引管理器未初始化"}

    try:
        # 搜索实体（按名称/别名匹配）
        results = manager.search_entities(q)
        return {"results": results, "query": q}
    except AttributeError:
        # 如果 search_entities 方法不存在，返回空结果
        return {"results": [], "query": q, "error": "搜索功能未实现"}
    except Exception as e:
        return {"results": [], "error": str(e)}


@router.get("/protagonist")
async def get_protagonist(root: Path = Depends(get_project_root)):
    """获取主角信息"""
    manager = get_index_manager(root)

    if not manager:
        return {"protagonist": None, "error": "索引管理器未初始化"}

    try:
        protagonist = manager.get_protagonist()
        return {"protagonist": protagonist}
    except Exception as e:
        return {"protagonist": None, "error": str(e)}


@router.get("/characters")
async def get_characters(root: Path = Depends(get_project_root)):
    """获取角色列表"""
    # 尝试从 IndexManager 获取
    manager = get_index_manager(root)
    if manager:
        try:
            entities = manager.get_entities_by_type("character")
            return {"characters": entities}
        except Exception:
            pass

    # 回退：从设定集/角色目录读取
    characters_dir = root / "设定集" / "角色"
    characters = []

    if characters_dir.exists():
        for f in characters_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            characters.append({
                "id": f.stem,
                "name": f.stem,
                "content": content
            })

    return {"characters": characters}


@router.get("/foreshadowing")
async def get_foreshadowing(
    status: Optional[str] = Query(None, description="pending/resolved"),
    root: Path = Depends(get_project_root)
):
    """获取伏笔列表"""
    manager = get_index_manager(root)

    if not manager:
        return {"foreshadowing": [], "error": "索引管理器未初始化"}

    try:
        entities = manager.get_entities_by_type("foreshadowing")

        # 按状态过滤
        if status:
            entities = [e for e in entities if e.get("current", {}).get("status") == status]

        return {"foreshadowing": entities}
    except Exception as e:
        return {"foreshadowing": [], "error": str(e)}


@router.get("/{entity_id}")
async def get_entity(entity_id: str, root: Path = Depends(get_project_root)):
    """获取实体详情（必须放在所有固定路径之后）"""
    manager = get_index_manager(root)

    if not manager:
        raise HTTPException(status_code=500, detail="索引管理器未初始化")

    try:
        entity = manager.get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"未找到实体: {entity_id}")

        # 获取出场记录
        appearances = manager.get_entity_appearances(entity_id, limit=20)

        return {"entity": entity, "appearances": appearances}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
