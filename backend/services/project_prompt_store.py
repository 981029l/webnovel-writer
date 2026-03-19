"""项目级 Prompt 配置存储。

将全局 `.claude/skills/webnovel-write/prompts` 中的模板快照到项目目录，
避免运行时按题材/子风格反复动态匹配。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.genre_catalog import canonical_genre_id, canonical_substyle_id, get_genre_bucket


APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPTS_DIR = APP_ROOT / ".claude" / "skills" / "webnovel-write" / "prompts"
PROJECT_PROMPTS_DIRNAME = ".webnovel/prompts"
PROJECT_PROMPTS_META = "meta.json"


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
        "id": "review",
        "name": "正文审查模板",
        "group": "审查",
        "description": "章节审查时使用的系统提示词。",
        "filename": "review.md",
        "variables": ["core_constraints", "common_mistakes", "cool_points"],
    },
    {
        "id": "extract_state",
        "name": "状态提取模板",
        "group": "设定收容",
        "description": "章节保存后用于设定提取与状态更新的模板。",
        "filename": "extract-state.md",
        "variables": ["core_constraints", "content"],
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
]

PROMPT_SLOT_MAP = {slot["id"]: slot for slot in PROMPT_SLOTS}


def _now_iso() -> str:
    return datetime.now().isoformat()


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


def _resolve_default_source(slot_id: str, genre: str, substyle: str) -> Optional[Path]:
    normalized_genre = canonical_genre_id(genre) or "玄幻"
    normalized_substyle = canonical_substyle_id(normalized_genre, substyle)
    bucket = get_genre_bucket(normalized_genre) or "xuanhuan"

    if slot_id == "writer_base":
        return DEFAULT_PROMPTS_DIR / "writer.md"
    if slot_id == "review":
        return DEFAULT_PROMPTS_DIR / "review.md"
    if slot_id == "extract_state":
        return DEFAULT_PROMPTS_DIR / "extract_state.md"
    if slot_id == "genre_writer":
        return DEFAULT_PROMPTS_DIR / "genres" / bucket / "writer.md"
    if slot_id == "substyle_writer":
        if not normalized_substyle:
            return None
        return DEFAULT_PROMPTS_DIR / "genres" / bucket / "substyles" / f"{normalized_substyle}.md"
    if slot_id == "chapter_hard_constraints":
        return DEFAULT_PROMPTS_DIR / "chapter-hard-constraints.md"
    if slot_id == "writing_user_prompt":
        return DEFAULT_PROMPTS_DIR / "writing-user-prompt.md"
    if slot_id == "polish":
        return DEFAULT_PROMPTS_DIR / "polish.md"
    return None


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
    target_slot_ids = list(slot_ids or PROMPT_SLOT_MAP.keys())

    meta = _load_meta(project_root)
    meta.setdefault("version", 1)
    meta["genre"] = normalized_genre
    meta["substyle"] = normalized_substyle
    meta.setdefault("slots", {})

    for slot_id in target_slot_ids:
        if slot_id not in PROMPT_SLOT_MAP:
            continue
        slot = PROMPT_SLOT_MAP[slot_id]
        slot_path = _slot_file(project_root, slot_id)
        source = _default_slot_content(slot_id, normalized_genre, normalized_substyle)
        should_write = force or not slot_path.exists()

        if should_write:
            _write_text(slot_path, source["content"])

        previous_meta = meta["slots"].get(slot_id, {})
        meta["slots"][slot_id] = {
            "name": slot["name"],
            "group": slot["group"],
            "description": slot["description"],
            "filename": slot["filename"],
            "variables": slot["variables"],
            "source_path": source["source_path"],
            "customized": False if should_write else bool(previous_meta.get("customized", False)),
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
    meta.setdefault("version", 1)
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

    slot_path = _slot_file(project_root, slot_id)
    if slot_path.exists():
        return _read_text(slot_path)

    ensure_project_prompts(project_root, genre, substyle, slot_ids=[slot_id])
    return _read_text(slot_path)
