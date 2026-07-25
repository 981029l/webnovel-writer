"""项目级 Prompt 配置存储。

将全局 `.claude/skills/webnovel-write/prompts` 中的模板快照到项目目录，
避免运行时按题材/子风格反复动态匹配。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.genre_catalog import (
    canonical_genre_id,
    canonical_substyle_id,
    get_genre_bucket,
    get_substyle_entry,
)
from services.prompt_fallbacks import (
    SLOT_FILENAMES as TEMPLATE_SLOT_FILENAMES,
    SLOT_VARIABLES as TEMPLATE_SLOT_VARIABLES,
)


APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPTS_DIR = APP_ROOT / ".claude" / "skills" / "webnovel-write" / "prompts"
PROJECT_PROMPTS_DIRNAME = ".webnovel/prompts"
PROJECT_PROMPTS_META = "meta.json"

# 项目 Prompt 快照的结构版本。
# v2：新增大纲/连摘槽位，extract_state 由死代码旧契约（new_entities/state_updates）
# 重定义为真实提取链路模板（new_characters/... 契约）。
# v3：新增黄金三章开篇槽位（opening_three）；大纲/提取/连摘模板基底融入
# D:\小说md 提示词库蒸馏的方法论（章级四任务/伏笔台账/五维自检等）。
# v4：分卷大纲支持分批生成（续写契约）；玄幻桶开局禁令（禁欠债催缴式开局）。
# v5：题材大纲附加要求（OUTLINE_METHOD_EXTRA）扩展到总纲初稿/总纲重写模板；
# 重写模板要求修正当前文稿中违反题材禁令的桥段。
# v6：分卷卷标题改用全卷范围变量（vol_start_chapter/vol_end_chapter，分批时不再
# 被批次范围覆盖）；契约禁止「本批概览」等过程性段落；玄幻欠债禁令扩展到背景元素。
# 版本落后的项目在 ensure_project_prompts 中对未自定义槽位做一次全量强制刷新。
PROMPTS_META_VERSION = 6


PROMPT_SLOTS: List[Dict[str, Any]] = [
    {
        "id": "writer_base",
        "name": "通用写作骨架",
        "group": "写作",
        "description": "章节正文的通用底线与输出骨架。",
        "filename": "writer-base.md",
        "variables": ["core_constraints", "worldview", "protagonist_name", "protagonist_desc"],
    },
    {
        "id": "genre_writer",
        "name": "题材写作协议",
        "group": "写作",
        "description": "项目当前题材的专属写作协议，创建项目后固定为项目快照。",
        "filename": "genre-writer.md",
        "variables": ["genre", "stage"],
    },
    {
        "id": "substyle_writer",
        "name": "子风格写作协议",
        "group": "写作",
        "description": "项目当前子风格的专属写作协议，创建项目后固定为项目快照。",
        "filename": "substyle-writer.md",
        "variables": ["genre", "substyle", "stage"],
    },
    {
        "id": "opening_three",
        "name": "黄金三章开篇协议",
        "group": "写作",
        "description": "写第 1-3 章时注入的开篇协议：情绪契约、三章功能分配、压迫-反击节奏。",
        "filename": TEMPLATE_SLOT_FILENAMES["opening_three"],
        "variables": TEMPLATE_SLOT_VARIABLES["opening_three"],
    },
    {
        "id": "outline_master",
        "name": "总纲初稿模板",
        "group": "大纲",
        "description": "初始化时生成全书总纲的完整提示词模板（按题材/子风格快照）。",
        "filename": TEMPLATE_SLOT_FILENAMES["outline_master"],
        "variables": TEMPLATE_SLOT_VARIABLES["outline_master"],
    },
    {
        "id": "outline_rewrite",
        "name": "总纲重写模板",
        "group": "大纲",
        "description": "重新规划全书总纲时的完整提示词模板。",
        "filename": TEMPLATE_SLOT_FILENAMES["outline_rewrite"],
        "variables": TEMPLATE_SLOT_VARIABLES["outline_rewrite"],
    },
    {
        "id": "outline_volume",
        "name": "分卷大纲模板",
        "group": "大纲",
        "description": "生成分卷详细大纲（逐章规划）的完整提示词模板。",
        "filename": TEMPLATE_SLOT_FILENAMES["outline_volume"],
        "variables": TEMPLATE_SLOT_VARIABLES["outline_volume"],
    },
    {
        "id": "outline_polish",
        "name": "大纲润色模板",
        "group": "大纲",
        "description": "按用户要求润色大纲时的系统提示词模板。",
        "filename": TEMPLATE_SLOT_FILENAMES["outline_polish"],
        "variables": TEMPLATE_SLOT_VARIABLES["outline_polish"],
    },
    {
        "id": "review",
        "name": "正文审查模板",
        "group": "审查",
        "description": "章节审查时使用的系统提示词。",
        "filename": "review.md",
        "variables": ["core_constraints", "common_mistakes", "cool_points"],
    },
    {
        "id": "extract_state",
        "name": "实体提取模板",
        "group": "设定收容",
        "description": "章节保存后提取新实体（角色/宝物/功法/势力/地点）与状态变更的模板，实际驱动设定收容链路。",
        "filename": TEMPLATE_SLOT_FILENAMES["extract_state"],
        "variables": TEMPLATE_SLOT_VARIABLES["extract_state"],
    },
    {
        "id": "chapter_hard_constraints",
        "name": "章节硬约束",
        "group": "写作",
        "description": "章节正文的通用硬约束（字数、大纲执行、命名一致性等底线规则）。",
        "filename": "chapter-hard-constraints.md",
        "variables": [
            "core_constraints", "worldview", "protagonist_name",
            "protagonist_desc", "word_count", "word_count_max",
        ],
    },
    {
        "id": "writing_user_prompt",
        "name": "写作用户提示词",
        "group": "写作",
        "description": "章节创作时发送给模型的 user 消息模板（大纲、角色表、边界红线等）。",
        "filename": "writing-user-prompt.md",
        "variables": [
            "chapter", "next_chapter", "chapter_outline", "recent_context",
            "active_roster", "character_details", "realtime_status",
            "entity_libraries", "next_chapter_outline", "chapter_keywords",
            "next_chapter_keywords", "continuity_summary", "previous_ending",
            "genre_style_anchor",
        ],
    },
    {
        "id": "polish",
        "name": "润色提示词",
        "group": "润色",
        "description": "章节润色时的完整系统提示词模板。",
        "filename": "polish.md",
        "variables": [
            "chapter_id", "genre", "substyle", "genre_writer_prompt",
            "substyle_writer_prompt", "genre_guard", "positive_style_instruction",
            "substyle_instruction", "chapter_outline", "substyle_examples",
            "genre_examples", "suggestions", "polish_guide", "typesetting",
            "content",
        ],
    },
    {
        "id": "continuity_summary",
        "name": "连续性摘要模板",
        "group": "摘要",
        "description": "章节保存后生成「下一章必须遵守」交接清单的提示词模板。",
        "filename": TEMPLATE_SLOT_FILENAMES["continuity_summary"],
        "variables": TEMPLATE_SLOT_VARIABLES["continuity_summary"],
    },
]

PROMPT_SLOT_MAP = {slot["id"]: slot for slot in PROMPT_SLOTS}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _backup_file(path: Path) -> Path:
    """为将被覆盖的文件落一个带时间戳的 .bak 副本，返回备份路径。"""
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup


def _project_prompts_dir(project_root: Path) -> Path:
    return Path(project_root) / PROJECT_PROMPTS_DIRNAME


def _meta_file(project_root: Path) -> Path:
    return _project_prompts_dir(project_root) / PROJECT_PROMPTS_META


def _slot_file(project_root: Path, slot_id: str) -> Path:
    slot = PROMPT_SLOT_MAP[slot_id]
    return _project_prompts_dir(project_root) / slot["filename"]


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_meta(project_root: Path) -> Dict[str, Any]:
    meta_path = _meta_file(project_root)
    if not meta_path.exists():
        return {"version": 1, "genre": "", "substyle": "", "slots": {}}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "genre": "", "substyle": "", "slots": {}}


def _save_meta(project_root: Path, meta: Dict[str, Any]) -> None:
    meta_path = _meta_file(project_root)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_style_package_dir(genre: str, substyle: str = "") -> Path:
    """定位子风格独立包目录。子风格缺省时回退该题材默认子风格。"""
    normalized_genre = canonical_genre_id(genre) or "玄幻"
    bucket = get_genre_bucket(normalized_genre) or "xuanhuan"
    normalized_substyle = canonical_substyle_id(normalized_genre, substyle)
    if not normalized_substyle:
        entry = get_substyle_entry(normalized_genre) or {}
        normalized_substyle = str(entry.get("id", "") or "")
    return DEFAULT_PROMPTS_DIR / "genres" / bucket / normalized_substyle


def _resolve_default_source(slot_id: str, genre: str, substyle: str) -> Optional[Path]:
    """所有槽位默认内容一律来自子风格独立包(无共享层)。"""
    slot = PROMPT_SLOT_MAP.get(slot_id)
    if not slot:
        return None
    return resolve_style_package_dir(genre, substyle) / slot["filename"]


def _default_slot_content(slot_id: str, genre: str, substyle: str) -> Dict[str, str]:
    source_path = _resolve_default_source(slot_id, genre, substyle)
    content = _read_text(source_path) if source_path else ""
    return {
        "content": content,
        "source_path": str(source_path) if source_path else "",
    }


def ensure_project_prompts(
    project_root: Path,
    genre: str,
    substyle: str = "",
    *,
    slot_ids: Optional[List[str]] = None,
    force: bool = False,
) -> Dict[str, Any]:
    project_root = Path(project_root)
    prompts_dir = _project_prompts_dir(project_root)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    normalized_genre = canonical_genre_id(genre) or "玄幻"
    normalized_substyle = canonical_substyle_id(normalized_genre, substyle)

    meta = _load_meta(project_root)
    meta_version = int(meta.get("version") or 1)
    needs_version_refresh = meta_version < PROMPTS_META_VERSION

    # 版本迁移必须覆盖全部槽位，不受调用方传入的 slot_ids 限制。
    if needs_version_refresh:
        target_slot_ids = list(PROMPT_SLOT_MAP.keys())
    else:
        target_slot_ids = list(slot_ids or PROMPT_SLOT_MAP.keys())

    meta["version"] = PROMPTS_META_VERSION
    meta["genre"] = normalized_genre
    meta["substyle"] = normalized_substyle
    meta.setdefault("slots", {})

    for slot_id in target_slot_ids:
        if slot_id not in PROMPT_SLOT_MAP:
            continue
        slot = PROMPT_SLOT_MAP[slot_id]
        slot_path = _slot_file(project_root, slot_id)
        source = _default_slot_content(slot_id, normalized_genre, normalized_substyle)
        previous_meta = meta["slots"].get(slot_id, {})
        is_customized = bool(previous_meta.get("customized", False))
        existing_text = _read_text(slot_path)

        force_this = force
        if needs_version_refresh and not is_customized:
            force_this = True
        # extract_state 旧契约指纹：旧模板服务于已删除的死代码链路（输出
        # new_entities/state_updates），保留只会与新提取契约互相矛盾——
        # 即使已自定义也强制刷新，原内容落 .bak 备份。
        if (
            slot_id == "extract_state"
            and slot_path.exists()
            and '"new_entities"' in existing_text
        ):
            _backup_file(slot_path)
            force_this = True
            is_customized = False

        # 空快照自愈：槽位文件存在但为空、而全局包已有内容时重新快照
        # （防止「先注册槽位、后生成包文件」时序把空串固化进项目）。
        should_write = (
            force_this
            or not slot_path.exists()
            or (not existing_text.strip() and bool(source["content"].strip()))
        )

        if should_write:
            _write_text(slot_path, source["content"])

        meta["slots"][slot_id] = {
            "name": slot["name"],
            "group": slot["group"],
            "description": slot["description"],
            "filename": slot["filename"],
            "variables": slot["variables"],
            "source_path": source["source_path"],
            "customized": False if should_write else is_customized,
            "updated_at": _now_iso(),
        }

    _save_meta(project_root, meta)
    return meta


def get_project_prompt_config(project_root: Path, genre: str, substyle: str = "") -> Dict[str, Any]:
    project_root = Path(project_root)
    meta = ensure_project_prompts(project_root, genre, substyle)

    prompts: List[Dict[str, Any]] = []
    for slot in PROMPT_SLOTS:
        slot_meta = meta.get("slots", {}).get(slot["id"], {})
        slot_path = _slot_file(project_root, slot["id"])
        prompts.append(
            {
                "id": slot["id"],
                "name": slot["name"],
                "group": slot["group"],
                "description": slot["description"],
                "variables": slot["variables"],
                "filename": slot["filename"],
                "source_path": slot_meta.get("source_path", ""),
                "customized": bool(slot_meta.get("customized", False)),
                "updated_at": slot_meta.get("updated_at"),
                "content": _read_text(slot_path),
            }
        )

    return {
        "genre": meta.get("genre") or canonical_genre_id(genre) or "玄幻",
        "substyle": meta.get("substyle") or canonical_substyle_id(genre, substyle),
        "prompts": prompts,
    }


def update_project_prompt_contents(project_root: Path, prompts: List[Dict[str, str]]) -> Dict[str, Any]:
    project_root = Path(project_root)
    meta = _load_meta(project_root)
    meta.setdefault("version", 1)
    meta.setdefault("slots", {})

    for item in prompts:
        slot_id = str(item.get("id", "")).strip()
        if slot_id not in PROMPT_SLOT_MAP:
            continue
        content = str(item.get("content", ""))
        _write_text(_slot_file(project_root, slot_id), content)
        slot = PROMPT_SLOT_MAP[slot_id]
        prev = meta["slots"].get(slot_id, {})
        meta["slots"][slot_id] = {
            "name": slot["name"],
            "group": slot["group"],
            "description": slot["description"],
            "filename": slot["filename"],
            "variables": slot["variables"],
            "source_path": prev.get("source_path", ""),
            "customized": True,
            "updated_at": _now_iso(),
        }

    _save_meta(project_root, meta)
    return meta


def reset_project_prompts(
    project_root: Path,
    genre: str,
    substyle: str = "",
    *,
    slot_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return ensure_project_prompts(
        project_root,
        genre,
        substyle,
        slot_ids=slot_ids,
        force=True,
    )


def sync_project_prompts_for_profile_change(
    project_root: Path,
    genre: str,
    substyle: str = "",
    *,
    slot_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """题材/子风格变更后同步项目 Prompt。

    已自定义的槽位保留内容，只更新来源元数据；
    未自定义的槽位刷新为新题材的默认模板。
    """
    project_root = Path(project_root)
    prompts_dir = _project_prompts_dir(project_root)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    normalized_genre = canonical_genre_id(genre) or "玄幻"
    normalized_substyle = canonical_substyle_id(normalized_genre, substyle)
    target_slot_ids = list(slot_ids or PROMPT_SLOT_MAP.keys())

    meta = _load_meta(project_root)
    meta["version"] = PROMPTS_META_VERSION
    meta["genre"] = normalized_genre
    meta["substyle"] = normalized_substyle
    meta.setdefault("slots", {})

    preserved_customized_slots: List[str] = []
    refreshed_slots: List[str] = []

    for slot_id in target_slot_ids:
        if slot_id not in PROMPT_SLOT_MAP:
            continue

        slot = PROMPT_SLOT_MAP[slot_id]
        slot_path = _slot_file(project_root, slot_id)
        source = _default_slot_content(slot_id, normalized_genre, normalized_substyle)
        previous_meta = meta["slots"].get(slot_id, {})
        is_customized = bool(previous_meta.get("customized", False))

        if is_customized and slot_path.exists():
            preserved_customized_slots.append(slot_id)
        else:
            _write_text(slot_path, source["content"])
            is_customized = False
            refreshed_slots.append(slot_id)

        meta["slots"][slot_id] = {
            "name": slot["name"],
            "group": slot["group"],
            "description": slot["description"],
            "filename": slot["filename"],
            "variables": slot["variables"],
            "source_path": source["source_path"],
            "customized": is_customized,
            "updated_at": _now_iso(),
        }

    _save_meta(project_root, meta)
    return {
        "meta": meta,
        "preserved_customized_slots": preserved_customized_slots,
        "refreshed_slots": refreshed_slots,
    }


def get_project_prompt_content(
    project_root: Path,
    slot_id: str,
    genre: str,
    substyle: str = "",
) -> str:
    if slot_id not in PROMPT_SLOT_MAP:
        return ""

    project_root = Path(project_root)
    slot_path = _slot_file(project_root, slot_id)
    meta = _load_meta(project_root)
    meta_version = int(meta.get("version") or 1)

    # 版本落后或文件缺失/为空时先走一次 ensure（版本落后会触发全量迁移），
    # 保证只走运行时、从不打开配置页的项目也能拿到新契约模板。
    if (
        meta_version >= PROMPTS_META_VERSION
        and slot_path.exists()
        and _read_text(slot_path).strip()
    ):
        return _read_text(slot_path)

    ensure_project_prompts(project_root, genre, substyle, slot_ids=[slot_id])
    return _read_text(slot_path)


def push_project_prompt_to_global(
    project_root: Path,
    slot_id: str,
    genre: str,
    substyle: str = "",
) -> Dict[str, Any]:
    """把项目槽位模板回写到全局子风格包（影响新项目与「恢复默认」）。

    目标路径完全由服务端从 slot_id + 项目题材推导，客户端不传路径。
    覆盖前对全局原文件落 .bak 备份；推送后项目内容与全局默认一致，
    customized 复位为 False。
    """
    if slot_id not in PROMPT_SLOT_MAP:
        raise ValueError(f"未知槽位: {slot_id}")

    project_root = Path(project_root)
    slot = PROMPT_SLOT_MAP[slot_id]
    content = _read_text(_slot_file(project_root, slot_id))
    if not content.strip():
        raise ValueError("项目模板内容为空，拒绝推送")

    target = (resolve_style_package_dir(genre, substyle) / slot["filename"]).resolve()
    base = DEFAULT_PROMPTS_DIR.resolve()
    if base not in target.parents:
        raise ValueError("目标路径越界，已拒绝")
    if not target.parent.exists():
        raise ValueError("目标子风格包目录不存在，拒绝创建新包")

    backup_path = ""
    if target.exists():
        backup_path = str(_backup_file(target))
    _write_text(target, content)

    meta = _load_meta(project_root)
    meta.setdefault("slots", {})
    meta["slots"][slot_id] = {
        "name": slot["name"],
        "group": slot["group"],
        "description": slot["description"],
        "filename": slot["filename"],
        "variables": slot["variables"],
        "source_path": str(target),
        "customized": False,
        "updated_at": _now_iso(),
    }
    _save_meta(project_root, meta)

    return {
        "slot_id": slot_id,
        "target_path": str(target),
        "backup_path": backup_path,
        "meta": meta,
    }
