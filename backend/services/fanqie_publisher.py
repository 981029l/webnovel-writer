"""番茄小说自动发布服务 — 基于 Playwright 浏览器自动化（多账号版）"""

import os
import re
import json
import base64
import time
import queue
import asyncio
import atexit
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# 番茄小说 URLs
BOOK_MANAGE_URL = "https://fanqienovel.com/main/writer/book-manage"
LOGIN_URL = "https://fanqienovel.com/main/writer/?enter_from=author_zone"

# 多账号目录
ACCOUNTS_DIR = Path.home() / ".webnovel" / "fanqie_accounts"

# 单线程执行器
_pw_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

# 全局浏览器实例
_playwright_instance = None
_browser_instance = None
_browser_lock = __import__('threading').Lock()

# 登录会话（登录成功后保持，直到手动关闭）
_login_context = None
_login_page = None

# 跟踪所有活跃的浏览器上下文（用于调试/强制关闭）
_active_contexts = []  # [(name, context)]
_contexts_lock = __import__('threading').Lock()


def _cleanup():
    global _playwright_instance, _browser_instance, _login_context, _login_page
    try:
        if _login_page: _login_page.close()
        if _login_context: _login_context.close()
        if _browser_instance: _browser_instance.close()
        if _playwright_instance: _playwright_instance.stop()
    except Exception:
        pass


atexit.register(_cleanup)


# ─────────── 环境检查 ───────────

def check_environment() -> dict:
    """轻量级环境检查"""
    result = {"ready": False, "error": None, "fix_commands": []}
    try:
        import playwright
    except ImportError:
        result["error"] = "未安装 playwright 库"
        result["fix_commands"] = ["pip install playwright", "playwright install chromium"]
        return result

    browsers_path = Path.home() / "Library" / "Caches" / "ms-playwright"
    if not browsers_path.exists():
        browsers_path = Path.home() / ".cache" / "ms-playwright"
    if browsers_path.exists() and list(browsers_path.glob("chromium*")):
        result["ready"] = True
    else:
        result["error"] = "Chromium 浏览器未安装"
        result["fix_commands"] = ["playwright install chromium"]
    return result


def _ensure_playwright():
    """确保浏览器实例"""
    global _playwright_instance, _browser_instance
    with _browser_lock:
        if _browser_instance is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                raise RuntimeError("未安装 playwright 库。请执行: pip install playwright && playwright install chromium")
            _playwright_instance = sync_playwright().start()
            try:
                _browser_instance = _playwright_instance.chromium.launch(headless=True)
            except Exception as e:
                err = str(e)
                if "shared libraries" in err:
                    raise RuntimeError("Chromium 缺少系统依赖。请执行: playwright install-deps chromium")
                raise RuntimeError(f"Chromium 启动失败: {err}\n请执行: playwright install chromium")
    return _browser_instance


def _track_context(name: str, context):
    """注册活跃上下文"""
    with _contexts_lock:
        _active_contexts.append((name, context))


def _untrack_context(context):
    """移除已关闭的上下文"""
    with _contexts_lock:
        _active_contexts[:] = [(n, c) for n, c in _active_contexts if c is not context]


def get_browser_sessions() -> list:
    """返回当前活跃的浏览器会话列表"""
    with _contexts_lock:
        sessions = [{"name": n} for n, c in _active_contexts]
    # 加上登录会话
    if _login_context is not None:
        has_login = any(n == "login" for n, _ in _active_contexts)
        if not has_login:
            sessions.append({"name": "login"})
    return sessions


def close_all_browsers() -> dict:
    """关闭所有活跃的浏览器上下文"""
    global _login_context, _login_page
    closed = 0
    # 关闭登录会话
    if _login_context is not None:
        _close_login_browser_internal()
        _login_state["active"] = False
        _login_state["status"] = "idle"
        _login_state["message"] = ""
        _login_state["screenshot"] = ""
        closed += 1
    # 关闭其他活跃上下文
    with _contexts_lock:
        for name, ctx in _active_contexts:
            try:
                ctx.close()
                closed += 1
            except Exception:
                pass
        _active_contexts.clear()
    return {"closed": closed}


# ─────────── 多账号管理 ───────────

def _account_file(name: str) -> Path:
    """获取账号状态文件路径"""
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return ACCOUNTS_DIR / f"{safe_name}.json"


def list_accounts() -> list:
    """列出所有已保存的账号"""
    if not ACCOUNTS_DIR.exists():
        return []
    accounts = []
    for f in sorted(ACCOUNTS_DIR.glob("*.json")):
        accounts.append({"name": f.stem, "logged_in": True})
    return accounts


