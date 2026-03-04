# Copyright (c) 2026 左岚. All rights reserved.
"""大纲管理 API"""

import re
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from services import projects_manager
from services.activity_logger import get_logger
from dependencies import get_project_root

router = APIRouter()


class OutlineItem(BaseModel):
    """大纲项"""
    id: str
    title: str
    type: str  # volume/chapter
    content: Optional[str] = None
    children: List["OutlineItem"] = []


class OutlineUpdate(BaseModel):
    """大纲更新请求"""
    content: str


# get_project_root imported from dependencies


@router.get("")
async def get_outlines(root: Path = Depends(get_project_root)):
    """获取大纲列表"""
    outline_dir = root / "大纲"
    
    if not outline_dir.exists():
        return {"outlines": [], "total_outline": None}
    
    outlines = []
    total_outline = None
    
    # 读取总纲
    total_file = outline_dir / "总纲.md"
    if total_file.exists():
        content = total_file.read_text(encoding="utf-8")
        total_outline = {"id": "total", "title": "总纲", "content": content}
    
    # 读取卷大纲（按卷号去重，保留内容更多的文件）
    seen_volumes = {}
    for f in sorted(outline_dir.glob("第*卷*.md")):
        match = re.search(r"第(\d+)卷", f.name)
        if match:
            volume = int(match.group(1))
            if volume not in seen_volumes or f.stat().st_size > seen_volumes[volume].stat().st_size:
                seen_volumes[volume] = f

    for volume in sorted(seen_volumes):
        f = seen_volumes[volume]
        content = f.read_text(encoding="utf-8")
        outlines.append({
            "id": f"volume_{volume}",
            "volume": volume,
            "title": f.stem,
            "content": content
        })
    
    return {"outlines": outlines, "total_outline": total_outline}


def parse_outline_chapters(content: str) -> List[dict]:
    """解析大纲内容中的章节列表"""
    chapters = []
    if not content:
        return chapters

    # 定义多种匹配模式（优先匹配"第X章"格式，避免误匹配普通序号列表）
    patterns = [
        # 模式0: 混合格式 (## **第1章：标题**) - 优先匹配
        re.compile(r"^\s*#{1,4}\s*(?:\*{2}|_{2})\s*第\s*(\d+)\s*章[：:]\s*(.+?)(?:\*{2}|_{2})?\s*$", re.MULTILINE),

        # 模式1: Markdown 标题 + 冒号格式 "## 第1章：标题"
        re.compile(r"^\s*#{1,4}\s*第\s*(\d+)\s*章[：:]\s*(.+?)\s*$", re.MULTILINE),
        
        # 模式2: Markdown 标题 + 书名号格式 "### 第61章《标题》"
        re.compile(r"^\s*#{1,4}\s*第\s*(\d+)\s*章《(.+?)》\s*$", re.MULTILINE),
        
        # 模式3: 列表项 + 加粗格式 "- **第121章：标题**"
        re.compile(r"^\s*[-*]\s*\*{2}第\s*(\d+)\s*章[：:]\s*([^\*]+?)\*{2}\s*$", re.MULTILINE),
        
        # 模式4: 纯加粗格式 "**第1章：标题**"
        re.compile(r"^\s*\*{2}第\s*(\d+)\s*章[：:]\s*([^\*]+?)\*{2}\s*$", re.MULTILINE),
        
        # 模式5: 纯文本格式 "第1章：标题" 或 "第1章 标题"
        re.compile(r"^\s*第\s*(\d+)\s*章[：:\s]\s*(.+?)\s*$", re.MULTILINE),
        
        # 模式6: 中文数字格式 "第一章 标题"
        re.compile(r"^\s*(?:#{1,4}\s*|\*{2})?第\s*([零一二三四五六七八九十百千万]+)\s*章[：:\s《]\s*(.+?)(?:\*{2}|》)?\s*$", re.MULTILINE),
    ]

    # Lazy import to avoid circular dependency if any
    try:
        from utils import chinese_to_arabic
    except ImportError:
        chinese_to_arabic = lambda x: 0 # Fallback

    seen_ids = set()

    for pattern in patterns:
        for m in pattern.finditer(content):
            try:
                raw_num = m.group(1)
                
                # 尝试判断是否是中文数字
                if any(c in "零一二三四五六七八九十百千万" for c in raw_num):
                    chap_num = chinese_to_arabic(raw_num)
                else:
                    chap_num = int(raw_num)
                    
                # 避免重复 (如果多种模式匹配到了同一行，或者不同模式匹配了同一个章节号)
                if chap_num in seen_ids:
                    continue
                
                chap_title = m.group(2).strip()
                # 去掉可能残留的 markdown 标记 (如 **, [], 等)
                chap_title = re.sub(r"[\*\[\]]", "", chap_title).strip()
                
                chapters.append({
                    "id": f"chapter_{chap_num}",
                    "chapter": chap_num,
                    "title": f"第{chap_num}章 {chap_title}",
                    "type": "chapter",
                    "children": []
                })
                seen_ids.add(chap_num)
            except:
                continue
    
    # 按章节号排序
    chapters.sort(key=lambda x: x["chapter"])
    return chapters


