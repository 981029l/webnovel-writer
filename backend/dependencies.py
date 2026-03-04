from pathlib import Path
from typing import Optional
from fastapi import Header, Query, HTTPException
from urllib.parse import unquote
import os


def get_project_root(
    project_root: Optional[str] = Query(None),
    x_project_root: Optional[str] = Header(None, alias="X-Project-Root")
) -> Path:
    """
    确定当前操作的项目根路径。
    优先级：
    1. URL 查询参数 project_root
    2. HTTP Header X-Project-Root
    3. 全局 projects_manager 记录的当前项目
    4. 报错（不再静默回退到默认路径）
    """
    # 1. 查询参数
    if project_root:
        result = Path(project_root).resolve()
        return result

    # 2. Header 参数
    if x_project_root:
        if x_project_root.lower() not in ["null", "undefined", "none"]:
            try:
                decoded = unquote(x_project_root)
                path = Path(decoded).resolve()
                if path.exists():
                    return path
            except Exception:
                pass

    # 3. 后端全局状态
    try:
        from services import projects_manager
        current = projects_manager.get_current_project_path()

        if current and current.exists():
            return current
    except ImportError:
        pass

    # 4. 报错，要求前端传递项目路径
    raise HTTPException(
        status_code=400,
        detail="未指定项目路径。请先在首页选择一个项目。"
    )
