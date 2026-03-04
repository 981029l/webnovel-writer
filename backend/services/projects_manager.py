# Copyright (c) 2026 左岚. All rights reserved.
# projects_manager.py - 多项目管理服务
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# 全局配置目录
GLOBAL_CONFIG_DIR = Path.home() / ".webnovel"
PROJECTS_FILE = GLOBAL_CONFIG_DIR / "projects.json"

def _ensure_config_dir():
    """确保全局配置目录存在"""
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def _load_projects_data() -> Dict[str, Any]:
    """加载项目列表数据"""
    _ensure_config_dir()
    data = {"current_project": None, "projects": []}
    
    if PROJECTS_FILE.exists():
        try:
            data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    # 自动发现根目录项目 (兼容旧版本) - 仅当没有任何项目时
    if not data["projects"]:
        # 注意：此处不应盲目将根目录设为项目，除非它确实包含正文/大纲目录
        root_path = Path(__file__).parent.parent.parent
        if (root_path / "大纲").exists() or (root_path / "正文").exists():
            state_file = root_path / ".webnovel" / "state.json"
            # ... (rest of the discovery logic remains similar but limited)
            try:
                if state_file.exists():
                    state = json.loads(state_file.read_text(encoding="utf-8"))
                    name = state.get("project_info", {}).get("title", state.get("title", "默认项目"))
                else:
                    name = "默认项目"
            except Exception:
                name = "默认项目"
            
            default_project = {
                "id": str(uuid.uuid4()),
                "name": name,
                "path": str(root_path.absolute()),
                "genre": "未知",
                "created_at": datetime.now().strftime("%Y-%m-%d"),
                "last_opened": datetime.now().strftime("%Y-%m-%d"),
                "exists": True
            }
            data["projects"].append(default_project)
            if not data["current_project"]:
                data["current_project"] = default_project["path"]
            _save_projects_data(data)
            
    return data

def find_project_by_path(path: Path) -> Optional[Dict[str, Any]]:
    """根据路径回溯查找所属项目"""
    data = _load_projects_data()
    path = path.expanduser().resolve()
    
    # 尝试匹配路径或其父目录
    best_match = None
    max_len = -1
    
    for p in data.get("projects", []):
        p_path = Path(p["path"]).expanduser().resolve()
        try:
            if path == p_path or p_path in path.parents:
                # 选取最长匹配路径（最具体的子项目）
                if len(str(p_path)) > max_len:
                    max_len = len(str(p_path))
                    best_match = p
        except ValueError:
            continue
            
    return best_match

def _save_projects_data(data: Dict[str, Any]):
    """保存项目列表数据"""
    _ensure_config_dir()
    PROJECTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def list_projects() -> List[Dict[str, Any]]:
    """获取所有项目列表（并同步最新标题、章节数、字数）"""
    data = _load_projects_data()
    projects = data.get("projects", [])
    updated = False

    # 检查项目路径是否存在，并同步标题
    for p in projects:
        p_path = Path(p["path"])
        p["exists"] = p_path.exists()

        if p["exists"]:
            # 尝试读取最新的 state.json
            state_file = p_path / ".webnovel" / "state.json"
            if state_file.exists():
                try:
                    state = json.loads(state_file.read_text(encoding="utf-8"))
                    # 获取最新标题
                    new_title = ""
                    if "project_info" in state:
                        new_title = state["project_info"].get("title", "")
                    else:
                        new_title = state.get("title", "")

                    # 如果标题不一致，更新缓存
                    if new_title and new_title != p["name"]:
                        p["name"] = new_title
                        updated = True
                except Exception:
                    pass

            # 统计章节数和总字数
            chapters_dir = p_path / "正文"
            if chapters_dir.exists():
                try:
                    chapter_files = list(chapters_dir.glob("第*章*.md"))
                    p["total_chapters"] = len(chapter_files)
                    total_words = 0
                    for f in chapter_files:
                        try:
                            total_words += len(f.read_text(encoding="utf-8"))
                        except Exception:
                            pass
                    p["total_words"] = total_words
                except Exception:
                    p["total_chapters"] = 0
                    p["total_words"] = 0
            else:
                p["total_chapters"] = 0
                p["total_words"] = 0
        else:
            p["total_chapters"] = 0
            p["total_words"] = 0

    # 如果有更新，保存回 projects.json
    if updated:
        _save_projects_data(data)

    return projects

