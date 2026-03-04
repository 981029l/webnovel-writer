# Copyright (c) 2026 左岚. All rights reserved.
# activity_logger.py - 活动记录服务
import json
import uuid
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

class ActivityLogger:
    """项目活动记录器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.activity_file = project_root / ".webnovel" / "activities.json"
        self.max_activities = 50

    def log(self, type: str, action: str, title: str, details: Optional[Dict] = None):
        """记录一条活动"""
        try:
            activities = self.get_activities()
            
            activity = {
                "id": str(uuid.uuid4()),
                "type": type, # write, outline, entity, ai, project
                "action": action, # created, updated, deleted, generated
                "title": title,
                "timestamp": int(time.time()),
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                "details": details or {}
            }
            
            activities.insert(0, activity)
            activities = activities[:self.max_activities]
            
            # 确保目录存在
            self.activity_file.parent.mkdir(parents=True, exist_ok=True)
            self.activity_file.write_text(json.dumps(activities, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as e:
            print(f"Failed to log activity: {e}")
            return False

    def get_activities(self) -> List[Dict[str, Any]]:
        """获取所有活动记录"""
        if not self.activity_file.exists():
            return []
        try:
            return json.loads(self.activity_file.read_text(encoding="utf-8"))
        except Exception:
            return []

# 全局辅助函数
def get_logger(project_root: Optional[Path]) -> Optional[ActivityLogger]:
    if not project_root:
        from services.projects_manager import get_current_project_path
        project_root = get_current_project_path()
    
    if project_root:
        return ActivityLogger(project_root)
    return None
