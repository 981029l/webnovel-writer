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

# 登录会话（登录成功后保持，直到手动关闭）
_login_context = None
_login_page = None


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
        if _login_context: _login_context.close()
    except Exception:
        pass
    _login_page = None
    _login_context = None
    _login_state["browser_open"] = False


def start_login_background(account_name: str = "默认账号"):
    # 如果有残留的浏览器会话，先自动关闭
    if _login_state["browser_open"] and not _login_state["active"]:
        _close_login_browser_internal()
    if _login_state["active"]:
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


def logout(account_name: str):
    return delete_account(account_name)


# ─────────── 书籍列表 ───────────

def _list_books_sync(account_name: str) -> list:
    state_file = _account_file(account_name)
    if not state_file.exists():
        return []

    browser = _ensure_playwright()
    context = browser.new_context(storage_state=str(state_file))
    page = context.new_page()
    books = []

    try:
        page.goto(BOOK_MANAGE_URL, timeout=60000)
        time.sleep(4)

        if "login" in page.url.lower() or "enter_from" in page.url:
            return []

        # 用 JS 在页面中提取书名：以"最近更新"为锚点，向上找书名
        books = page.evaluate('''() => {
            const text = document.body.innerText;
            const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
            const result = [];
            const seen = new Set();
            const noise = new Set([
                '番茄小说网','作家课堂','作品管理','征文活动','征文作品',
                '作品推荐','创建章节','创建作品','作品可搜','作品小贴士',
                '章节管理','数据中心','创建新书','草稿箱','作家专区',
                '工作台','我的小说','作品相关','创作中心','消息','帮助',
                '收入','活动','签约','设置','退出','首页',
                '推荐评估','点此了解','刷新','全选','发起推荐'
            ]);
            const noiseRe = [
                /^最近更新/, /^\\d+\\s*章$/, /万字/, /连载|完结|签约/,
                /^第\\d+章/, /推荐|评估|小贴士|创建|管理|课堂|征文/,
                /^\\d+(\\.\\d+)?\\s*万/, /章节/, /作品/, /更新/
            ];
            for (let i = 0; i < lines.length; i++) {
                if (/^最近更新/.test(lines[i])) {
                    for (let j = i - 1; j >= Math.max(0, i - 3); j--) {
                        const line = lines[j];
                        if (line.length >= 2 && line.length <= 30
                            && !seen.has(line) && !noise.has(line)
                            && !noiseRe.some(r => r.test(line))) {
                            seen.add(line);
                            result.push({name: line});
                            break;
                        }
                    }
                }
            }
            return result;
        }''')

    except Exception:
        pass
    finally:
        try:
            page.close()
            context.close()
        except Exception:
            pass

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
                return f"检测到限制提示（含"{kw}"）"
    except Exception:
        pass
    return ""


def _publish_single_chapter(page, context, book_name, chapter_num, chapter_title, content):
    """发布单个章节"""
    try:
        page.goto(BOOK_MANAGE_URL, timeout=60000)
        page.wait_for_timeout(3000)

        book_container = page.locator('div, li, section').filter(
            has_text=book_name).filter(has=page.locator('text="章节管理"')).last

        if book_container.is_visible():
            book_container.get_by_text("章节管理").first.click()
        else:
            page.get_by_text("章节管理").first.click()

        page.wait_for_timeout(4000)
        original_pages = len(context.pages)
        editor_page = context.pages[-1] if original_pages > 1 and context.pages[-1] != page else page

        # 检查草稿
        draft_row = editor_page.locator('tr, li, .chapter-item').filter(
            has_text=re.compile(f"第\\s*{chapter_num}\\s*章")).first
        if draft_row.is_visible():
            edit_icon = draft_row.locator('td').last.locator('svg, i, a, span, button, img').first
            if edit_icon.is_visible(): edit_icon.click()
            else: draft_row.click()
        else:
            new_btn = editor_page.get_by_role("button", name="新建章节").first
            if not new_btn.is_visible(): new_btn = editor_page.get_by_text("新建章节").first
            new_btn.click()

        page.wait_for_timeout(4000)
        if len(context.pages) > original_pages:
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
        return {"success": False, "message": str(e)}


def _publish_chapters_sync(project_root, book_name, account_name, chapter_ids):
    """批量发布章节（轮询模式，状态写入 _publish_state）"""
    global _publish_state
    root = Path(project_root)
    state_file = _account_file(account_name)

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
    browser = _ensure_playwright()
    context = browser.new_context(storage_state=str(state_file))
    page = context.new_page()
    success_count = 0
    fail_count = 0
    config = _load_fanqie_config(root)
    results = []

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

            r = _publish_single_chapter(page, context, book_name, cnum, ctitle, body)
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


def get_publish_poll() -> dict:
    return dict(_publish_state)