def delete_account(name: str) -> dict:
    """删除账号"""
    f = _account_file(name)
    if f.exists():
        f.unlink()
    return {"success": True}


# ─────────── 项目配置 ───────────

def _load_fanqie_config(project_root: Path) -> dict:
    config_file = project_root / ".webnovel" / "fanqie_config.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_fanqie_config(project_root: Path, config: dict):
    webnovel_dir = project_root / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    (webnovel_dir / "fanqie_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─────────── Markdown 转纯文本 ───────────

def md_to_plaintext(content: str, filename: str = "") -> tuple:
    chapter_num = ""
    title = ""
    if filename:
        m = re.search(r"第(\d+)章[：:\-\s]*(.*)", filename)
        if m:
            chapter_num = m.group(1)
            title = m.group(2).strip()

    lines = content.split('\n')
    body_lines = []
    for line in lines:
        if re.match(r'^\s*<!--.*?-->\s*$', line, re.DOTALL):
            continue
        m = re.match(r'^#\s*第(\d+)章[：:\-\s]*(.*)', line)
        if m:
            if not chapter_num: chapter_num = m.group(1)
            if not title: title = m.group(2).strip()
            continue
        if re.match(r'^#+\s', line):
            continue
        body_lines.append(line)

    body = '\n'.join(body_lines).strip()
    body = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)
    body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)
    body = re.sub(r'\*(.+?)\*', r'\1', body)
    body = re.sub(r'~~(.+?)~~', r'\1', body)
    body = body.replace('（开始您的创作...）', '').replace('（点击 AI 规划本卷自动生成）', '')
    return (chapter_num, title, body)


# ─────────── 登录（轮询模式 + 多账号 + 手动关闭） ───────────

_login_state = {
    "active": False,
    "status": "idle",
    "message": "",
    "screenshot": "",
    "error": "",
    "account_name": "",
    "browser_open": False,
}


def _take_qr_screenshot(page):
    """尝试只截取二维码区域，失败则截全页"""
    qr_selectors = [
        'canvas',
        'img[src*="qrcode"]',
        'img[src*="qr"]',
        '[class*="qr"] canvas',
        '[class*="qr"] img',
        '[class*="qrcode"]',
        '[class*="QRCode"]',
    ]
    for sel in qr_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                ss = el.screenshot()
                if len(ss) > 500:  # 确保不是空白图
                    return ss
        except Exception:
            continue
    # 回退：截全页
    return page.screenshot(full_page=False)


def _is_logged_in(page) -> bool:
    try:
        url = page.url
        if "login" in url.lower() or "passport" in url.lower():
            return False
        for sel in ['text="章节管理"', 'text="创作中心"', 'text="作品管理"', 'text="创建新书"']:
            try:
                if page.locator(sel).first.is_visible(timeout=1000):
                    return True
            except Exception:
                continue
        for sel in ['text="扫码登录"', 'text="密码登录"', 'text="验证码登录"']:
            try:
                if page.locator(sel).first.is_visible(timeout=500):
                    return False
            except Exception:
                continue
        return False
    except Exception:
        return False


def _login_worker(account_name: str):
    """后台登录线程"""
    global _login_state, _login_context, _login_page

    _login_state.update({
        "active": True, "status": "running", "message": "正在启动浏览器...",
        "screenshot": "", "error": "", "account_name": account_name, "browser_open": False,
    })

    try:
        browser = _ensure_playwright()
        _login_state["message"] = "正在打开番茄登录页面..."
        _login_context = browser.new_context()
        _track_context("login", _login_context)
        _login_page = _login_context.new_page()

        _login_page.goto(LOGIN_URL, timeout=60000)
        _login_state["message"] = "正在切换到扫码登录..."
        time.sleep(2)

        # 切换到扫码登录
        for qr_text in ["扫码登录", "二维码登录"]:
            try:
                btn = _login_page.get_by_text(qr_text, exact=False).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    time.sleep(2)
                    break
            except Exception:
                continue

        _login_state["message"] = "等待扫码..."
        _login_state["browser_open"] = True

        for i in range(150):
            if not _login_state["active"]:
                break

            try:
                ss = _take_qr_screenshot(_login_page)
                _login_state["screenshot"] = base64.b64encode(ss).decode('utf-8')
                _login_state["message"] = "请使用手机扫描二维码登录"
            except Exception:
                pass

            if _is_logged_in(_login_page):
                # 保存到多账号目录
                state_file = _account_file(account_name)
                _login_context.storage_state(path=str(state_file))
                _login_state["status"] = "success"
                _login_state["message"] = f"账号 [{account_name}] 登录成功，请手动关闭浏览器"
                # 不关闭 context/page，等用户手动关闭
                _login_state["active"] = False
                return

            time.sleep(2)

        _login_state["status"] = "timeout"
        _login_state["message"] = "登录超时，请重试"
        _close_login_browser_internal()

    except Exception as e:
        _login_state["status"] = "error"
        _login_state["message"] = str(e)
        _login_state["error"] = str(e)
        _close_login_browser_internal()

    _login_state["active"] = False


