 
"""角色管理 API - 查看和编辑角色库中的角色文件"""

import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from .projects import get_project_root

router = APIRouter(prefix="/api/characters", tags=["characters"])

class CharacterUpdate(BaseModel):
    content: str


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def _strip_bracket_alias(value: str) -> str:
    return re.sub(r"[（(].*?[）)]", "", value or "").strip()


def _extract_markdown_field(content: str, label: str) -> str:
    """提取 markdown 字段值，兼容 `- **字段**：值` / `字段: 值`。"""
    if not content:
        return ""
    pattern = rf"(?:^|\n)\s*(?:-\s*)?(?:\*{{0,2}})?{re.escape(label)}(?:\*{{0,2}})?\s*[：:]\s*(.+)"
    m = re.search(pattern, content, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _extract_protagonist_name(root: Path, settings_dir: Path) -> str:
    """从 state.json / 主角卡中解析主角名。"""
    state_file = root / ".webnovel" / "state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            for key in ["protagonist_state", "protagonist"]:
                section = state.get(key)
                if isinstance(section, dict):
                    name = (section.get("name") or "").strip()
                    if name:
                        return name
        except Exception:
            pass

    card_file = settings_dir / "主角卡.md"
    if not card_file.exists():
        return ""
    text = card_file.read_text(encoding="utf-8")

    patterns = [
        r"^>\s*主角[：:]\s*([^｜|\n]+)",
        r"\*?\*?姓名\*?\*?[：:]\s*([^\s（(]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.MULTILINE)
        if not m:
            continue
        name = (m.group(1) or "").strip()
        if name and "待填写" not in name and "待定" not in name:
            return name
    return ""


@router.get("")
async def list_characters(root: Path = Depends(get_project_root)):
    """获取世界观设定库列表（角色/宝物/功法/势力/地点）"""
    settings_dir = root / "设定集"
    char_lib = settings_dir / "角色库"
    
    result = {
        "实时状态": None,
        "主角卡": None,
        "主要角色": [],
        "次要角色": [],
        "反派角色": [],
        "活跃角色表": None,
        "宝物库": [],
        "功法库": [],
        "势力库": [],
        "地点库": []
    }
    
    # 读取实时状态文件
    status_file = settings_dir / "实时状态.md"
    if status_file.exists():
        result["实时状态"] = {
            "name": "实时状态",
            "path": str(status_file.relative_to(root)),
            "size": status_file.stat().st_size
        }

    # 读取主角卡
    protagonist_file = settings_dir / "主角卡.md"
    if protagonist_file.exists():
        result["主角卡"] = {
            "name": "主角卡",
            "path": str(protagonist_file.relative_to(root)),
            "size": protagonist_file.stat().st_size
        }
    
    # 读取角色库
    if char_lib.exists():
        # 读取活跃角色表
        roster_file = char_lib / "活跃角色.md"
        if roster_file.exists():
            result["活跃角色表"] = {
                "name": "活跃角色",
                "path": str(roster_file.relative_to(root)),
                "size": roster_file.stat().st_size
            }
        
        # 读取各角色分类目录
        for category in ["主要角色", "次要角色", "反派角色"]:
            cat_dir = char_lib / category
            if cat_dir.exists():
                for f in sorted(cat_dir.glob("*.md")):
                    result[category].append({
                        "name": f.stem,
                        "path": str(f.relative_to(root)),
                        "size": f.stat().st_size
                    })
    
    # 读取其他设定库（兼容旧目录“物品库”）
    lib_mapping = {
        "宝物库": ["宝物库", "物品库"],
        "功法库": ["功法库"],
        "势力库": ["势力库"],
        "地点库": ["地点库"],
    }
    for logical_name, dir_candidates in lib_mapping.items():
        seen = set()
        for dir_name in dir_candidates:
            lib_dir = settings_dir / dir_name
            if not lib_dir.exists():
                continue
            for f in sorted(lib_dir.glob("*.md")):
                key = str(f.resolve())
                if key in seen:
                    continue
                seen.add(key)
                result[logical_name].append({
                    "name": f.stem,
                    "path": str(f.relative_to(root)),
                    "size": f.stat().st_size
                })
    
    total = sum(len(v) for _, v in result.items() if isinstance(v, list))
    total += sum(1 for k in ["实时状态", "主角卡", "活跃角色表"] if result.get(k))
    return {"categories": result, "total": total}

@router.get("/file")
async def get_character_file(path: str, root: Path = Depends(get_project_root)):
    """读取角色文件内容"""
    file_path = root / path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    if not str(file_path).startswith(str(root / "设定集")):
        raise HTTPException(status_code=403, detail="无权访问此文件")
    
    return {
        "name": file_path.stem,
        "path": path,
        "content": file_path.read_text(encoding="utf-8")
    }

@router.put("/file")
async def update_character_file(path: str, data: CharacterUpdate, root: Path = Depends(get_project_root)):
    """更新角色文件内容"""
    file_path = root / path
    
    if not str(file_path).startswith(str(root / "设定集")):
        raise HTTPException(status_code=403, detail="无权修改此文件")
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(data.content, encoding="utf-8")
    
    return {"success": True, "path": path}

@router.post("/create")
async def create_character(
    name: str,
    category: str = "次要角色",
    root: Path = Depends(get_project_root)
):
    """创建新角色文件"""
    if category not in ["主要角色", "次要角色", "反派角色"]:
        raise HTTPException(status_code=400, detail="无效的分类")
    
    char_dir = root / "设定集" / "角色库" / category
    char_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = char_dir / f"{name}.md"
    if file_path.exists():
        raise HTTPException(status_code=400, detail="角色已存在")
    
    template = f"""# {name}

## 基本信息
- **身份**：待填写
- **首次出场**：第?章
- **当前境界**：未知
- **当前状态**：存活
- **当前地点**：未知
- **最后更新章节**：第?章

## 与主角关系
待补充

## 外貌描写
待补充

## 性格特点
待补充

## 关键事件时间线
- 第?章：初次登场

---
*手动创建*
"""
    file_path.write_text(template, encoding="utf-8")
    
    return {
        "success": True,
        "path": str(file_path.relative_to(root)),
        "name": name
    }

@router.get("/profile")
async def get_character_profile(name: str, root: Path = Depends(get_project_root)):
    """获取角色详细档案，包括关联的宝物、势力、功法"""
    settings_dir = root / "设定集"
    char_lib = settings_dir / "角色库"
    protagonist_name = _extract_protagonist_name(root, settings_dir)

    # 1. 找到角色文件并读取内容（精确 + 容错匹配）
    char_content = None
    char_category = None
    resolved_name = name
    category_dirs = ["主要角色", "次要角色", "反派角色"]

    # 精确匹配
    for category in category_dirs:
        f = char_lib / category / f"{name}.md"
        if f.exists():
            char_content = f.read_text(encoding="utf-8")
            char_category = category
            resolved_name = f.stem
            break

    # 容错匹配：处理空格/括号别名等不一致
    if char_content is None and char_lib.exists():
        request_norm = _normalize_name(name)
        request_alias = _strip_bracket_alias(request_norm)
        best = None
        best_score = -1

        for category in category_dirs:
            cat_dir = char_lib / category
            if not cat_dir.exists():
                continue
            for f in cat_dir.glob("*.md"):
                stem = f.stem
                stem_norm = _normalize_name(stem)
                stem_alias = _strip_bracket_alias(stem_norm)

                score = 0
                if stem_norm == request_norm:
                    score = 100
                elif stem_alias and request_alias and stem_alias == request_alias:
                    score = 95
                elif stem_alias and request_norm and stem_alias == request_norm:
                    score = 90
                elif request_alias and stem_norm and request_alias == stem_norm:
                    score = 88
                elif request_alias and stem_alias and (request_alias in stem_alias or stem_alias in request_alias):
                    score = 70
                elif request_norm and stem_norm and (request_norm in stem_norm or stem_norm in request_norm):
                    score = 60

                if score > best_score:
                    best_score = score
                    best = (f, category, stem)

        if best is not None and best_score >= 70:
            f, category, stem = best
            char_content = f.read_text(encoding="utf-8")
            char_category = category
            resolved_name = stem

    # 主角兜底：若未建独立档案，但请求命中主角名，则回退到主角卡
    if char_content is None:
        card_file = settings_dir / "主角卡.md"
        if card_file.exists():
            request_alias = _strip_bracket_alias(_normalize_name(name))
            protagonist_alias = _strip_bracket_alias(_normalize_name(protagonist_name))
            if (
                request_alias in {"主角", "男主", "女主"}
                or (request_alias and protagonist_alias and request_alias == protagonist_alias)
            ):
                char_content = card_file.read_text(encoding="utf-8")
                char_category = "主角卡"
                resolved_name = protagonist_name or name

    # 2. 扫描宝物库，找持有者包含该角色名的宝物
    treasures = []
    treasure_dir = settings_dir / "宝物库"
    if not treasure_dir.exists():
        treasure_dir = settings_dir / "物品库"
    if treasure_dir.exists():
        for f in sorted(treasure_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            # 检查持有者字段或内容中提到该角色
            if re.search(rf'持有者[：:]\s*.*{re.escape(resolved_name)}', content) or \
               (resolved_name in content and len(resolved_name) >= 2):
                desc_match = re.search(r'##\s*效果[/／]?用途?\s*\n+(.+?)(?:\n\n|\n##|\Z)', content, re.DOTALL)
                treasures.append({
                    "name": f.stem,
                    "desc": desc_match.group(1).strip()[:60] if desc_match else "",
                })

    # 3. 扫描势力库
    factions = []
    faction_dir = settings_dir / "势力库"
    if faction_dir.exists():
        for f in sorted(faction_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            if resolved_name in content and len(resolved_name) >= 2:
                desc_match = re.search(r'##\s*设定描述\s*\n+(.+?)(?:\n\n|\n##|\Z)', content, re.DOTALL)
                factions.append({
                    "name": f.stem,
                    "desc": desc_match.group(1).strip()[:60] if desc_match else "",
                })

    # 4. 扫描功法库
    techniques = []
    technique_dir = settings_dir / "功法库"
    if technique_dir.exists():
        for f in sorted(technique_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            if re.search(rf'(?:\*{{0,2}})?修炼者(?:\*{{0,2}})?[：:]\s*.*{re.escape(resolved_name)}', content) or \
               (resolved_name in content and len(resolved_name) >= 2):
                desc_match = re.search(r'##\s*效果[/／]?特点?\s*\n+(.+?)(?:\n\n|\n##|\Z)', content, re.DOTALL)
                techniques.append({
                    "name": f.stem,
                    "desc": desc_match.group(1).strip()[:60] if desc_match else "",
                })

    # 5. 提取角色基本信息
    realm_text = _extract_markdown_field(char_content or "", "当前境界")
    status_text = _extract_markdown_field(char_content or "", "当前状态")
    location_text = _extract_markdown_field(char_content or "", "当前地点")
    last_update_text = _extract_markdown_field(char_content or "", "最后更新章节")
    identity_text = _extract_markdown_field(char_content or "", "身份")
    first_appear_text = _extract_markdown_field(char_content or "", "首次出场") or _extract_markdown_field(char_content or "", "首次出现")

    return {
        "name": resolved_name,
        "queryName": name,
        "category": char_category or "未归档",
        "content": char_content or "",
        "realm": realm_text,
        "status": status_text if status_text else ("主角" if char_category == "主角卡" else ("未建档" if char_content is None else "未知")),
        "location": location_text,
        "lastUpdateChapter": last_update_text,
        "identity": identity_text,
        "firstAppear": first_appear_text,
        "treasures": treasures,
        "factions": factions,
        "techniques": techniques,
        "missing": char_content is None,
    }


@router.get("/relationships")
async def get_relationships(root: Path = Depends(get_project_root)):
    """提取角色关系图谱数据"""
    settings_dir = root / "设定集"
    char_lib = settings_dir / "角色库"

    nodes = []
    edges = []
    node_names = set()
    node_map = {}  # name -> node index

    if not char_lib.exists():
        return {"nodes": [], "edges": []}

    # 1. 收集所有角色节点（从分类目录）
    categories = {
        "主要角色": {"color": "#e74c3c", "size": 50},
        "次要角色": {"color": "#3498db", "size": 30},
        "反派角色": {"color": "#8e44ad", "size": 40},
    }

    char_data = []  # (name, category, content, path)

    for category, style in categories.items():
        cat_dir = char_lib / category
        if not cat_dir.exists():
            continue
        for f in sorted(cat_dir.glob("*.md")):
            name = f.stem
            if name in node_names:
                continue
            content = f.read_text(encoding="utf-8")
            node_names.add(name)
            idx = len(nodes)
            node_map[name] = idx

            # 检测角色是否死亡
            dead = False
            status_text = _extract_markdown_field(content, "当前状态")
            if status_text:
                if any(kw in status_text for kw in ['死亡', '已死', '身亡', '阵亡', '被杀', '殒命', '亡故']):
                    dead = True

            nodes.append({
                "id": idx,
                "name": name,
                "category": category,
                "symbolSize": style["size"],
                "itemStyle": {"color": style["color"]},
                "value": category,
                "dead": dead,
            })
            char_data.append((name, category, content))

    # 2. 提取主角（优先 state/主角卡）
    protagonist_name = _extract_protagonist_name(root, settings_dir)
    protagonist_key = _strip_bracket_alias(_normalize_name(protagonist_name))
    if protagonist_key:
        for existing_name in node_names:
            if _strip_bracket_alias(_normalize_name(existing_name)) == protagonist_key:
                protagonist_name = existing_name
                break

    # 主角没有独立档案时，补一个虚拟节点，保证关系可视化不丢主角
    if protagonist_name and protagonist_name not in node_map:
        idx = len(nodes)
        node_map[protagonist_name] = idx
        node_names.add(protagonist_name)
        nodes.append({
            "id": idx,
            "name": protagonist_name,
            "category": "主要角色",
            "symbolSize": 50,
            "itemStyle": {"color": "#e74c3c"},
            "value": "主要角色",
            "dead": False,
        })

    # 如果仍没有找到，用第一个主要角色兜底
    if not protagonist_name:
        for name, category, content in char_data:
            if category == "主要角色":
                protagonist_name = name
                break

    # 3. 提取关系边
    edge_set = set()  # 避免重复边

    for name, category, content in char_data:
        if name == protagonist_name:
            continue

        # 提取 "与主角关系" 字段
        rel_match = re.search(r'##\s*与主角关系\s*\n+(.+?)(?:\n\n|\n##|\Z)', content, re.DOTALL)
        if rel_match and protagonist_name and protagonist_name in node_map:
            rel_text = rel_match.group(1).strip()
            if rel_text and rel_text != "待补充" and rel_text != "待填写":
                # 截取关系标签（不超过15字）
                rel_label = rel_text.split('\n')[0].strip('- ').strip()
                if len(rel_label) > 15:
                    rel_label = rel_label[:15] + "…"

                source = node_map.get(name)
                target = node_map.get(protagonist_name)
                if source is not None and target is not None:
                    edge_key = tuple(sorted([source, target]))
                    if edge_key not in edge_set:
                        edge_set.add(edge_key)
                        edges.append({
                            "source": source,
                            "target": target,
                            "label": rel_label,
                        })

        # 在描述中查找其他角色名的引用
        for other_name in node_names:
            if other_name == name or len(other_name) < 2:
                continue
            if other_name in content:
                source = node_map.get(name)
                target = node_map.get(other_name)
                if source is not None and target is not None:
                    edge_key = tuple(sorted([source, target]))
                    if edge_key not in edge_set:
                        edge_set.add(edge_key)
                        # 尝试从上下文提取关系描述
                        ctx_match = re.search(
                            rf'(?:与|和|跟)?{re.escape(other_name)}(?:的)?(.{{2,8}}?)(?:[，。；\n])',
                            content
                        )
                        label = ctx_match.group(1).strip() if ctx_match else "相关"
                        if len(label) > 10:
                            label = "相关"
                        edges.append({
                            "source": source,
                            "target": target,
                            "label": label,
                        })

    return {
        "nodes": nodes,
        "edges": edges,
        "protagonist": protagonist_name,
        "stats": {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
        }
    }


@router.delete("/file")
async def delete_character(path: str, root: Path = Depends(get_project_root)):
    """删除角色文件"""
    file_path = root / path
    
    if not str(file_path).startswith(str(root / "设定集")):
        raise HTTPException(status_code=403, detail="无权删除此文件")
    
    if "活跃角色.md" in path:
        raise HTTPException(status_code=403, detail="不能删除活跃角色表")
    if path.endswith("主角卡.md"):
        raise HTTPException(status_code=403, detail="不能删除主角卡")
    if path.endswith("实时状态.md"):
        raise HTTPException(status_code=403, detail="不能删除实时状态")
    
    if file_path.exists():
        file_path.unlink()
        return {"success": True}
    
    raise HTTPException(status_code=404, detail="文件不存在")