@router.get("/tree")
async def get_outline_tree(root: Path = Depends(get_project_root)):
    """获取大纲树状结构"""
    outline_dir = root / "大纲"
    
    tree = []
    
    # 读取总纲
    total_file = outline_dir / "总纲.md"
    if total_file.exists():
        tree.append({
            "id": "total",
            "title": "总纲",
            "type": "total",
            "children": []
        })
    
    # 读取卷大纲并构建树（按卷号去重，保留内容更多的文件）
    seen_volumes = {}
    for f in sorted(outline_dir.glob("第*卷*.md")):
        match = re.search(r"第(\d+)卷", f.name)
        if match:
            volume = int(match.group(1))
            if volume not in seen_volumes or f.stat().st_size > seen_volumes[volume].stat().st_size:
                seen_volumes[volume] = f

    for volume in sorted(seen_volumes):
        f = seen_volumes[volume]
        content = f.read_text(encoding="utf-8")

        # 从前10行提取卷名（文件开头可能有说明文字）
        lines = content.split('\n')[:10]
        volume_title = f"第{volume}卷"

        for line in lines:
            clean_line = re.sub(r'^[#\s]+', '', line.strip())
            if not clean_line:
                continue

            # 尝试多种卷名格式
            # 格式1: "第X卷：标题" 或 "第X卷 标题"
            m = re.search(r"第\s*[\d一二三四五六七八九十百]+\s*卷[大纲]*[：:\s]+(.+?)(?:\s*[\(（]|$)", clean_line)
            if m:
                title = m.group(1).strip()
                title = re.sub(r"[《》【】]", "", title)  # 去书名号
                title = re.sub(r"\d+章.*$", "", title).strip()  # 去章数后缀
                if title:
                    volume_title = f"第{volume}卷 {title}"
                    break

            # 格式2: "第X卷《标题》" 或 "第X卷【标题】"
            m = re.search(r"第\s*[\d一二三四五六七八九十百]+\s*卷[大纲]*[：:\s]*[《【](.+?)[》】]", clean_line)
            if m:
                title = m.group(1).strip()
                title = re.sub(r"\d+章.*$", "", title).strip()
                if title:
                    volume_title = f"第{volume}卷 {title}"
                    break

        # 解析章节
        chapters = parse_outline_chapters(content)

        tree.append({
            "id": f"volume_{volume}",
            "volume": volume,
            "title": volume_title,
            "type": "volume",
            "children": chapters
        })
    
    return {"tree": tree}


@router.get("/{volume}")
async def get_volume_outline(volume: int, root: Path = Depends(get_project_root)):
    """获取卷大纲详情"""
    outline_dir = root / "大纲"
    
    # 查找卷大纲文件
    pattern = f"第{volume}卷*.md"
    files = list(outline_dir.glob(pattern))
    
    if not files:
        raise HTTPException(status_code=404, detail=f"未找到第{volume}卷大纲")
    
    outline_file = files[0]
    content = outline_file.read_text(encoding="utf-8")
    
    # 解析章节列表
    chapters_data = parse_outline_chapters(content)
    
    # 转换为前端需要的简单格式
    chapters = []
    for c in chapters_data:
        # 去掉 "第X章 " 前缀，只保留标题，因为前端可能分别显示
        # 但这里的 title 已经是 "第X章 标题"
        # 我们可以保留原样或者做转换，这里保持原有 API返回格式: {chapter: int, title: str}
        # parse_outline_chapters 返回的 title 是完整标题
        # 我们从 title 中把纯标题提取出来? 
        # parse_outline_chapters title 格式: f"第{chap_num}章 {chap_title}"
        # 简单起见，提取出 chap_title
        clean_title = c["title"].replace(f"第{c['chapter']}章 ", "")
        chapters.append({
            "chapter": c["chapter"],
            "title": clean_title
        })
    
    return {
        "volume": volume,
        "title": outline_file.stem,
        "content": content,
        "chapters": chapters
    }