def _close_login_browser_internal():
    """内部：关闭登录浏览器会话"""
    global _login_context, _login_page
    try:
        if _login_page: _login_page.close()
    except Exception:
        pass
    try:
        if _login_context:
            _untrack_context(_login_context)
            _login_context.close()
    except Exception:
        pass
    _login_page = None
    _login_context = None
    _login_state["browser_open"] = False


def start_login_background(account_name: str = "默认账号"):
    # 如果有残留的浏览器会话，先自动关闭
    if _login_state["browser_open"] and not _login_state["active"]:
        _close_login_browser_internal()
    # 强制重置卡死的登录状态（超过5分钟视为卡死）
    if _login_state["active"]:
        import threading
        # 检查执行器中是否真有线程在跑
        alive = any(t.is_alive() for t in threading.enumerate() if t.name.startswith("playwright"))
        if not alive:
            _login_state["active"] = False
            _close_login_browser_internal()
        else:
            return {"ok": False, "message": "登录进程正在运行，请稍候"}
    _pw_executor.submit(_login_worker, account_name)
    return {"ok": True, "message": "登录进程已启动"}


def get_login_poll() -> dict:
    return {
        "active": _login_state["active"],
        "status": _login_state["status"],
        "message": _login_state["message"],
        "screenshot": _login_state["screenshot"],
        "error": _login_state["error"],
        "account_name": _login_state["account_name"],
        "browser_open": _login_state["browser_open"],
    }


def close_login_browser() -> dict:
    """手动关闭登录浏览器"""
    _close_login_browser_internal()
    _login_state["status"] = "idle"
    _login_state["message"] = ""
    _login_state["screenshot"] = ""
    return {"success": True}


def cancel_login():
    _login_state["active"] = False
    _close_login_browser_internal()


def check_login_status() -> dict:
    """返回所有账号状态"""
    accounts = list_accounts()
    return {"accounts": accounts}


def _verify_account_sync(account_name: str) -> dict:
    """通过读取 cookie 过期时间快速验证账号有效性（不启动浏览器）"""
    state_file = _account_file(account_name)
    if not state_file.exists():
        return {"name": account_name, "valid": False, "reason": "账号文件不存在"}

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        cookies = data.get("cookies", [])
        if not cookies:
            return {"name": account_name, "valid": False, "reason": "无 cookie 数据"}

        # 检查关键 cookie 是否存在且未过期
        now = time.time()
        key_cookies = [c for c in cookies if c.get("domain", "").endswith("fanqienovel.com")]
        if not key_cookies:
            return {"name": account_name, "valid": False, "reason": "无番茄域名 cookie"}

        # 检查 sessionid 等关键登录 cookie
        session_cookies = [c for c in key_cookies if c.get("name", "") in ("sessionid", "sessionid_ss", "sid_guard", "sid_tt")]
        if not session_cookies:
            # 也接受有 cookie 但没有明确 session 的情况（可能用了其他认证方式）
            session_cookies = key_cookies

        expired = []
        for c in session_cookies:
            exp = c.get("expires", -1)
            if exp > 0 and exp < now:
                expired.append(c.get("name", ""))

        if expired:
            return {"name": account_name, "valid": False, "reason": f"cookie 已过期: {', '.join(expired[:3])}"}

        # cookie 文件修改时间
        mtime = state_file.stat().st_mtime
        age_days = (now - mtime) / 86400
        if age_days > 30:
            return {"name": account_name, "valid": False, "reason": f"登录已超过 {int(age_days)} 天，建议重新登录"}

        return {"name": account_name, "valid": True, "reason": ""}
    except Exception as e:
        return {"name": account_name, "valid": False, "reason": f"读取失败: {str(e)[:80]}"}


async def verify_account(account_name: str) -> dict:
    """验证单个账号 cookie 有效性（纯文件检查，不启动浏览器，不阻塞）"""
    return _verify_account_sync(account_name)


async def verify_all_accounts() -> list:
    """逐个验证所有账号（共用单线程执行器，顺序执行）"""
    accounts = list_accounts()
    results = []
    for acc in accounts:
        r = await verify_account(acc["name"])
        results.append(r)
    return results


