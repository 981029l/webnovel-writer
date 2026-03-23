"""番茄小说自动上传 API（多账号版）"""

import json
import re
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from dependencies import get_project_root
from services import fanqie_publisher

router = APIRouter()

_env_cache = None


class FanqieConfigUpdate(BaseModel):
    book_name: str
    account_name: Optional[str] = None


class FanqiePublishRequest(BaseModel):
    chapter_ids: List[int]


class LoginRequest(BaseModel):
    account_name: str = "默认账号"


@router.get("/status")
async def get_status(root: Path = Depends(get_project_root)):
    global _env_cache
    if _env_cache is None or not _env_cache.get("ready"):
        _env_cache = fanqie_publisher.check_environment()

    login_status = fanqie_publisher.check_login_status()
    config = fanqie_publisher._load_fanqie_config(root)
    return {
        "env_ready": _env_cache["ready"],
        "env_error": _env_cache.get("error"),
        "env_fix_commands": _env_cache.get("fix_commands", []),
        "accounts": login_status["accounts"],
        "book_name": config.get("book_name"),
        "account_name": config.get("account_name", ""),
        "published_chapters": config.get("published_chapters", []),
    }


@router.post("/login")
async def start_login(data: LoginRequest):
    result = fanqie_publisher.start_login_background(data.account_name)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result


@router.get("/login/poll")
async def poll_login():
    return fanqie_publisher.get_login_poll()


@router.post("/login/close")
async def close_login_browser():
    return fanqie_publisher.close_login_browser()


@router.post("/logout")
async def do_logout(data: LoginRequest):
    return fanqie_publisher.logout(data.account_name)


@router.get("/verify")
async def verify_accounts(account_name: str = Query(None)):
    """验证账号 cookie 有效性"""
    try:
        if account_name:
            result = await fanqie_publisher.verify_account(account_name)
            return {"results": [result]}
        else:
            results = await fanqie_publisher.verify_all_accounts()
            return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browsers")
async def get_browser_sessions():
    """获取活跃的浏览器会话"""
    return {"sessions": fanqie_publisher.get_browser_sessions()}


@router.get("/debug/screenshot")
async def debug_screenshot(account_name: str = Query("默认账号")):
    """截图番茄后台用于调试"""
    try:
        return await fanqie_publisher.debug_screenshot(account_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browsers/close-all")
async def close_all_browsers():
    """关闭所有浏览器会话"""
    return fanqie_publisher.close_all_browsers()


@router.get("/books")
async def get_books(account_name: str = Query("默认账号")):
    try:
        books = await fanqie_publisher.list_books(account_name)
        return {"books": books}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(data: FanqieConfigUpdate, root: Path = Depends(get_project_root)):
    config = fanqie_publisher._load_fanqie_config(root)
    config["book_name"] = data.book_name
    if data.account_name is not None:
        config["account_name"] = data.account_name
    fanqie_publisher._save_fanqie_config(root, config)
    return {"success": True}


@router.get("/chapters")
async def get_chapters(root: Path = Depends(get_project_root)):
    chapters_dir = root / "正文"
    if not chapters_dir.exists():
        return {"chapters": []}

    config = fanqie_publisher._load_fanqie_config(root)
    published = set(config.get("published_chapters", []))

    chapters = []
    for f in sorted(chapters_dir.glob("*.md")):
        m = re.search(r"第(\d+)章[：:\-\s]*(.*)", f.stem)
        if not m:
            continue
        cid = int(m.group(1))
        title = m.group(2).strip() or ""
        content = f.read_text(encoding="utf-8")
        body = re.sub(r'^#.*$', '', content, flags=re.MULTILINE)
        body = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)
        chapters.append({"id": cid, "title": title, "word_count": len(body.strip()), "published": cid in published})

    chapters.sort(key=lambda c: c["id"])
    return {"chapters": chapters}


@router.post("/chapters/sync")
async def sync_chapters(root: Path = Depends(get_project_root)):
    """从番茄后台同步章节发布状态"""
    config = fanqie_publisher._load_fanqie_config(root)
    book_name = config.get("book_name")
    account_name = config.get("account_name", "默认账号")
    if not book_name:
        raise HTTPException(status_code=400, detail="请先配置番茄书名")

    result = await fanqie_publisher.sync_chapters(account_name, book_name, str(root))
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/publish")
async def publish_chapters(data: FanqiePublishRequest, root: Path = Depends(get_project_root)):
    """启动后台发布任务"""
    config = fanqie_publisher._load_fanqie_config(root)
    book_name = config.get("book_name")
    account_name = config.get("account_name", "默认账号")
    if not book_name:
        raise HTTPException(status_code=400, detail="请先配置番茄书名")
    if not data.chapter_ids:
        raise HTTPException(status_code=400, detail="请选择要发布的章节")

    result = fanqie_publisher.start_publish_background(str(root), book_name, account_name, data.chapter_ids)
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result


@router.get("/publish/poll")
async def poll_publish():
    """轮询发布进度"""
    return fanqie_publisher.get_publish_poll()


@router.post("/publish/stop")
async def stop_publish():
    """强制停止发布任务"""
    return fanqie_publisher.stop_publish()