def get_current_project() -> Optional[Dict[str, Any]]:
    """获取当前项目"""
    data = _load_projects_data()
    current_path = data.get("current_project")
    if not current_path:
        return None
    for p in data.get("projects", []):
        if p["path"] == current_path:
            p["exists"] = Path(p["path"]).exists()
            return p
    return None

def set_current_project(path: Path):
    """设置当前项目路径"""
    data = _load_projects_data()
    abs_path = str(path.expanduser().resolve())
    
    # 确保保存为绝对路径
    data["current_project"] = abs_path
    
    # 更新最后打开时间
    for p in data["projects"]:
        if str(Path(p["path"]).expanduser().resolve()) == abs_path:
            p["last_opened"] = datetime.now().strftime("%Y-%m-%d")
            break
            
    _save_projects_data(data)


def get_current_project_path() -> Optional[Path]:
    """获取当前项目路径"""
    project = get_current_project()
    if project and project.get("exists"):
        return Path(project["path"])
    return None

def create_project(name: str, path: str, genre: str = "修仙") -> Dict[str, Any]:
    """新建项目"""
    project_path = Path(path).expanduser().resolve()
    project_path.mkdir(parents=True, exist_ok=True)
    
    # 创建项目基础目录结构
    (project_path / "大纲").mkdir(exist_ok=True)
    (project_path / "正文").mkdir(exist_ok=True)
    (project_path / "设定集").mkdir(exist_ok=True)
    (project_path / ".webnovel").mkdir(exist_ok=True)
    
    # 初始化 state.json
    state_file = project_path / ".webnovel" / "state.json"
    state = {
        "title": name, 
        "genre": genre, 
        "created_at": datetime.now().isoformat(),
        "initialized": False  # 新建项目默认未初始化，需通过 AI Init 完成
    }
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # 添加到项目列表
    data = _load_projects_data()
    project = {
        "id": str(uuid.uuid4()),
        "name": name,
        "path": str(project_path),
        "genre": genre,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "last_opened": datetime.now().strftime("%Y-%m-%d")
    }
    
    # 检查是否已存在
    for p in data["projects"]:
        if Path(p["path"]).expanduser().resolve() == project_path:
            return {"error": "项目路径已存在", "project": p}
    
    data["projects"].append(project)
    data["current_project"] = project["path"]
    _save_projects_data(data)
    
    return {"success": True, "project": project}

def switch_project(project_id: str) -> Dict[str, Any]:
    """切换当前项目"""
    data = _load_projects_data()
    for p in data["projects"]:
        if p["id"] == project_id:
            if not Path(p["path"]).expanduser().exists():
                return {"error": "项目路径不存在", "path": p["path"]}
            data["current_project"] = p["path"]
            p["last_opened"] = datetime.now().strftime("%Y-%m-%d")
            _save_projects_data(data)
            return {"success": True, "project": p}
    return {"error": "项目不存在"}

def import_project(path: str) -> Dict[str, Any]:
    """导入现有项目"""
    project_path = Path(path).expanduser().resolve()
    if not project_path.exists():
        return {"error": "路径不存在"}
    
    # 尝试读取项目信息
    state_file = project_path / ".webnovel" / "state.json"
    name = project_path.name
    genre = "未知"
    
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            name = state.get("title", name)
            genre = state.get("genre", genre)
        except Exception:
            pass
    
    data = _load_projects_data()
    
    # 检查是否已存在
    for p in data["projects"]:
        if p["path"] == str(project_path.absolute()):
            data["current_project"] = p["path"]
            _save_projects_data(data)
            return {"success": True, "project": p, "already_exists": True}
    
    # 新增
    project = {
        "id": str(uuid.uuid4()),
        "name": name,
        "path": str(project_path.absolute()),
        "genre": genre,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "last_opened": datetime.now().strftime("%Y-%m-%d")
    }
    data["projects"].append(project)
    data["current_project"] = project["path"]
    _save_projects_data(data)
    
    return {"success": True, "project": project}

def delete_project(project_id: str, delete_files: bool = False) -> Dict[str, Any]:
    """删除项目（从索引移除，可选删除文件）"""
    data = _load_projects_data()
    for i, p in enumerate(data["projects"]):
        if p["id"] == project_id:
            removed = data["projects"].pop(i)
            if data["current_project"] == removed["path"]:
                data["current_project"] = data["projects"][0]["path"] if data["projects"] else None
            _save_projects_data(data)
            
            if delete_files:
                import shutil
                try:
                    shutil.rmtree(removed["path"])
                except Exception as e:
                    return {"success": True, "warning": f"文件删除失败: {e}"}
            
            return {"success": True}
    return {"error": "项目不存在"}