def _debug_screenshot_sync(account_name: str) -> dict:
    """截图番茄后台并保存HTML结构"""
    state_file = _account_file(account_name)
    if not state_file.exists():
        return {"ok": False, "message": "账号不存在"}
    browser = _ensure_playwright()
    context = browser.new_context(storage_state=str(state_file))
    _track_context(f"debug:{account_name}", context)
    page = context.new_page()
    try:
        page.goto(BOOK_MANAGE_URL, timeout=30000)
        time.sleep(4)
        debug_dir = ACCOUNTS_DIR / "debug"
        debug_dir.mkdir(exist_ok=True)
        page.screenshot(path=str(debug_dir / f"page_{account_name}.png"), full_page=True)
        # 保存页面文本结构
        text = page.evaluate('() => document.body.innerText')
        (debug_dir / f"text_{account_name}.txt").write_text(text, encoding="utf-8")
        # 保存所有"章节管理"链接的上下文
        info = page.evaluate('''() => {
            const results = [];
            const all = document.querySelectorAll('*');
            for (const el of all) {
                if (el.textContent.trim() === '章节管理' && el.children.length === 0) {
                    let ctx = [];
                    let p = el;
                    for (let i = 0; i < 6 && p; i++) {
                        ctx.push({tag: p.tagName, class: p.className, text: p.textContent.trim().substring(0, 100)});
                        p = p.parentElement;
                    }
                    results.push(ctx);
                }
            }
            return results;
        }''')
        (debug_dir / f"links_{account_name}.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "message": f"截图已保存到 {debug_dir}", "url": page.url}
    except Exception as e:
        return {"ok": False, "message": str(e)}
    finally:
        try:
            page.close()
            context.close()
        except Exception:
            pass
        _untrack_context(context)


async def debug_screenshot(account_name: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_pw_executor, _debug_screenshot_sync, account_name)


def logout(account_name: str):
    return delete_account(account_name)


# ─────────── 书籍列表 ───────────

def _list_books_sync(account_name: str) -> list:
    state_file = _account_file(account_name)
    if not state_file.exists():
        return []

    browser = _ensure_playwright()
    context = browser.new_context(storage_state=str(state_file))
    _track_context(f"books:{account_name}", context)
    page = context.new_page()
    books = []

    try:
        page.goto(BOOK_MANAGE_URL, timeout=30000)
        time.sleep(4)

        if "login" in page.url.lower() or "enter_from" in page.url:
            raise RuntimeError(f"账号 [{account_name}] 登录已失效，请重新登录")

        # 用 JS 从 info-content 卡片提取书名和书籍ID
        books = page.evaluate('''() => {
            const cards = document.querySelectorAll('.info-content');
            const result = [];
            for (const card of cards) {
                const text = (card.innerText || card.textContent || '').trim();
                if (!text) continue;
                let name = text.split('\\n')[0].trim();
                for (const kw of ['征文作品', '最近更新', '连载', '完结']) {
                    const idx = name.indexOf(kw);
                    if (idx > 0) { name = name.substring(0, idx).trim(); break; }
                }
                // 提取书籍ID：从"章节管理"链接的href中获取
                let bookId = '';
                const links = card.querySelectorAll('a');
                for (const link of links) {
                    const href = link.getAttribute('href') || '';
                    const m = href.match(/\\/book\\/([\\d]+)/);
                    if (m) { bookId = m[1]; break; }
                }
                // 也从 book-info 链接获取
                if (!bookId) {
                    const allLinks = card.querySelectorAll('a[href*="book"]');
                    for (const link of allLinks) {
                        const m = (link.getAttribute('href') || '').match(/(\\d{10,})/);
                        if (m) { bookId = m[1]; break; }
                    }
                }
                if (name.length >= 2 && name.length <= 50) {
                    result.push({name: name, book_id: bookId});
                }
            }
            return result;
        }''')

    except RuntimeError:
        raise
    except Exception:
        pass
    finally:
        try:
            page.close()
            context.close()
        except Exception:
            pass
        _untrack_context(context)

    return books or []


async def list_books(account_name: str = "默认账号") -> list:
    """异步获取书籍列表（在 Playwright 线程池中执行）"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_pw_executor, _list_books_sync, account_name)


# ─────────── 章节状态同步（从番茄拉取真实状态） ───────────

def _sync_chapters_sync(account_name: str, book_name: str, project_root: str) -> dict:
    """从番茄后台拉取章节的真实发布状态，更新本地 config"""
    state_file = _account_file(account_name)
    if not state_file.exists():
        return {"ok": False, "message": f"账号 [{account_name}] 未登录"}

    root = Path(project_root)
    browser = _ensure_playwright()
    context = browser.new_context(storage_state=str(state_file))
    _track_context(f"sync:{account_name}", context)
    page = context.new_page()

    try:
        page.goto(BOOK_MANAGE_URL, timeout=60000)
        page.wait_for_timeout(3000)

        # 找到目标书籍并进入章节管理
        book_container = page.locator('div, li, section').filter(
            has_text=book_name).filter(has=page.locator('text="章节管理"')).last

        if book_container.is_visible():
            book_container.get_by_text("章节管理").first.click()
        else:
            # 尝试直接点
            page.get_by_text("章节管理").first.click()

        page.wait_for_timeout(4000)
        # 可能打开了新tab
        target_page = context.pages[-1] if len(context.pages) > 1 else page

        # 用 JS 提取章节列表和状态
        remote_chapters = target_page.evaluate('''() => {
            const text = document.body.innerText;
            const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
            const chapters = [];
            for (let i = 0; i < lines.length; i++) {
                const m = lines[i].match(/^第\\s*(\\d+)\\s*章/);
                if (!m) continue;
                const num = parseInt(m[1]);
                // 向后查找状态：已发布/草稿/定时发布
                let status = 'unknown';
                for (let j = i; j < Math.min(i + 5, lines.length); j++) {
                    if (/已发布|已发表/.test(lines[j])) { status = 'published'; break; }
                    if (/草稿/.test(lines[j])) { status = 'draft'; break; }
                    if (/定时/.test(lines[j])) { status = 'scheduled'; break; }
                }
                chapters.push({num, status});
            }
            return chapters;
        }''')

        # 更新本地 config
        published_ids = [ch["num"] for ch in (remote_chapters or []) if ch["status"] == "published"]
        config = _load_fanqie_config(root)
        config["published_chapters"] = published_ids
        _save_fanqie_config(root, config)

        return {
            "ok": True,
            "remote_chapters": remote_chapters or [],
            "published_count": len(published_ids),
            "message": f"同步完成：{len(published_ids)} 章已发布"
        }

    except Exception as e:
        return {"ok": False, "message": f"同步失败: {str(e)}"}
    finally:
        try:
            if len(context.pages) > 1:
                context.pages[-1].close()
            page.close()
            context.close()
        except Exception:
            pass
        _untrack_context(context)


async def sync_chapters(account_name: str, book_name: str, project_root: str) -> dict:
    """异步同步章节状态"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _pw_executor, _sync_chapters_sync, account_name, book_name, project_root
    )