@router.put("/total")
async def update_total_outline(data: OutlineUpdate, root: Path = Depends(get_project_root)):
    """更新总纲"""
    outline_dir = root / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    
    outline_file = outline_dir / "总纲.md"
    outline_file.write_text(data.content, encoding="utf-8")
    
    # 记录活动
    logger = get_logger(root)
    if logger:
        logger.log(
            type="outline",
            action="updated",
            title="更新全书总纲"
        )
    
    return {"success": True, "path": str(outline_file)}


@router.put("/{volume}")
async def update_volume_outline(volume: int, data: OutlineUpdate, root: Path = Depends(get_project_root)):
    """更新卷大纲"""
    outline_dir = root / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    
    # 查找或创建卷大纲文件
    pattern = f"第{volume}卷*.md"
    files = list(outline_dir.glob(pattern))
    
    if files:
        outline_file = files[0]
    else:
        outline_file = outline_dir / f"第{volume}卷-详细大纲.md"
    
    outline_file.write_text(data.content, encoding="utf-8")
    
    # 记录活动
    logger = get_logger(root)
    if logger:
        logger.log(
            type="outline",
            action="updated",
            title=f"更新第{volume}卷大纲"
        )

    return {"success": True, "path": str(outline_file)}


@router.delete("/{volume}")
async def delete_volume_outline(
    volume: int,
    delete_related_characters: bool = Query(False, description="是否删除该卷自动生成角色"),
    root: Path = Depends(get_project_root)
):
    """删除卷大纲"""
    outline_dir = root / "大纲"
    if not outline_dir.exists():
        raise HTTPException(status_code=404, detail=f"未找到第{volume}卷大纲")

    pattern = f"第{volume}卷*.md"
    files = list(outline_dir.glob(pattern))

    if not files:
        raise HTTPException(status_code=404, detail=f"未找到第{volume}卷大纲")

    for f in files:
        f.unlink()

    deleted_character_files = []
    deleted_character_names = []
    roster_updated = False

    # 可选：删除该卷自动生成的角色档案（危险操作）
    if delete_related_characters:
        marker = f"档案创建于第{volume}卷大纲生成时"
        char_lib = root / "设定集" / "角色库"
        for category in ["主要角色", "次要角色", "反派角色"]:
            cat_dir = char_lib / category
            if not cat_dir.exists():
                continue
            for f in sorted(cat_dir.glob("*.md")):
                try:
                    content = f.read_text(encoding="utf-8")
                except Exception:
                    continue
                if marker in content:
                    deleted_character_files.append(str(f.relative_to(root)))
                    deleted_character_names.append(f.stem)
                    f.unlink()

        # 从活跃角色表中移除被删除角色
        if deleted_character_names:
            roster_file = char_lib / "活跃角色.md"
            if roster_file.exists():
                try:
                    lines = roster_file.read_text(encoding="utf-8").splitlines()
                    new_lines = []
                    deleted_set = set(deleted_character_names)
                    for line in lines:
                        if any(f"**{name}**" in line for name in deleted_set):
                            continue
                        new_lines.append(line)
                    if len(new_lines) != len(lines):
                        roster_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                        roster_updated = True
                except Exception:
                    pass

    logger = get_logger(root)
    if logger:
        extra = ""
        if delete_related_characters:
            extra = f"（联动删除角色 {len(deleted_character_files)} 个）"
        logger.log(
            type="outline",
            action="deleted",
            title=f"删除第{volume}卷大纲{extra}"
        )

    return {
        "success": True,
        "deleted": len(files),
        "deleted_character_count": len(deleted_character_files),
        "deleted_character_names": sorted(set(deleted_character_names)),
        "deleted_character_files": deleted_character_files,
        "roster_updated": roster_updated
    }