# ─────────── 章节发布 ───────────

_PUBLISH_ERROR_KEYWORDS = ["上限", "限制", "频繁", "不能", "超过", "失败", "请稍后", "已达到"]


def _check_publish_error(page) -> str:
    """检查发布后页面是否有错误/限制提示，返回错误信息或空字符串"""
    # 先检查常见的 toast/弹窗选择器
    toast_selectors = [
        '.toast', '.message', '.alert', '.notice', '.tip',
        '[class*="toast"]', '[class*="message"]', '[class*="notice"]',
        '[class*="Toast"]', '[class*="Message"]', '[class*="modal"]',
        '[role="alert"]', '[role="dialog"]',
    ]
    for sel in toast_selectors:
        try:
            els = page.locator(sel).all()
            for el in els:
                if el.is_visible(timeout=300):
                    text = el.inner_text().strip()
                    if text and any(kw in text for kw in _PUBLISH_ERROR_KEYWORDS):
                        return text
        except Exception:
            continue
    # 兜底：扫描整页文本
    try:
        body_text = page.locator('body').inner_text()
        for kw in _PUBLISH_ERROR_KEYWORDS:
            if kw in body_text:
                # 尝试提取含关键词的那一行
                for line in body_text.split('\n'):
                    line = line.strip()
                    if kw in line and len(line) < 100:
                        return line
                return f"检测到限制提示（含'{kw}'）"
    except Exception:
        pass
    return ""


def _publish_single_chapter(page, context, book_name, chapter_num, chapter_title, content, book_id=""):
    """发布单个章节"""
    try:
        # 如果有 book_id，直接跳到章节管理页，不走 book-manage
        if book_id:
            chapter_mgmt_url = f"https://fanqienovel.com/main/writer/chapter-manage/{book_id}"
            print(f"[fanqie] 直接跳转章节管理: {chapter_mgmt_url}")
            page.goto(chapter_mgmt_url, timeout=60000)
            page.wait_for_timeout(3000)
        else:
            # 没有 book_id，走旧逻辑从 book-manage 页找书
            page.goto(BOOK_MANAGE_URL, timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(2000)

            # 如果被重定向，重试
            for retry in range(3):
                if "book-manage" in page.url:
                    break
                print(f"[fanqie] 页面被重定向到 {page.url}，重新导航")
                page.goto(BOOK_MANAGE_URL, timeout=30000)
                page.wait_for_timeout(2000)

            if "book-manage" not in page.url:
                try:
                    page.get_by_text("作品管理").first.click(force=True)
                    page.wait_for_timeout(3000)
                except Exception:
                    pass

            page.wait_for_timeout(1000)

            # 清弹窗
            for _ in range(3):
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            try:
                for close_sel in ['.info-content .close', '.info-content button', '.modal-close', '[class*="close"]']:
                    close_btn = page.locator(close_sel).first
                    if close_btn.is_visible(timeout=500):
                        close_btn.click(force=True)
                        page.wait_for_timeout(300)
            except Exception:
                pass

            # 精确匹配书名找章节管理入口
            match_info = page.evaluate('''(bookName) => {
                const cards = document.querySelectorAll('.info-content');
                const debug = {cards: cards.length, texts: [], url: window.location.href};
                for (const card of cards) {
                    const text = (card.innerText || card.textContent || '').trim();
                    debug.texts.push(text.substring(0, 60));
                    if (text.includes(bookName)) {
                        const links = card.querySelectorAll('a, button');
                        for (const link of links) {
                            if (link.textContent.trim() === '章节管理') {
                                link.click();
                                return {clicked: true, debug: debug};
                            }
                        }
                    }
                }
                return {clicked: false, debug: debug};
            }''', book_name)
            print(f"[fanqie] 匹配结果: {match_info}")
            if not match_info.get("clicked"):
                debug = match_info.get("debug", {})
                raise Exception(f"未找到书籍「{book_name}」的章节管理入口 (页面有{debug.get('cards',0)}本书, URL={debug.get('url','')})")

            page.wait_for_timeout(4000)

        # ── 现在已经在章节管理页 ──
        editor_page = page
        # 章节管理可能打开新标签页
        if len(context.pages) > 1:
            editor_page = context.pages[-1]

        # 清弹窗/遮罩（章节管理页也可能有）
        for _ in range(3):
            editor_page.keyboard.press("Escape")
            editor_page.wait_for_timeout(300)
        try:
            for close_sel in ['.info-content .close', '.info-content button', '.modal-close', '[class*="close"]']:
                close_btn = editor_page.locator(close_sel).first
                if close_btn.is_visible(timeout=300):
                    close_btn.click(force=True)
                    editor_page.wait_for_timeout(300)
        except Exception:
            pass

        # 检查草稿
        draft_row = editor_page.locator('tr, li, .chapter-item').filter(
            has_text=re.compile(f"第\\s*{chapter_num}\\s*章")).first
        if draft_row.is_visible(timeout=3000):
            edit_icon = draft_row.locator('td').last.locator('svg, i, a, span, button, img').first
            if edit_icon.is_visible(): edit_icon.click(force=True)
            else: draft_row.click(force=True)
        else:
            # 尝试多种方式找"新建章节"按钮
            new_btn = None
            for selector in [
                lambda: editor_page.get_by_role("button", name="新建章节").first,
                lambda: editor_page.get_by_text("新建章节").first,
                lambda: editor_page.get_by_text("创建章节").first,
                lambda: editor_page.get_by_role("button", name="创建章节").first,
                lambda: editor_page.locator('button:has-text("新建"), a:has-text("新建")').first,
            ]:
                try:
                    btn = selector()
                    if btn.is_visible(timeout=2000):
                        new_btn = btn
                        break
                except Exception:
                    continue
            if new_btn:
                new_btn.click(force=True)
            else:
                raise Exception("未找到'新建章节'按钮，番茄页面可能已更新或登录已失效")

        page.wait_for_timeout(4000)
        if len(context.pages) > 1:
            editor_page = context.pages[-1]

        # 清弹窗
        for _ in range(3):
            editor_page.keyboard.press("Escape")
            editor_page.wait_for_timeout(200)
        for _ in range(10):
            clicked = False
            try:
                for txt in ["下一步", "完成", "我知道了", "跳过"]:
                    for btn in editor_page.get_by_text(txt, exact=True).element_handles():
                        box = btn.bounding_box()
                        if box and box['y'] > 100:
                            btn.click(); editor_page.wait_for_timeout(600); clicked = True
            except Exception: pass
            if not clicked: break

        # 填序号和标题
        num_input = editor_page.locator('input[type="text"]').first
        if num_input.is_visible(): num_input.fill(chapter_num, force=True)

        title_input = editor_page.get_by_placeholder("请输入标题", exact=False).first
        if not title_input.is_visible(): title_input = editor_page.get_by_placeholder("请输入章节名", exact=False).first
        if not title_input.is_visible(): title_input = editor_page.locator('input[type="text"]').last
        if title_input.is_visible(): title_input.fill(chapter_title, force=True)

        # 填正文
        editor = editor_page.locator('.ql-editor').first
        if not editor.is_visible(): editor = editor_page.locator('.ProseMirror').first
        if not editor.is_visible(): editor = editor_page.locator('[contenteditable="true"]').first
        if editor.is_visible():
            editor.click(force=True)
            editor_page.keyboard.press("Control+A")
            editor_page.keyboard.press("Backspace")
            editor_page.evaluate(
                "([el, text]) => { el.innerText = text; el.dispatchEvent(new Event('input', {bubbles: true})); }",
                [editor.element_handle(), content])
            editor.click()
            editor_page.keyboard.press("End")
            editor_page.keyboard.press("Space")
            page.wait_for_timeout(500)
            editor_page.keyboard.press("Backspace")

        # 发布
        next_btn = editor_page.get_by_text("下一步", exact=True).last
        if next_btn.is_visible():
            next_btn.click(force=True)
            try:
                b = editor_page.get_by_role("button", name="提交").first
                b.wait_for(state="visible", timeout=2000); b.click(force=True)
            except Exception: pass
            try:
                b = editor_page.get_by_role("button", name="确定").first
                b.wait_for(state="visible", timeout=2000); b.click(force=True)
            except Exception: pass
            try:
                pub = editor_page.get_by_role("button", name="确认发布").first
                pub.wait_for(state="visible", timeout=6000)
                try:
                    editor_page.get_by_text("是", exact=True).first.click(force=True)
                    editor_page.wait_for_timeout(500)
                except Exception: pass
                pub.click(force=True)
                editor_page.wait_for_timeout(3000)
                # 检查是否有错误/限制提示
                err_msg = _check_publish_error(editor_page)
                if err_msg:
                    result = {"success": False, "message": f"第{chapter_num}章 {chapter_title} {err_msg}"}
                else:
                    result = {"success": True, "message": f"第{chapter_num}章 {chapter_title} 发布成功"}
            except Exception:
                try:
                    sb = editor_page.get_by_text("存草稿", exact=False).first
                    if sb.is_visible():
                        sb.click()
                        result = {"success": False, "message": f"第{chapter_num}章 未能发布，已存为草稿"}
                    else:
                        result = {"success": False, "message": "未找到发布按钮"}
                except Exception: result = {"success": False, "message": "发布失败"}
        else:
            sb = editor_page.get_by_text("存草稿", exact=False).first
            if sb.is_visible():
                sb.click()
                result = {"success": False, "message": f"第{chapter_num}章 未能发布，已存为草稿"}
            else:
                result = {"success": False, "message": "未找到下一步按钮"}

        page.wait_for_timeout(3000)
        if editor_page != page:
            try: editor_page.close()
            except Exception: pass
        return result
    except Exception as e:
        # 保存失败截图用于调试
        try:
            debug_dir = ACCOUNTS_DIR / "debug"
            debug_dir.mkdir(exist_ok=True)
            active_page = editor_page if 'editor_page' in dir() else page
            active_page.screenshot(path=str(debug_dir / f"fail_{chapter_num}.png"))
        except Exception:
            pass
        return {"success": False, "message": str(e)}


def _publish_chapters_sync(project_root, book_name, account_name, chapter_ids):
    """批量发布章节（轮询模式，状态写入 _publish_state）"""
    global _publish_state
    root = Path(project_root)
    state_file = _account_file(account_name)
    print(f"[fanqie] 发布: 账号={account_name}, 书名={book_name}, 章节={chapter_ids}, cookie文件={state_file}")

    if not state_file.exists():
        _publish_state.update({"active": False, "status": "error", "message": f"账号 [{account_name}] 未登录"})
        return

    chapter_files = {}
    chapters_dir = root / "正文"
    if chapters_dir.exists():
        for f in chapters_dir.glob("*.md"):
            m = re.search(r"第(\d+)章", f.name)
            if m:
                cid = int(m.group(1))
                if cid in chapter_ids:
                    chapter_files[cid] = f

    if not chapter_files:
        _publish_state.update({"active": False, "status": "error", "message": "没有找到待发布的章节文件"})
        return

    sorted_ids = sorted(chapter_files.keys())
    total = len(sorted_ids)

    # 发布前先验证账号有效性
    check = _verify_account_sync(account_name)
    if not check["valid"]:
        _publish_state.update({"active": False, "status": "error", "message": f"账号 [{account_name}] {check['reason']}，请重新登录后再发布"})
        return

    browser = _ensure_playwright()
    context = browser.new_context(storage_state=str(state_file))
    _track_context(f"publish:{account_name}", context)
    page = context.new_page()
    success_count = 0
    fail_count = 0
    config = _load_fanqie_config(root)
    results = []

    # 先获取 book_id：到 book-manage 页提取
    book_id = ""
    try:
        page.goto(BOOK_MANAGE_URL, timeout=30000)
        page.wait_for_timeout(4000)
        book_id = page.evaluate('''(bookName) => {
            const cards = document.querySelectorAll('.info-content');
            for (const card of cards) {
                const text = (card.innerText || card.textContent || '').trim();
                if (text.includes(bookName)) {
                    const links = card.querySelectorAll('a[href]');
                    for (const link of links) {
                        const m = (link.getAttribute('href') || '').match(/(\\d{10,})/);
                        if (m) return m[1];
                    }
                }
            }
            return '';
        }''', book_name)
        print(f"[fanqie] 获取到 book_id={book_id}")
    except Exception as e:
        print(f"[fanqie] 获取 book_id 失败: {e}")

    # 如果从 URL 中也能提取（比如被重定向到 book-info 页）
    if not book_id:
        m = re.search(r'/(\d{10,})', page.url)
        if m:
            book_id = m.group(1)
            print(f"[fanqie] 从URL提取 book_id={book_id}")

    try:
        for idx, cid in enumerate(sorted_ids):
            fp = chapter_files[cid]
            content = fp.read_text(encoding="utf-8")
            cnum, ctitle, body = md_to_plaintext(content, fp.stem)
            if not cnum: cnum = str(cid)

            _publish_state.update({
                "current": idx + 1, "total": total,
                "chapter_title": f"第{cnum}章 {ctitle}",
                "message": f"正在上传第{cnum}章..."
            })

            r = _publish_single_chapter(page, context, book_name, cnum, ctitle, body, book_id=book_id)
            if r["success"]:
                success_count += 1
                config.setdefault("published_chapters", [])
                if cid not in config["published_chapters"]:
                    config["published_chapters"].append(cid)
                _save_fanqie_config(root, config)
                results.append({"chapter_id": cid, "success": True, "message": r["message"]})
            else:
                fail_count += 1
                results.append({"chapter_id": cid, "success": False, "message": r["message"]})

            _publish_state["results"] = results
            page.wait_for_timeout(1000)

    except Exception as e:
        results.append({"chapter_id": 0, "success": False, "message": f"发布出错: {str(e)}"})
    finally:
        try: page.close(); context.close()
        except Exception: pass
        _untrack_context(context)
        _publish_state.update({
            "active": False, "status": "done",
            "success_count": success_count, "fail_count": fail_count,
            "total": total, "results": results,
            "message": f"上传完成：成功 {success_count} 章，失败 {fail_count} 章"
        })


# 发布状态（轮询）
_publish_state = {
    "active": False, "status": "idle", "message": "",
    "current": 0, "total": 0, "chapter_title": "",
    "success_count": 0, "fail_count": 0, "results": []
}


def start_publish_background(project_root, book_name, account_name, chapter_ids):
    if _publish_state["active"]:
        return {"ok": False, "message": "发布任务正在运行"}
    _publish_state.update({
        "active": True, "status": "running", "message": "准备上传...",
        "current": 0, "total": len(chapter_ids), "chapter_title": "",
        "success_count": 0, "fail_count": 0, "results": []
    })
    _pw_executor.submit(_publish_chapters_sync, project_root, book_name, account_name, chapter_ids)
    return {"ok": True, "message": "发布任务已启动"}


def stop_publish() -> dict:
    """强制停止发布任务并重置状态"""
    was_active = _publish_state["active"]
    _publish_state.update({
        "active": False, "status": "idle", "message": "",
        "current": 0, "total": 0, "chapter_title": "",
        "success_count": 0, "fail_count": 0, "results": []
    })
    # 同时关闭所有浏览器会话
    close_all_browsers()
    return {"ok": True, "message": "已停止" if was_active else "无运行中的任务"}


def get_publish_poll() -> dict:
    return dict(_publish_state)
