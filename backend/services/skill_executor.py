 
"""Skills 执行器 - 完整复用 .claude 目录中的 Skills 工作流"""

import sys
import json
import re
import asyncio
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional
from services.genre_catalog import (
    canonical_genre_id,
    canonical_substyle_id,
    get_genre_bucket,
    get_substyle_entry,
    get_conflict_examples,
    get_extra_prohibitions,
    get_positive_style,
    get_trope_keywords,
    get_knowledge_preferred_files,
    get_template_preferred_files,
    get_opening_instruction,
    get_template_aliases,
    GENERIC_POSITIVE_STYLE,
    GENERIC_OPENING_INSTRUCTION,
)
from services.project_prompt_store import get_project_prompt_content

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"
SKILLS_DIR = CLAUDE_DIR / "skills"
AGENTS_DIR = CLAUDE_DIR / "agents"
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
TEMPLATES_DIR = CLAUDE_DIR / "templates"

# 添加 scripts 目录到 Python 路径
sys.path.insert(0, str(SCRIPTS_DIR))


class SkillExecutor:
    """Skills 工作流执行器"""

    def __init__(self, project_root: Path = None, ai_service=None):
        self.project_root = project_root or PROJECT_ROOT
        self.ai_service = ai_service
        self.webnovel_dir = self.project_root / ".webnovel"
        self._file_locks: Dict[str, threading.RLock] = {}
        self._schema_ensure_chapter: int = -1

    def _debug_enabled(self) -> bool:
        flag = os.getenv("WEBNOVEL_DEBUG", "").strip().lower()
        return flag in {"1", "true", "yes", "on"}

    def _debug(self, message: str) -> None:
        if self._debug_enabled():
            print(message)

    def _lock_key(self, path: Path) -> str:
        try:
            return str(path.resolve())
        except Exception:
            return str(path)

    def _get_file_lock(self, path: Path) -> threading.RLock:
        key = self._lock_key(path)
        lock = self._file_locks.get(key)
        if lock is None:
            lock = threading.RLock()
            self._file_locks[key] = lock
        return lock

    @contextmanager
    def _locked_file(self, path: Path):
        lock = self._get_file_lock(path)
        with lock:
            yield

    def _safe_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        return str(value)

    def _normalize_entity_name(self, name: str) -> str:
        """统一实体名格式，避免重复建档与路径问题。"""
        text = self._safe_text(name).strip()
        text = text.replace("/", "-").replace("\\", "-")
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[\"'`]", "", text)
        return text.strip(" .，。；;:：")

    def _name_key(self, name: str) -> str:
        """角色别名匹配键：忽略空白和括号别名。"""
        norm = self._normalize_entity_name(name)
        norm = re.sub(r"\s+", "", norm)
        no_bracket = re.sub(r"[（(].*?[）)]", "", norm).strip()
        return no_bracket or norm

    def _infer_character_category(self, importance: str = "", identity: str = "") -> str:
        imp = self._safe_text(importance).lower()
        identity_l = self._safe_text(identity).lower()
        if "villain" in imp or "反派" in imp:
            return "反派角色"
        if "major" in imp or "主要" in imp:
            return "主要角色"
        if any(k in identity_l for k in ["敌", "反派", "邪", "仇", "刺客"]):
            return "反派角色"
        if any(k in identity_l for k in ["主角", "妻", "父", "母", "兄", "姐", "弟", "妹", "核心"]):
            return "主要角色"
        return "次要角色"

    def _iter_character_files(self) -> List[Path]:
        char_lib = self.project_root / "设定集" / "角色库"
        result: List[Path] = []
        for category in ["主要角色", "次要角色", "反派角色"]:
            cat_dir = char_lib / category
            if not cat_dir.exists():
                continue
            result.extend(sorted(cat_dir.glob("*.md")))
        return result

    def _find_character_file_by_name(self, name: str) -> Optional[Path]:
        """按精确名或别名键匹配现有角色档案。"""
        query = self._normalize_entity_name(name)
        if not query:
            return None

        query_key = self._name_key(query)
        for f in self._iter_character_files():
            stem = f.stem
            if stem == query:
                return f
            if self._name_key(stem) == query_key:
                return f
        return None

    def _find_entity_file_in_dir(self, lib_dir: Path, name: str) -> Optional[Path]:
        query = self._normalize_entity_name(name)
        if not query or not lib_dir.exists():
            return None
        query_key = self._name_key(query)
        for f in lib_dir.glob("*.md"):
            stem = f.stem
            if stem == query:
                return f
            if self._name_key(stem) == query_key:
                return f
        return None

    def _alias_key(self, name: str) -> str:
        """实体别名键：去掉常见前缀后用于弱匹配。"""
        text = self._normalize_entity_name(name)
        text = re.sub(r"\s+", "", text)
        text = re.sub(r"^(小|大|新|旧|老|初阶|初级|高级|基础|入门|简化|简易|残缺|伪)", "", text)
        return text

    def _common_suffix_len(self, a: str, b: str) -> int:
        ia = len(a) - 1
        ib = len(b) - 1
        n = 0
        while ia >= 0 and ib >= 0 and a[ia] == b[ib]:
            n += 1
            ia -= 1
            ib -= 1
        return n

    def _find_similar_entity_file_in_dir(self, lib_dir: Path, name: str) -> Optional[Path]:
        """保守弱匹配：仅在唯一候选时认定为同一实体，避免重复建档。"""
        query = self._normalize_entity_name(name)
        if not query or not lib_dir.exists():
            return None

        alias_q = self._alias_key(query)
        if len(alias_q) < 2:
            return None

        candidates: List[tuple[int, int, Path]] = []
        for f in sorted(lib_dir.glob("*.md")):
            stem = self._normalize_entity_name(f.stem)
            if not stem:
                continue
            alias_s = self._alias_key(stem)
            if not alias_s:
                continue
            suffix_len = self._common_suffix_len(alias_q, alias_s)
            if suffix_len < 2:
                continue
            if alias_q[-1] != alias_s[-1]:
                continue
            candidates.append((suffix_len, len(alias_s), f))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best = candidates[0]
        tied = [c for c in candidates if c[0] == best[0] and c[1] == best[1]]
        if len(tied) != 1:
            return None
        return best[2]

    def _extract_json_object(self, raw: str) -> Optional[Dict[str, Any]]:
        if not raw:
            return None

        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)

        # 1) 直接 JSON
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

        # 2) 代码块中的 JSON
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
        if fence_match:
            try:
                obj = json.loads(fence_match.group(1))
                return obj if isinstance(obj, dict) else None
            except Exception:
                pass

        # 3) 平衡花括号提取
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        obj = json.loads(candidate)
                        return obj if isinstance(obj, dict) else None
                    except Exception:
                        break
        return None

    async def _chat_json_with_retry(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        retries: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """请求 AI 并尽量得到可解析 JSON，对输出漂移做重试修复。"""
        if not self.ai_service:
            return None

        correction = ""
        for attempt in range(retries + 1):
            full_prompt = prompt if not correction else f"{prompt}\n\n{correction}"
            try:
                result = await self.ai_service.chat(
                    [{"role": "user", "content": full_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                obj = self._extract_json_object(result or "")
                if obj is not None:
                    return obj
                correction = (
                    "上次输出无法解析。请严格只输出一个 JSON 对象："
                    "不要代码块、不要解释、不要额外文本。"
                )
            except Exception as e:
                correction = f"上次请求失败（{e}）。请只输出一个合法 JSON 对象。"
        return None

    def _get_context_budgets(self, mode: str) -> Dict[str, int]:
        """统一上下文预算（字符级），避免各处硬编码截断失控。"""
        budgets: Dict[str, Dict[str, int]] = {
            "write": {
                "core_constraints": 2800,
                "genre_style": 1800,
                "genre_examples": 1200,
                "worldview": 1000,
                "power_system": 1000,
                "gold_finger": 1800,
                "scene_ref_each": 1200,
                "chapter_outline": 2400,
                "next_chapter_outline": 1600,
                "recent_context": 1200,
                "active_roster": 2400,
                "character_details": 3200,
                "realtime_status": 1800,
                "entity_libraries": 1800,
                "continuity_summary": 1800,
                "previous_ending": 600,
                "rag_scenes": 1400,
            },
            "outline_replan": {
                "world": 1200,
                "power": 1200,
                "char": 1200,
                "gold_finger": 1400,
                "entity_libraries": 1400,
                "genre_tropes": 1200,
                "genre_examples": 900,
                "current_outline": 12000,
                "guidance": 1600,
            },
            "outline_plan": {
                "volume_outline": 2600,
                "world": 1200,
                "power": 1200,
                "char": 1000,
                "gold_finger": 1400,
                "entity_libraries": 1400,
                "prev_volume_outline": 2600,
                "character_roster": 1800,
                "chapter_planning": 1200,
                "conflict_design": 1000,
                "genre_tropes": 1000,
                "genre_examples": 900,
            },
            "outline_polish": {
                "content": 12000,
                "requirements": 1800,
                "genre_examples": 900,
            },
            "outline_entity_extract": {
                "roster": 1800,
                "outline": 8000,
            },
            "polish": {
                "content": 10000,
                "suggestions": 1800,
                "guide": 1600,
                "typesetting": 1200,
                "genre_examples": 1000,
            },
            "extract_state": {
                "chunk_size": 5200,
                "chunk_overlap": 600,
                "max_tokens": 3600,
                "roster": 1800,
                "techniques": 1400,
            },
            "review": {
                "chapter_outline": 2200,
                "previous_ending": 1200,
                "active_roster": 2200,
                "gold_finger": 1400,
                "worldview": 1400,
                "realtime_status": 1400,
                "character_details": 3200,
                "entity_libraries": 1800,
                "content": 9000,
            },
            "continuity_summary": {
                "content": 9000,
            },
            "consistency_guard": {
                "outline": 2400,
                "next_outline": 1600,
                "reference": 2600,
                "chunk_size": 4200,
                "chunk_overlap": 500,
                "scan_max_tokens": 1800,
                "fix_max_tokens": 12000,
            },
        }
        return budgets.get(mode, {})

    def _truncate_text(self, text: str, max_chars: int, keep_tail: bool = True) -> str:
        """按预算截断文本；默认保留头尾，减少关键结尾信息丢失。"""
        raw = self._safe_text(text)
        if max_chars <= 0 or len(raw) <= max_chars:
            return raw

        if keep_tail and max_chars >= 120:
            marker = "\n...(中间省略)...\n"
            head = int(max_chars * 0.6)
            tail = max_chars - head - len(marker)
            if tail < 20:
                tail = 20
                head = max_chars - len(marker) - tail
            return f"{raw[:head]}{marker}{raw[-tail:]}"

        return raw[:max_chars]

    def _compress_outline_for_prompt(self, content: str, max_chars: int = 12000) -> str:
        """大纲压缩：优先保留卷/章标题及其邻近条目，再整体截断。"""
        raw = self._safe_text(content)
        if len(raw) <= max_chars:
            return raw

        lines = raw.splitlines()
        kept: List[str] = []
        carry = 0
        for line in lines:
            s = line.strip()
            if re.match(r"^#{1,6}\s*", s) or re.match(r"^\*?\*?第\s*\d+\s*[章节卷]", s) or re.match(r"^第\s*\d+\s*[章节卷]", s):
                kept.append(line)
                carry = 4
                continue
            if carry > 0 and s:
                kept.append(line)
                carry -= 1

        compressed = "\n".join(kept).strip() if kept else raw
        return self._truncate_text(compressed, max_chars, keep_tail=False)

    def _format_rag_related_scenes(self, related_scenes: List[Dict[str, Any]], max_chars: int) -> str:
        if not related_scenes:
            return ""
        rows: List[str] = []
        for item in related_scenes[:3]:
            chapter = item.get("chapter", "?")
            scene = item.get("scene", "?")
            score_raw = item.get("score")
            try:
                score = f"{float(score_raw):.3f}"
            except Exception:
                score = self._safe_text(score_raw) or "?"
            snippet = self._safe_text(item.get("content", ""))
            rows.append(f"- 第{chapter}章 场景{scene}（相关度 {score}）：{snippet}")
        return self._truncate_text("\n".join(rows), max_chars, keep_tail=False)

    def _normalize_genre_key(self, genre: str) -> str:
        text = self._safe_text(genre).strip()
        text_l = text.lower()
        bucket = get_genre_bucket(text)
        if bucket:
            return bucket
        alias_map = {
            "玄幻": "xuanhuan",
            "修仙": "xuanhuan",
            "仙侠": "xuanhuan",
            "奇幻": "xuanhuan",
            "xuanhuan": "xuanhuan",
            "xianxia": "xuanhuan",
            "系统流": "xuanhuan",
            "武侠": "xuanhuan",
            "规则怪谈": "rules-mystery",
            "怪谈": "rules-mystery",
            "悬疑": "rules-mystery",
            "惊悚": "rules-mystery",
            "恐怖": "rules-mystery",
            "rules-mystery": "rules-mystery",
            "黑暗题材": "dark",
            "黑暗": "dark",
            "dark": "dark",
            "狗血言情": "dog-blood-romance",
            "替身文": "dog-blood-romance",
            "现代言情": "dog-blood-romance",
            "言情": "dog-blood-romance",
            "romance": "dog-blood-romance",
            "dog-blood-romance": "dog-blood-romance",
            "古言": "period-drama",
            "古代言情": "period-drama",
            "宫斗": "period-drama",
            "历史": "period-drama",
            "period-drama": "period-drama",
            "现实题材": "realistic",
            "现实": "realistic",
            "现实向": "realistic",
            "都市": "realistic",
            "都市异能": "realistic",
            "都市现实": "realistic",
            "科幻": "realistic",
            "军事": "realistic",
            "体育": "realistic",
            "realistic": "realistic",
            "知乎短篇": "zhihu-short",
            "短篇": "zhihu-short",
            "轻小说": "zhihu-short",
            "zhihu-short": "zhihu-short",
        }
        if text in alias_map:
            return alias_map[text]

        # 兼容 玄幻流/仙侠爽文/规则怪谈向 等题材变体写法
        if any(k in text for k in ["玄幻", "修仙", "仙侠", "奇幻", "武侠", "系统流"]) or any(k in text_l for k in ["xuanhuan", "xianxia"]):
            return "xuanhuan"
        if any(k in text for k in ["规则怪谈", "怪谈", "悬疑", "惊悚", "恐怖"]) or "mystery" in text_l:
            return "rules-mystery"
        if any(k in text for k in ["狗血言情", "替身", "追妻火葬场", "甜宠", "虐恋"]) or "romance" in text_l:
            return "dog-blood-romance"
        if any(k in text for k in ["古言", "宫斗", "宅斗", "朝堂", "历史"]) or "period" in text_l:
            return "period-drama"
        if any(k in text for k in ["现实", "都市", "职场", "社会议题", "科幻", "军事", "体育"]) or "realistic" in text_l:
            return "realistic"
        if any(k in text for k in ["知乎短篇", "短篇", "反转短文", "轻小说"]) or "zhihu" in text_l:
            return "zhihu-short"
        if "黑暗" in text or "dark" in text_l:
            return "dark"

        return text_l

    def _is_weird_mystery_genre(self, genre: str) -> bool:
        key = self._normalize_genre_key(genre)
        if key == "rules-mystery":
            return True
        text = self._safe_text(genre)
        return any(k in text for k in ["规则怪谈", "怪谈", "诡异", "惊悚", "恐怖"])

    def _should_block_weird_style_terms(self, genre: str, *signals: str) -> bool:
        """非怪谈题材默认拦截诡异流术语；仅在显式声明融合怪谈时放行。"""
        if self._is_weird_mystery_genre(genre):
            return False

        merged = "\n".join(self._safe_text(s) for s in signals if s)
        allow_flags = ["允许怪谈元素", "融合怪谈", "怪谈支线", "诡异支线"]
        return not any(flag in merged for flag in allow_flags)

    def _filter_scenes_by_forbidden_terms(self, scenes: List[Dict[str, Any]], forbidden_terms: List[str]) -> List[Dict[str, Any]]:
        if not scenes or not forbidden_terms:
            return scenes
        filtered: List[Dict[str, Any]] = []
        for item in scenes:
            snippet = self._safe_text(item.get("content", "")).lower()
            if any(term.lower() in snippet for term in forbidden_terms):
                continue
            filtered.append(item)
        return filtered

    def _extract_markdown_section(self, content: str, heading_keywords: List[str]) -> str:
        raw = self._safe_text(content)
        if not raw or not heading_keywords:
            return ""
        lines = raw.splitlines()

        start = -1
        for i, line in enumerate(lines):
            s = line.strip()
            if not re.match(r"^##(?!#)\s*", s):
                continue
            if any(k in s for k in heading_keywords):
                start = i
                break
        if start < 0:
            return ""

        end = len(lines)
        for j in range(start + 1, len(lines)):
            if re.match(r"^##(?!#)\s*", lines[j].strip()):
                end = j
                break
        return "\n".join(lines[start:end]).strip()

    def _get_effective_substyle(self, genre: str, substyle: str = "") -> str:
        effective = canonical_substyle_id(genre, substyle)
        if effective:
            return effective
        return canonical_substyle_id(genre, self._get_project_substyle())

    def _build_substyle_instruction(self, genre: str, substyle: str = "", stage: str = "writing") -> str:
        effective = self._get_effective_substyle(genre, substyle)
        item = get_substyle_entry(genre, effective)
        if not item:
            return ""

        lines = [
            f"【子风格锁定】当前阶段：{stage}。",
            f"当前题材：{canonical_genre_id(genre)}｜子风格：{item.get('name', effective)}。",
        ]
        description = self._safe_text(item.get("description", "")).strip()
        if description:
            lines.append(f"核心方向：{description}")

        focus = item.get("focus") or []
        if focus:
            lines.append("必须体现：")
            lines.extend(f"{idx}. {self._safe_text(point)}" for idx, point in enumerate(focus, start=1))

        avoid = item.get("avoid") or []
        if avoid:
            lines.append("明确回避：")
            lines.extend(f"- {self._safe_text(point)}" for point in avoid)

        return "\n".join(lines)

    def _extract_substyle_example_snippets(
        self,
        content: str,
        keywords: List[str],
        max_items: int = 5,
        max_chars: int = 900,
    ) -> str:
        raw = self._safe_text(content)
        if not raw or not keywords:
            return ""

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
        matched: List[str] = []
        seen: set[str] = set()
        lowered_keywords = [k.lower() for k in keywords if k]

        for para in paragraphs:
            compact = re.sub(r"\s+", " ", para)
            lower = compact.lower()
            if not any(k in lower for k in lowered_keywords):
                continue
            compact = re.sub(r"`([^`]+)`", r"\1", compact)
            compact = re.sub(r"\*\*([^*]+)\*\*", r"\1", compact)
            compact = re.sub(r"^[-*]\s*", "", compact)
            compact = compact.strip()
            if len(compact) < 18:
                continue
            key = compact.lower()
            if key in seen:
                continue
            seen.add(key)
            matched.append(compact)
            if len(matched) >= max_items:
                break

        if not matched:
            return ""

        merged = "\n".join(f"- {item}" for item in matched)
        return self._truncate_text(merged, max_chars, keep_tail=False)

    def _load_substyle_examples(self, genre: str, substyle: str = "", max_chars: int = 900) -> str:
        effective = self._get_effective_substyle(genre, substyle)
        item = get_substyle_entry(genre, effective)
        if not item:
            return ""

        keywords = list(item.get("keywords") or [])
        if not keywords:
            return ""

        snippets: List[str] = []
        used = 0
        sources: List[tuple[str, str]] = []

        template_text = self._load_genre_template(genre)
        if template_text:
            sources.append(("题材模板", template_text))

        guide_text = self._load_genre_style_guide(genre, max_chars=2200)
        if guide_text:
            sources.append(("题材指南", guide_text))

        genre_dir = self._resolve_genre_knowledge_dir(genre)
        if genre_dir:
            for path in sorted(genre_dir.glob("*.md"))[:4]:
                text = self._read_file(path)
                if text:
                    sources.append((path.stem, text))

        budget_each = max(220, max_chars // max(1, min(len(sources), 3)))
        for source_name, source_text in sources:
            part = self._extract_substyle_example_snippets(
                source_text,
                keywords,
                max_items=3,
                max_chars=budget_each,
            )
            if not part:
                continue
            block = f"## {source_name}\n{part}"
            if used + len(block) > max_chars and snippets:
                break
            snippets.append(block)
            used += len(block)
            if len(snippets) >= 3:
                break

        if snippets:
            return self._truncate_text("\n\n".join(snippets), max_chars, keep_tail=False)

        focus = item.get("focus") or []
        if focus:
            fallback = "\n".join(f"- {self._safe_text(point)}" for point in focus)
            return self._truncate_text(fallback, max_chars, keep_tail=False)
        return ""

    def _load_genre_trope_focus(self, genre: str, source: str = "", max_chars: int = 1200) -> str:
        """从通用套路库中提取当前题材对应片段，避免混入其他题材套路。"""
        raw = self._safe_text(source).strip()
        if not raw:
            raw = self._load_reference("webnovel-init", "genre-tropes.md")
        if not raw:
            return ""

        key = self._normalize_genre_key(genre)
        keywords = get_trope_keywords(key)
        section = self._extract_markdown_section(raw, keywords) if keywords else ""

        # 未命中时，回退到题材模板（仍然是按题材）
        if not section:
            section = self._load_genre_template(genre)
        if not section:
            # 不再回退到混合套路总表，避免跨题材污染
            return ""

        return self._truncate_text(section, max_chars, keep_tail=False)

    def _resolve_genre_knowledge_dir(self, genre: str) -> Optional[Path]:
        key = self._normalize_genre_key(genre)
        if not key:
            return None
        genre_dir = CLAUDE_DIR / "genres" / key
        return genre_dir if genre_dir.exists() else None

    def _extract_genre_example_snippets(self, content: str, max_items: int = 8, max_chars: int = 1200) -> str:
        raw = self._safe_text(content)
        if not raw:
            return ""

        lines = raw.splitlines()
        snippets: List[str] = []
        seen: set[str] = set()

        for i, line in enumerate(lines):
            s = line.strip()
            if not s:
                continue
            if not re.search(r"(示例|例子|样例|范例)", s):
                continue
            if re.search(r"(错误示例|反例|反面示例|❌)", s):
                continue
            if s.startswith("|") or s.count("|") >= 2:
                continue

            block: List[str] = [s]
            for j in range(i + 1, min(len(lines), i + 8)):
                nxt = lines[j].strip()
                if not nxt:
                    if len(block) >= 3:
                        break
                    continue
                if re.match(r"^#{1,4}\s*", nxt):
                    break
                if re.search(r"(示例|例子|样例|范例)", nxt) and len(block) >= 2:
                    break
                if re.search(r"(错误示例|反例|反面示例|❌)", nxt):
                    break
                if nxt.startswith("|") or nxt.count("|") >= 2:
                    continue
                if nxt.startswith("```"):
                    continue
                block.append(nxt)
                if len(" ".join(block)) >= 180:
                    break

            candidate = " ".join(block).strip()
            candidate = re.sub(r"```+", "", candidate)
            candidate = re.sub(r"`([^`]+)`", r"\1", candidate)
            candidate = re.sub(r"\*\*([^*]+)\*\*", r"\1", candidate)
            candidate = re.sub(r"^[-*]\s*", "", candidate)
            candidate = re.sub(r"\s{2,}", " ", candidate)
            if len(candidate) < 18:
                continue
            if re.search(r"(错误示例|反例|反面示例|❌)", candidate):
                continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            snippets.append(candidate)
            if len(snippets) >= max_items:
                break

        if not snippets:
            return ""

        merged = "\n".join(f"- {item}" for item in snippets)
        return self._truncate_text(merged, max_chars, keep_tail=False)

    def _load_genre_style_examples(self, genre: str, substyle: str = "", max_chars: int = 1200) -> str:
        """按题材动态加载"示例片段"，用于风格对齐（只学表达，不照抄）。"""
        genre_dir = self._resolve_genre_knowledge_dir(genre)
        effective_substyle = self._get_effective_substyle(genre, substyle)

        key = self._normalize_genre_key(genre)
        ordered = get_knowledge_preferred_files(key)
        files: List[Path] = []
        if genre_dir:
            for name in ordered:
                p = genre_dir / name
                if p.exists():
                    files.append(p)
            if not files:
                files = sorted(genre_dir.glob("*.md"))[:3]

        snippets: List[str] = []
        used = 0
        budget_each = max(260, max_chars // max(1, min(3, len(files) if files else 1)))
        for p in files[:3]:
            text = self._read_file(p)
            if not text:
                continue
            part = self._extract_genre_example_snippets(text, max_items=4, max_chars=budget_each)
            if not part:
                continue
            header = f"## {p.stem}\n{part}"
            cost = len(header)
            if used + cost > max_chars and snippets:
                break
            snippets.append(header)
            used += cost

        substyle_examples = self._load_substyle_examples(
            genre,
            effective_substyle,
            max_chars=max(260, min(700, max_chars // 2)),
        )
        if substyle_examples:
            snippets.insert(0, f"## 子风格示例（{effective_substyle}）\n{substyle_examples}")

        merged = "\n\n".join(snippets).strip()
        if merged:
            return self._truncate_text(merged, max_chars, keep_tail=False)

        # 兜底：至少提供当前题材文档片段
        fallback = self._load_substyle_examples(genre, effective_substyle, max_chars=max_chars)
        if fallback:
            return fallback
        fallback = self._load_genre_style_guide(genre, max_chars=max_chars)
        return fallback or ""

    def _build_genre_guard_instruction(self, genre: str, stage: str = "writing") -> str:
        key = self._normalize_genre_key(genre)
        examples = get_conflict_examples(key)
        base = (
            f"【题材锁定（最高优先级）】当前题材：{genre}。\n"
            f"当前阶段：{stage}。\n"
            f"冲突、危机、张力必须来自题材本身（{examples}）。\n"
            f'环境描写、氛围渲染必须服务于"{genre}"核心阅读体验。'
        )
        prohibitions = get_extra_prohibitions(key)
        if prohibitions:
            genre_label = genre or key
            base += f"\n【{genre_label}额外禁令】\n{prohibitions}"
        return base

    def _build_genre_positive_style_instruction(self, genre: str, stage: str = "writing") -> str:
        key = self._normalize_genre_key(genre)
        style_text = get_positive_style(key)
        genre_label = genre or key
        return f"【{genre_label}正向风格锚定】当前阶段：{stage}。\n{style_text}"

    def _build_opening_chapter_instruction(self, genre: str, substyle: str, chapter: int, chapter_outline: str = "") -> str:
        """给第1章补一段条件式约束，只强化大纲已有内容。"""
        if chapter != 1:
            return ""

        key = self._normalize_genre_key(genre)
        substyle_text = self._safe_text(substyle)
        outline_hint = "以下要求只用于强化本章大纲已有内容，禁止为了满足节奏私自新增事件、收益、反制、机缘或结局。"

        specific = get_opening_instruction(key)
        if specific:
            return (
                "【第1章开篇约束（以大纲为准）】\n"
                f"{outline_hint}\n"
                f"{specific}"
            )
        # 通用回退
        return (
            f"【第1章开篇约束（以大纲为准）】当前子风格：{substyle_text or '未指定'}。\n"
            f"{outline_hint}\n"
            f"{GENERIC_OPENING_INSTRUCTION}"
        )

    def _has_abrupt_tail(self, content: str) -> bool:
        """检测正文是否疑似半句截断。"""
        text = self._safe_text(content).rstrip()
        if not text or len(text) < 120:
            return False
        if re.search(r'[。！？!?…】）》」』\u201c\u201d"\x27]\s*$', text):
            return False

        tail = text[-90:]
        # 典型未完成尾部：停在逗号/冒号/引导词/连接词后
        if re.search(r"[，、:：；;\-—]\s*$", text):
            return True
        if re.search(r"(目光|声音|身影|下一瞬|仿佛|像是|他|她|它|而|但|却|并且|于是)\s*$", tail):
            return True
        # 末尾没有终止标点，且长度较长，按不完整处理
        return True

    async def _repair_abrupt_tail(
        self,
        chapter: int,
        genre: str,
        chapter_outline: str,
        content: str,
    ) -> str:
        """在不改动前文的前提下补全被截断的结尾。"""
        raw = self._safe_text(content).rstrip()
        if not raw or not self._has_abrupt_tail(raw) or not self.ai_service:
            return raw

        style_bundle, normalized_genre, normalized_substyle = self._build_stage_style_bundle(
            genre,
            self._get_project_substyle(),
            stage="结尾补写",
            genre_style_chars=500,
            genre_examples_chars=400,
            substyle_examples_chars=300,
        )
        substyle_display = normalized_substyle or "默认子风格"
        style_section = f"【当前阶段题材协议】\n{style_bundle}\n\n" if style_bundle else ""

        prompt = f"""{style_section}你是网文总编。下面正文疑似在结尾被截断，请只补写结尾收束段。

【硬性要求】
1. 只补写结尾 1-4 句，不得改写前文；
2. 严格符合题材"{normalized_genre}"与子风格"{substyle_display}"的当前阶段创作协议，不得回切旧题材腔调；
3. 延续本章大纲，不越界写到下一章核心事件；
4. 必须以完整句结束（句号/问号/感叹号/省略号）。

【本章大纲（节选）】
{self._truncate_text(chapter_outline, 1200, keep_tail=False)}

【正文末尾片段】
{self._truncate_text(raw, 1600, keep_tail=True)}

请直接输出"补写内容"，不要解释。"""
        try:
            appendix = await self.ai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=380,
            )
            appendix = self._safe_text(appendix).strip()
            if not appendix:
                return raw
            # 防止模型整段重写全文
            if len(appendix) > 900 or raw[:120] in appendix:
                return raw
            if appendix in raw:
                return raw
            if not re.search(r'[。！？!?…】）》」』\u201c\u201d"\x27]\s*$', appendix):
                appendix = appendix.rstrip() + "。"
            return f"{raw}\n{appendix}".strip()
        except Exception:
            return raw

    def _split_text_chunks(self, text: str, chunk_size: int, overlap: int = 0) -> List[str]:
        """将长文本切分为带重叠窗口，减少长章抽取遗漏。"""
        raw = self._safe_text(text)
        if not raw:
            return []
        if chunk_size <= 0 or len(raw) <= chunk_size:
            return [raw]

        overlap = max(0, min(overlap, chunk_size // 3))
        step = max(1, chunk_size - overlap)
        chunks: List[str] = []
        start = 0
        while start < len(raw):
            end = min(len(raw), start + chunk_size)
            piece = raw[start:end]

            # 优先在自然边界切断，避免句子被截断
            if end < len(raw):
                boundary = max(piece.rfind("\n"), piece.rfind("。"), piece.rfind("！"), piece.rfind("？"))
                if boundary >= max(0, len(piece) - 260):
                    end = start + boundary + 1
                    piece = raw[start:end]

            piece = piece.strip()
            if piece:
                chunks.append(piece)
            if end >= len(raw):
                break
            start = max(0, end - overlap)

        return chunks

    def _split_content_for_rag(self, content: str, chunk_size: int = 1800, overlap: int = 200) -> List[Dict[str, Any]]:
        """将正文切分为可索引场景，避免 scene_index 恒定为 1。"""
        pieces = self._split_text_chunks(content, chunk_size=chunk_size, overlap=overlap)
        result: List[Dict[str, Any]] = []
        for idx, piece in enumerate(pieces, start=1):
            text = self._safe_text(piece).strip()
            if not text:
                continue
            result.append({"scene_index": idx, "content": text})
        if not result:
            fallback = self._safe_text(content).strip()
            if fallback:
                result.append({"scene_index": 1, "content": fallback})
        return result

    def _is_word_char(self, ch: str) -> bool:
        if not ch:
            return False
        return bool(re.match(r"[0-9A-Za-z_\u4e00-\u9fff]", ch))

    def _replace_term_safely(self, content: str, src: str, dst: str) -> tuple[str, int]:
        """保守替换：仅在边界清晰的位置替换，避免 `小明` 命中 `小明月`。"""
        if not content or not src or src == dst:
            return content, 0

        wraps = [
            ("【", "】"),
            ("「", "」"),
            ("『", "』"),
            (""", """),
            ("\"", "\""),
            ("'", "'"),
            ("`", "`"),
            ("**", "**"),
        ]
        replaced = content
        wrapped_hits = 0
        for left, right in wraps:
            wrapped_src = f"{left}{src}{right}"
            wrapped_dst = f"{left}{dst}{right}"
            c = replaced.count(wrapped_src)
            if c <= 0:
                continue
            replaced = replaced.replace(wrapped_src, wrapped_dst)
            wrapped_hits += c

        pieces: List[str] = []
        hits = 0
        last = 0
        for m in re.finditer(re.escape(src), replaced):
            start, end = m.span()
            prev_ch = replaced[start - 1] if start > 0 else ""
            next_ch = replaced[end] if end < len(replaced) else ""
            if self._is_word_char(prev_ch) or self._is_word_char(next_ch):
                continue
            pieces.append(replaced[last:start])
            pieces.append(dst)
            last = end
            hits += 1
        if hits > 0:
            pieces.append(replaced[last:])
            replaced = "".join(pieces)
        return replaced, wrapped_hits + hits

    def _sanitize_reader_facing_content(self, content: str) -> tuple[str, Dict[str, int]]:
        """清理正文中的记录型标签，避免把状态记账内容直接展示给读者。"""
        raw = self._safe_text(content)
        if not raw:
            return raw, {"removed_lines": 0, "removed_inline_tags": 0}

        # 仅移除"记录口径"标签；普通系统提示（任务、奖励、面板等）不在该列表中。
        labels = r"(?:伤亡|消耗|状态|战损|资源(?:变化|消耗)?|统计|损失|剩余|阵亡|折损|战果|结算|记录)"
        line_pat = re.compile(rf"^\s*(?:[-*]\s*)?【\s*{labels}\s*[：:][^】]{{1,140}}】\s*$")
        inline_pat = re.compile(rf"【\s*{labels}\s*[：:][^】]{{1,140}}】")

        removed_lines = 0
        removed_inline_tags = 0
        kept_lines: List[str] = []

        for line in raw.splitlines():
            if line_pat.match(line):
                removed_lines += 1
                continue
            cleaned, cnt = inline_pat.subn("", line)
            if cnt > 0:
                removed_inline_tags += cnt
                cleaned = re.sub(r"\s{2,}", " ", cleaned).rstrip()
            kept_lines.append(cleaned)

        sanitized = "\n".join(kept_lines)
        sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip()
        if not sanitized:
            # 兜底：避免误清洗导致整章为空。
            return raw, {"removed_lines": 0, "removed_inline_tags": 0}

        return sanitized, {"removed_lines": removed_lines, "removed_inline_tags": removed_inline_tags}

    def _enforce_chapter_length_cap(
        self,
        content: str,
        min_chars: int = 2800,
        max_chars: int = 4000,
    ) -> tuple[str, Dict[str, int]]:
        """章节字数硬上限约束：超限时在自然边界裁剪，避免失控到 6k+。"""
        raw = self._safe_text(content).strip()
        raw_len = len(raw)
        if not raw:
            return raw, {"original": 0, "final": 0, "trimmed": 0}
        if max_chars <= 0 or raw_len <= max_chars:
            return raw, {"original": raw_len, "final": raw_len, "trimmed": 0}

        clipped = raw[:max_chars]
        boundaries = [
            clipped.rfind("\n\n"),
            clipped.rfind("\n"),
            clipped.rfind("。"),
            clipped.rfind("！"),
            clipped.rfind("？"),
            clipped.rfind("；"),
        ]
        boundary = max(boundaries)
        if boundary >= int(max_chars * 0.75):
            clipped = clipped[:boundary + 1]

        clipped = clipped.strip()
        # 防止边界裁剪过短导致内容断裂感过强
        if len(clipped) < min_chars:
            clipped = raw[:max_chars].strip()

        final_len = len(clipped)
        if not clipped:
            return raw, {"original": raw_len, "final": raw_len, "trimmed": 0}
        return clipped, {"original": raw_len, "final": final_len, "trimmed": int(final_len < raw_len)}

    def _build_polish_prompt(self, chapter_id: int, content: str, suggestions: str, mode: str = "rewrite") -> str:
        """构建润色 prompt（统一非流式与流式），并按预算压缩上下文。"""
        polish_budget = self._get_context_budgets("polish")
        genre = self._get_project_genre()
        substyle = self._get_project_substyle()
        chapter_outline = self._find_chapter_outline(chapter_id)
        genre_writer_prompt = self._load_genre_writer_prompt(genre, stage="正文润色")
        substyle_writer_prompt = self._load_substyle_writer_prompt(genre, substyle, stage="正文润色")
        genre_guard = self._build_genre_guard_instruction(genre, stage="正文润色")
        positive_style_instruction = self._build_genre_positive_style_instruction(genre, stage="正文润色")
        substyle_instruction = self._build_substyle_instruction(genre, substyle, stage="正文润色")
        polish_guide = self._truncate_text(
            self._load_reference("webnovel-write", "polish-guide.md"),
            polish_budget.get("guide", 1600),
            keep_tail=False,
        )
        typesetting = self._truncate_text(
            self._load_reference("webnovel-write", "writing/typesetting.md"),
            polish_budget.get("typesetting", 1200),
            keep_tail=False,
        )
        suggestions_for_prompt = self._truncate_text(
            suggestions,
            polish_budget.get("suggestions", 1800),
            keep_tail=True,
        )
        genre_examples_for_prompt = self._truncate_text(
            self._load_genre_style_examples(genre, substyle, max_chars=polish_budget.get("genre_examples", 1000)),
            polish_budget.get("genre_examples", 1000),
            keep_tail=False,
        )
        substyle_examples_for_prompt = self._truncate_text(
            self._load_substyle_examples(genre, substyle, max_chars=polish_budget.get("genre_examples", 700)),
            polish_budget.get("genre_examples", 700),
            keep_tail=False,
        )
        content_for_prompt = self._truncate_text(
            content,
            polish_budget.get("content", 10000),
            keep_tail=True,
        )
        chapter_outline_for_prompt = self._truncate_text(chapter_outline, 1800, keep_tail=False)

        if mode == "targeted_fix":
            return f"""你是资深网文审校编辑。你的任务是根据【审查意见】对第{chapter_id}章进行**定点修订**，不是整章重写。

【修订原则（必须严格遵守）】
1. 只修改【审查意见】明确指出的问题，未命中的段落、台词、节奏和表达能不动就不动。
2. 保留原有剧情顺序、段落结构、人物关系、情绪走向和有效爽点，禁止借机重写成另一个版本。
3. 先修复设定冲突、角色/地点/术语错误、逻辑漏洞、连续性问题，再处理语句不顺或冗余。
4. 如果审查意见中某条与大纲或正文上下文冲突，以大纲、设定和正文事实为准，不要机械硬改。
5. 不得新增下一章剧情，不得擅自扩写，不得把局部修订演变成洗稿式重写。
6. 即使只改少量位置，也必须返回**完整正文**，方便前端直接替换。
7. 优先做“句内替换”和“局部短句增删”，不要整段改写；能改 1 句就不要改 1 段。
8. 非必要禁止重排段落顺序，禁止整体换文风，禁止把原文 50% 以上内容改成新写法。
9. 若审查意见主要是术语、设定、角色称谓、地点、时间线错误，应只修正对应词句，不要顺手润色整章。

【当前题材】
题材：{genre}
子风格：{substyle or "（无）"}

【本章大纲（防止修偏）】
{chapter_outline_for_prompt if chapter_outline_for_prompt else "（无）"}

【审查意见】
{suggestions_for_prompt.strip() if suggestions_for_prompt.strip() else "（无）"}

【排版要求】
{typesetting if typesetting else "段落清晰，标点规范。"}

【原文】
{content_for_prompt}

        【输出要求】
1. 只输出修订后的完整正文，不要解释修改点，不要写“已根据意见修改”之类废话。
2. 未命中的句段尽量保持原样，避免整章风格漂移。
3. 你的目标不是“写得更华丽”，而是“在原文基础上修对问题”。
4. 记录标签禁入正文：严禁输出【伤亡：...】、【消耗：...】、【状态：...】等记账型标签。"""

        # 主路径：从 slot 系统加载模板
        polish_template = self._load_project_prompt("polish")
        if polish_template:
            return self._format_prompt_text(
                polish_template,
                chapter_id=str(chapter_id),
                genre=genre,
                substyle=substyle,
                genre_writer_prompt=genre_writer_prompt or "",
                substyle_writer_prompt=substyle_writer_prompt or "",
                genre_guard=genre_guard or "",
                positive_style_instruction=positive_style_instruction or "",
                substyle_instruction=substyle_instruction or "",
                chapter_outline=chapter_outline_for_prompt or "（无）",
                substyle_examples=substyle_examples_for_prompt or "（无）",
                genre_examples=genre_examples_for_prompt or "（无）",
                suggestions=suggestions_for_prompt.strip() if suggestions_for_prompt.strip() else "（无特定意见，请按【核心指令】进行商业阅读效率提升）",
                polish_guide=polish_guide or "保持原文风格，优化文笔，修正错别字。",
                typesetting=typesetting or "段落清晰，标点规范。",
                content=content_for_prompt,
            )

        # Fallback：原始硬编码
        return f"""你是番茄小说/起点读书 Top100 数据团队的商业网文润色编辑。你的任务是**深度润色**第{chapter_id}章，目标是最大化读者留存率和完读率。

【核心指令：必须重写！】
即使【修改意见】为空，你也**必须**对原文进行全方位的提升！绝不允许原封不动地返回！
请从以下维度进行优化：
1. **阅读速度**：削除一切减速句（冗余心理、重复描写、无效过渡），确保每段都在推进信息或情绪，读者不会停下来重读。
2. **爽点密度**：每 800 字至少安排一个满足感落点（获得、反转、压制、揭秘、升级），不允许出现连续 800 字以上的"空转区"。
3. **钩子布局**：段末埋微悬念（一句未完的话、一个反常细节、一个即将揭晓的信息），章末设强断点（重大转折、新威胁出现、关键抉择前夕）。
4. **节奏节拍**：动作/对话/内心三拍交替，避免单一叙述模式连续超过 3 段；对话要短促有力，动作要具体可视化。

【题材锁定（最高优先级）】
当前题材：{genre}
当前子风格：{substyle}
{genre_writer_prompt if genre_writer_prompt else ""}
{substyle_writer_prompt if substyle_writer_prompt else ""}
{genre_guard}
{positive_style_instruction}
{substyle_instruction}

【本章大纲（用于防跑偏）】
{chapter_outline_for_prompt if chapter_outline_for_prompt else "（无）"}

【子风格示例（按当前子风格抽取）】
{substyle_examples_for_prompt if substyle_examples_for_prompt else "（无）"}

【题材示例（按当前题材动态加载）】
{genre_examples_for_prompt if genre_examples_for_prompt else "（无）"}
要求：只学习表达节奏与语气，不要照抄句子。

【修改意见（用户指定）】
{suggestions_for_prompt if suggestions_for_prompt.strip() else "（无特定意见，请按【核心指令】进行商业阅读效率提升）"}

【润色指南】
{polish_guide if polish_guide else "保持原文风格，优化文笔，修正错别字。"}

【排版要求】
{typesetting if typesetting else "段落清晰，标点规范。"}

【待润色内容（已压缩）】
{content_for_prompt}

**输出要求（严格遵守）**：
1. **仅输出润色后的正文**，不要包含"好的"、"这是润色后的内容"等任何废话。
2. **必须产生实质性的变化**，不要只是改标点或换个别词。
3. **严禁删减关键剧情**，但可以大幅度优化描写方式。
4. 格式必须符合【排版要求】。
5. **记录标签禁入正文**：严禁输出【伤亡：...】、【消耗：...】、【状态：...】等记账型标签。"""

    def _build_targeted_fix_patch_prompt(self, chapter_id: int, content: str, suggestions: str) -> str:
        """构建定点修补 prompt：要求模型返回局部替换补丁，而不是整章重写。"""
        genre = self._get_project_genre()
        substyle = self._get_project_substyle()
        chapter_outline = self._truncate_text(self._find_chapter_outline(chapter_id), 1800, keep_tail=False)
        typesetting = self._truncate_text(
            self._load_reference("webnovel-write", "writing/typesetting.md"),
            1200,
            keep_tail=False,
        )
        content_for_prompt = self._truncate_text(content, 12000, keep_tail=True)
        suggestions_for_prompt = self._truncate_text(suggestions, 2400, keep_tail=True)
        return f"""你是资深小说审校编辑。你的任务不是重写第{chapter_id}章，而是基于【审查意见】对原文做**最小必要修改**。

【核心原则】
1. 只能做“定点修补”，禁止整章重写，禁止整体改文风。
2. 优先修改术语、设定、人名、地点、时间线、逻辑错误；其次才是局部病句。
3. 能改 1 句就不要改 1 段；能替换 10 个字就不要重写 100 个字。
4. 未命中的句段必须保持原样。
5. 每条补丁里的 original 必须是原文中连续出现、可以直接精确匹配的一段文本。
6. original 应尽量唯一，建议 15-120 字；replacement 只做必要修正，不要扩写。
7. 如果无需修改，返回空 edits。

【当前题材】
题材：{genre}
子风格：{substyle or "（无）"}

【本章大纲】
{chapter_outline if chapter_outline else "（无）"}

【审查意见】
{suggestions_for_prompt if suggestions_for_prompt else "（无）"}

【排版要求】
{typesetting if typesetting else "段落清晰，标点规范。"}

【原文】
{content_for_prompt}

请只输出合法 JSON 对象，不要输出 Markdown 代码块，不要解释：
{{
  "edits": [
    {{
      "original": "原文中需要替换的连续片段",
      "replacement": "修正后的片段",
      "reason": "简短说明"
    }}
  ]
}}
"""

    def _extract_json_object_text(self, raw: str) -> str:
        """从模型输出中提取 JSON 对象文本。"""
        text = self._safe_text(raw).strip()
        if not text:
            return ""
        if text.startswith("{") and text.endswith("}"):
            return text

        fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1].strip()
        return text

    def _apply_targeted_fix_edits(self, content: str, edits: List[Dict[str, Any]]) -> tuple[str, Dict[str, Any]]:
        """按局部补丁替换原文，避免整章重写。"""
        updated = self._safe_text(content)
        applied: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []

        for item in edits or []:
            if not isinstance(item, dict):
                continue
            original = self._safe_text(item.get("original", ""))
            replacement = self._safe_text(item.get("replacement", ""))
            reason = self._safe_text(item.get("reason", "")).strip()

            if not original.strip():
                skipped.append({"reason": reason or "original 为空", "original": original[:80]})
                continue
            if original == replacement:
                skipped.append({"reason": reason or "replacement 未变化", "original": original[:80]})
                continue

            occurrences = updated.count(original)
            if occurrences != 1:
                skipped.append({
                    "reason": reason or f"original 匹配次数异常: {occurrences}",
                    "original": original[:80],
                    "occurrences": occurrences,
                })
                continue

            updated = updated.replace(original, replacement, 1)
            applied.append({
                "reason": reason,
                "original": original[:80],
                "replacement": replacement[:80],
            })

        return updated, {"applied": applied, "skipped": skipped}

    async def _run_targeted_fix_edit_pass(self, chapter_id: int, content: str, suggestions: str) -> tuple[str, Dict[str, Any]]:
        """执行一次定点修补，返回修补后正文和补丁报告。"""
        if not self.ai_service:
            raise RuntimeError("AI Service not initialized")

        prompt = self._build_targeted_fix_patch_prompt(chapter_id, content, suggestions)
        raw = await self.ai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4000,
            response_format="json_object",
        )
        json_text = self._extract_json_object_text(raw)
        data = json.loads(json_text) if json_text else {}
        edits = data.get("edits", []) if isinstance(data, dict) else []
        updated, report = self._apply_targeted_fix_edits(content, edits)
        report["edit_count"] = len(edits) if isinstance(edits, list) else 0
        return updated, report

    def _merge_extraction_payload(self, acc: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        """合并分块抽取结果，做去重与字段补全。"""
        if not isinstance(acc, dict) or not acc:
            acc = {
                "new_characters": [],
                "new_treasures": [],
                "new_techniques": [],
                "new_organizations": [],
                "new_locations": [],
                "status_changes": [],
                "entity_events": [],
                "exits": [],
                "status_file_updates": {"character_updates": [], "resource_updates": [], "new_items": [], "troop_casualties": {}},
            }
        if not isinstance(incoming, dict):
            return acc

        def upsert_name_list(key: str):
            existing = acc.setdefault(key, [])
            current_map = {self._name_key(self._safe_text(x.get("name", ""))): i for i, x in enumerate(existing) if isinstance(x, dict)}
            for item in incoming.get(key, []):
                if not isinstance(item, dict):
                    continue
                name = self._normalize_entity_name(item.get("name", ""))
                if not name:
                    continue
                item = dict(item)
                item["name"] = name
                nkey = self._name_key(name)
                idx = current_map.get(nkey)
                if idx is None:
                    current_map[nkey] = len(existing)
                    existing.append(item)
                    continue
                merged = existing[idx]
                for k, v in item.items():
                    val = self._safe_text(v).strip()
                    if val and not self._safe_text(merged.get(k, "")).strip():
                        merged[k] = v

        for list_key in ["new_characters", "new_treasures", "new_techniques", "new_organizations", "new_locations"]:
            upsert_name_list(list_key)

        # status_changes：同名合并，后片段非空字段优先覆盖
        status_map: Dict[str, Dict[str, Any]] = {
            self._name_key(self._safe_text(x.get("name", ""))): x
            for x in acc.setdefault("status_changes", [])
            if isinstance(x, dict)
        }
        for item in incoming.get("status_changes", []):
            if not isinstance(item, dict):
                continue
            name = self._normalize_entity_name(item.get("name", ""))
            if not name:
                continue
            key = self._name_key(name)
            if key not in status_map:
                normalized = {
                    "name": name,
                    "status": self._safe_text(item.get("status", "")).strip(),
                    "realm": self._safe_text(item.get("realm", "")).strip(),
                    "location": self._safe_text(item.get("location", "")).strip(),
                    "change": self._safe_text(item.get("change", "")).strip(),
                }
                acc["status_changes"].append(normalized)
                status_map[key] = normalized
                continue
            target = status_map[key]
            for field in ["status", "realm", "location"]:
                value = self._safe_text(item.get(field, "")).strip()
                if value:
                    target[field] = value
            change_new = self._safe_text(item.get("change", "")).strip()
            if change_new:
                change_old = self._safe_text(target.get("change", "")).strip()
                if not change_old:
                    target["change"] = change_new
                elif change_new not in change_old:
                    target["change"] = f"{change_old}；{change_new}"

        # entity_events 去重
        event_seen = {
            (self._name_key(self._safe_text(x.get("name", ""))), self._safe_text(x.get("event", "")).strip())
            for x in acc.setdefault("entity_events", [])
            if isinstance(x, dict)
        }
        for item in incoming.get("entity_events", []):
            if not isinstance(item, dict):
                continue
            name = self._normalize_entity_name(item.get("name", ""))
            event = self._safe_text(item.get("event", "")).strip()
            if not name or not event:
                continue
            key = (self._name_key(name), event)
            if key in event_seen:
                continue
            event_seen.add(key)
            payload = dict(item)
            payload["name"] = name
            acc["entity_events"].append(payload)

        # exits 同名去重，保留最新 reason
        exit_map: Dict[str, Dict[str, Any]] = {
            self._name_key(self._safe_text(x.get("name", ""))): x
            for x in acc.setdefault("exits", [])
            if isinstance(x, dict)
        }
        for item in incoming.get("exits", []):
            if not isinstance(item, dict):
                continue
            name = self._normalize_entity_name(item.get("name", ""))
            if not name:
                continue
            key = self._name_key(name)
            reason = self._safe_text(item.get("reason", "")).strip()
            if key not in exit_map:
                payload = {"name": name, "reason": reason}
                acc["exits"].append(payload)
                exit_map[key] = payload
            elif reason:
                exit_map[key]["reason"] = reason

        # status_file_updates 合并
        sfu = acc.setdefault("status_file_updates", {})
        incoming_sfu = incoming.get("status_file_updates", {})
        if isinstance(incoming_sfu, dict):
            for field in ["chapter_event", "event_consequence"]:
                value = self._safe_text(incoming_sfu.get(field, "")).strip()
                if value:
                    sfu[field] = value

            def merge_named_list(target_key: str, name_key: str):
                target = sfu.setdefault(target_key, [])
                mapping = {self._safe_text(x.get(name_key, "")).strip(): x for x in target if isinstance(x, dict)}
                for item in incoming_sfu.get(target_key, []):
                    if not isinstance(item, dict):
                        continue
                    name = self._safe_text(item.get(name_key, "")).strip()
                    if not name:
                        continue
                    if name not in mapping:
                        payload = dict(item)
                        target.append(payload)
                        mapping[name] = payload
                        continue
                    for k, v in item.items():
                        val = self._safe_text(v).strip()
                        if val:
                            mapping[name][k] = v

            merge_named_list("character_updates", "name")
            merge_named_list("resource_updates", "resource_name")
            merge_named_list("new_items", "name")

            troop_in = incoming_sfu.get("troop_casualties", {})
            if isinstance(troop_in, dict):
                troop = sfu.setdefault("troop_casualties", {})
                for k, v in troop_in.items():
                    val = self._safe_text(v).strip()
                    if val:
                        troop[k] = v

        return acc

    def _collect_consistency_reference(self, context_pack: Dict[str, Any]) -> Dict[str, List[str]]:
        """收集写后设定一致性检查所需的标准名参考。"""

        def dedupe(items: List[str]) -> List[str]:
            seen = set()
            result: List[str] = []
            for raw in items:
                name = self._normalize_entity_name(raw)
                if not name:
                    continue
                key = self._name_key(name)
                if key in seen:
                    continue
                seen.add(key)
                result.append(name)
            return result

        core = context_pack.get("core", {}) if isinstance(context_pack, dict) else {}
        characters: List[str] = []

        protagonist_snapshot = core.get("protagonist_snapshot", {})
        if not isinstance(protagonist_snapshot, dict):
            protagonist_snapshot = {}
        protagonist_name = self._safe_text(protagonist_snapshot.get("name", "")).strip()
        if protagonist_name:
            characters.append(protagonist_name)

        roster_text = self._safe_text(core.get("character_roster", ""))
        dead_characters: List[str] = []
        if roster_text:
            characters.extend(re.findall(r"-\s*\*\*(.+?)\*\*", roster_text))
            if "## 已下线" in roster_text:
                offline_part = roster_text.split("## 已下线", 1)[1]
                dead_characters.extend(re.findall(r"-\s*\*\*(.+?)\*\*", offline_part))

        for f in self._iter_character_files()[:120]:
            characters.append(f.stem)

        settings_dir = self.project_root / "设定集"
        buckets: Dict[str, List[str]] = {
            "characters": dedupe(characters),
            "dead_characters": dedupe(dead_characters),
            "techniques": [],
            "treasures": [],
            "organizations": [],
            "locations": [],
        }
        dir_map = {
            "techniques": "功法库",
            "treasures": "宝物库",
            "organizations": "势力库",
            "locations": "地点库",
        }
        for key, dirname in dir_map.items():
            lib_dir = settings_dir / dirname
            if not lib_dir.exists():
                continue
            names = [p.stem for p in sorted(lib_dir.glob("*.md"))[:120]]
            buckets[key] = dedupe(names)

        return buckets

    def _format_consistency_reference(self, reference: Dict[str, List[str]], max_chars: int) -> str:
        """将标准名参考压缩成提示词文本。"""
        rows = [
            f"【角色标准名】{'、'.join(reference.get('characters', [])[:80]) or '（无）'}",
            f"【已下线/死亡角色（禁止复活）】{'、'.join(reference.get('dead_characters', [])[:80]) or '（无）'}",
            f"【功法标准名】{'、'.join(reference.get('techniques', [])[:120]) or '（无）'}",
            f"【宝物标准名】{'、'.join(reference.get('treasures', [])[:120]) or '（无）'}",
            f"【势力标准名】{'、'.join(reference.get('organizations', [])[:120]) or '（无）'}",
            f"【地点标准名】{'、'.join(reference.get('locations', [])[:120]) or '（无）'}",
        ]
        return self._truncate_text("\n".join(rows), max_chars, keep_tail=False)

    def _merge_conflict_scan_payload(self, acc: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        """合并设定冲突扫描结果。"""
        if not isinstance(acc, dict) or not acc:
            acc = {"conflicts": [], "rename_suggestions": [], "summary": ""}
        if not isinstance(incoming, dict):
            return acc

        existing_conf = {
            (
                self._safe_text(x.get("kind", "")).strip().lower(),
                self._name_key(self._safe_text(x.get("observed", ""))),
                self._name_key(self._safe_text(x.get("canonical", ""))),
                self._safe_text(x.get("reason", "")).strip(),
            )
            for x in acc.get("conflicts", [])
            if isinstance(x, dict)
        }
        for raw in incoming.get("conflicts", []):
            if not isinstance(raw, dict):
                continue
            kind = self._safe_text(raw.get("kind", "name_mismatch")).strip().lower() or "name_mismatch"
            severity = self._safe_text(raw.get("severity", "major")).strip().lower() or "major"
            observed = self._normalize_entity_name(raw.get("observed", ""))
            canonical = self._normalize_entity_name(raw.get("canonical", ""))
            reason = self._safe_text(raw.get("reason", "")).strip()
            evidence = self._safe_text(raw.get("evidence", "")).strip()
            if not any([observed, canonical, reason]):
                continue
            key = (kind, self._name_key(observed), self._name_key(canonical), reason)
            if key in existing_conf:
                continue
            existing_conf.add(key)
            acc.setdefault("conflicts", []).append({
                "kind": kind,
                "severity": severity,
                "observed": observed,
                "canonical": canonical,
                "reason": reason,
                "evidence": evidence,
            })

        rename_map: Dict[str, Dict[str, Any]] = {}
        for item in acc.get("rename_suggestions", []):
            if not isinstance(item, dict):
                continue
            src = self._normalize_entity_name(item.get("from", ""))
            dst = self._normalize_entity_name(item.get("to", ""))
            if not src or not dst or src == dst:
                continue
            key = self._name_key(src)
            rename_map[key] = {"from": src, "to": dst, "confidence": item.get("confidence", 0.6)}

        incoming_renames = incoming.get("rename_suggestions", [])
        if isinstance(incoming_renames, list):
            for item in incoming_renames:
                if not isinstance(item, dict):
                    continue
                src = self._normalize_entity_name(item.get("from", item.get("observed", "")))
                dst = self._normalize_entity_name(item.get("to", item.get("canonical", "")))
                if not src or not dst or src == dst:
                    continue
                key = self._name_key(src)
                conf_raw = item.get("confidence", 0.75)
                try:
                    conf = float(conf_raw)
                except Exception:
                    conf = 0.75
                existing = rename_map.get(key)
                if existing is None:
                    rename_map[key] = {"from": src, "to": dst, "confidence": conf}
                    continue
                try:
                    old_conf = float(existing.get("confidence", 0.0))
                except Exception:
                    old_conf = 0.0
                if conf > old_conf:
                    rename_map[key] = {"from": src, "to": dst, "confidence": conf}

        acc["rename_suggestions"] = list(rename_map.values())

        summary = self._safe_text(incoming.get("summary", "")).strip()
        if summary:
            old = self._safe_text(acc.get("summary", "")).strip()
            acc["summary"] = summary if not old else f"{old}；{summary}"

        return acc

    def _apply_rename_suggestions(self, content: str, suggestions: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
        """按建议替换术语，优先处理长词并避免中文子串误伤。"""
        updated = self._safe_text(content)
        if not updated or not suggestions:
            return updated, []

        plan: List[Dict[str, Any]] = []
        for item in suggestions:
            if not isinstance(item, dict):
                continue
            src = self._normalize_entity_name(item.get("from", ""))
            dst = self._normalize_entity_name(item.get("to", ""))
            if not src or not dst or src == dst or len(src) < 2:
                continue
            try:
                conf = float(item.get("confidence", 0.75))
            except Exception:
                conf = 0.75
            plan.append({"from": src, "to": dst, "confidence": conf})
        plan.sort(key=lambda x: len(x["from"]), reverse=True)

        applied: List[Dict[str, Any]] = []
        for item in plan:
            src = item["from"]
            dst = item["to"]
            if src not in updated:
                continue
            updated_next, count = self._replace_term_safely(updated, src, dst)
            if count <= 0:
                continue
            updated = updated_next
            applied.append({"from": src, "to": dst, "count": count, "confidence": item.get("confidence", 0.75)})

        return updated, applied

    def _extract_critical_conflicts(self, conflicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        critical: List[Dict[str, Any]] = []
        for item in conflicts:
            if not isinstance(item, dict):
                continue
            severity = self._safe_text(item.get("severity", "")).strip().lower()
            kind = self._safe_text(item.get("kind", "")).strip().lower()
            if severity in {"critical", "major"}:
                critical.append(item)
                continue
            if kind in {"realm_conflict", "location_conflict", "timeline_conflict", "identity_conflict", "dead_character_revive"}:
                critical.append(item)
        return critical

    async def _ai_fix_setting_conflicts(
        self,
        chapter: int,
        content: str,
        critical_conflicts: List[Dict[str, Any]],
        context_pack: Dict[str, Any],
        reference_text: str,
    ) -> str:
        """对关键冲突做一次定向修正，尽量保留原文结构。"""
        if not self.ai_service or not critical_conflicts:
            return content

        budget = self._get_context_budgets("consistency_guard")
        core = context_pack.get("core", {}) if isinstance(context_pack, dict) else {}
        outline_text = self._truncate_text(self._safe_text(core.get("chapter_outline", "")), budget.get("outline", 2400), keep_tail=False)
        full_outline_text = self._safe_text(core.get("outline", ""))
        next_outline_text = self._truncate_text(self._parse_outline(full_outline_text, chapter + 1), budget.get("next_outline", 1600), keep_tail=False)
        conflicts_text = self._truncate_text(
            json.dumps(critical_conflicts[:12], ensure_ascii=False, indent=2),
            3200,
            keep_tail=False,
        )
        style_bundle, normalized_genre, normalized_substyle = self._build_project_stage_style_bundle(
            stage="设定冲突修复",
            genre_style_chars=450,
            genre_examples_chars=300,
            substyle_examples_chars=250,
        )
        substyle_display = normalized_substyle or "默认子风格"
        style_section = f"【当前阶段题材协议】\n{style_bundle}\n\n" if style_bundle else ""

        prompt = f"""{style_section}你是小说设定修复编辑器。请仅修复"设定一致性冲突"，禁止改剧情主线、禁止新增剧情点。

【题材】
{normalized_genre} / {substyle_display}

【本章大纲（必须保持）】
{outline_text or "（无）"}

【下一章预览（避免提前透支）】
{next_outline_text or "（无）"}

【标准名参考】
{reference_text or "（无）"}

【必须修复的关键冲突】
{conflicts_text}

【当前正文】
{content}

输出要求：
1. 仅输出修复后的完整正文，不要解释。
2. 优先做名词/身份/境界/地点一致性修正，不要改写叙事结构。
3. 保持原文长度与段落结构，不能大幅删减（长度不低于原文的85%）。
4. 修复后的正文仍须保持当前题材/子风格的笔调，不得修成其他流派腔调。"""

        try:
            fixed = await self.ai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=budget.get("fix_max_tokens", 12000),
            )
            fixed_text = self._safe_text(fixed).strip()
            if not fixed_text:
                return content
            if fixed_text.startswith("```"):
                fixed_text = re.sub(r"^```(?:markdown|md|text)?\s*", "", fixed_text, flags=re.IGNORECASE)
                fixed_text = re.sub(r"\s*```$", "", fixed_text).strip()
            if len(fixed_text) < int(len(content) * 0.85):
                print("[一致性修复] 输出长度异常，回退原文")
                return content
            return fixed_text
        except Exception as e:
            print(f"[一致性修复] AI 修复失败: {e}")
            return content

    async def _run_setting_conflict_guard(
        self,
        chapter: int,
        content: str,
        context_pack: Dict[str, Any],
    ) -> Dict[str, Any]:
        """写后设定冲突守卫：扫描冲突并自动修正。"""
        raw_content = self._safe_text(content)
        if not raw_content.strip() or not self.ai_service:
            return {
                "content": raw_content,
                "report": {
                    "scan_chunks": 0,
                    "scan_ok": 0,
                    "conflict_count": 0,
                    "rename_candidates": 0,
                    "rename_applied": 0,
                    "ai_rewrite_applied": False,
                    "summary": "skip",
                },
            }

        budget = self._get_context_budgets("consistency_guard")
        core = context_pack.get("core", {}) if isinstance(context_pack, dict) else {}
        chapter_outline = self._truncate_text(self._safe_text(core.get("chapter_outline", "")), budget.get("outline", 2400), keep_tail=False)
        full_outline_text = self._safe_text(core.get("outline", ""))
        next_outline = self._truncate_text(self._parse_outline(full_outline_text, chapter + 1), budget.get("next_outline", 1600), keep_tail=False)
        reference_obj = self._collect_consistency_reference(context_pack)
        reference_text = self._format_consistency_reference(reference_obj, budget.get("reference", 2600))
        style_bundle, normalized_genre, normalized_substyle = self._build_project_stage_style_bundle(
            stage="设定冲突扫描",
            genre_style_chars=320,
            genre_examples_chars=0,
            substyle_examples_chars=0,
        )
        substyle_display = normalized_substyle or "默认子风格"
        style_section = f"【当前阶段题材协议】\n{style_bundle}\n\n" if style_bundle else ""

        chunks = self._split_text_chunks(
            raw_content,
            chunk_size=budget.get("chunk_size", 4200),
            overlap=budget.get("chunk_overlap", 500),
        )
        if len(chunks) > 6:
            # 控制额外耗时：超长章节取首段+中段+尾段，避免只看头尾漏掉中部冲突
            mid = len(chunks) // 2
            candidate_idx = [0, 1, max(0, mid - 1), mid, len(chunks) - 2, len(chunks) - 1]
            picked = sorted(set(i for i in candidate_idx if 0 <= i < len(chunks)))
            chunks = [chunks[i] for i in picked]

        merged: Dict[str, Any] = {}
        ok_scans = 0
        total_scans = len(chunks)
        for idx, piece in enumerate(chunks, start=1):
            scan_prompt = f"""{style_section}你是小说设定一致性检查器。请检查"正文片段"是否与标准名/大纲冲突。

【题材】
{normalized_genre} / {substyle_display}

【第{chapter}章大纲】
{chapter_outline or "（无）"}

【下一章预览】
{next_outline or "（无）"}

【标准名参考（优先级高于正文）】
{reference_text or "（无）"}

【正文片段 {idx}/{total_scans}】
{piece}

仅输出 JSON：
{{
  "conflicts": [
    {{
      "kind": "name_mismatch|identity_conflict|realm_conflict|location_conflict|timeline_conflict|dead_character_revive",
      "severity": "critical|major|minor",
      "observed": "正文里出现的冲突词",
      "canonical": "应使用的标准词（若有）",
      "reason": "冲突原因",
      "evidence": "一句证据"
    }}
  ],
  "rename_suggestions": [
    {{"from": "错误写法", "to": "标准写法", "confidence": 0.95}}
  ],
  "summary": "本片段结论"
}}

规则：
1. 仅报告有证据的冲突，禁止臆测。
2. 如果只是文风差异，不要报冲突。
3. 没有问题时返回空数组。"""

            scan_data = await self._chat_json_with_retry(
                scan_prompt,
                temperature=0.2,
                max_tokens=budget.get("scan_max_tokens", 1800),
                retries=1,
            )
            if not scan_data:
                continue
            merged = self._merge_conflict_scan_payload(merged, scan_data)
            ok_scans += 1

        conflicts = merged.get("conflicts", []) if isinstance(merged.get("conflicts"), list) else []
        rename_suggestions = merged.get("rename_suggestions", []) if isinstance(merged.get("rename_suggestions"), list) else []
        renamed_content, applied = self._apply_rename_suggestions(raw_content, rename_suggestions)

        critical_conflicts = self._extract_critical_conflicts(conflicts)
        non_name_kinds = {"identity_conflict", "realm_conflict", "location_conflict", "timeline_conflict", "dead_character_revive"}
        non_name_critical = [
            x
            for x in critical_conflicts
            if self._safe_text(x.get("kind", "")).strip().lower() in non_name_kinds
        ]

        ai_rewrite_applied = False
        final_content = renamed_content
        if non_name_critical:
            fixed = await self._ai_fix_setting_conflicts(
                chapter=chapter,
                content=renamed_content,
                critical_conflicts=non_name_critical,
                context_pack=context_pack,
                reference_text=reference_text,
            )
            if fixed and fixed != renamed_content:
                final_content = fixed
                ai_rewrite_applied = True

        summary = self._safe_text(merged.get("summary", "")).strip()
        report = {
            "scan_chunks": total_scans,
            "scan_ok": ok_scans,
            "conflict_count": len(conflicts),
            "rename_candidates": len(rename_suggestions),
            "rename_applied": len(applied),
            "ai_rewrite_applied": ai_rewrite_applied,
            "summary": summary,
            "applied_replacements": applied[:20],
            "critical_conflicts": critical_conflicts[:12],
        }
        return {"content": final_content, "report": report}

    def _normalize_character_extraction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清洗角色抽取数据，保证结构稳定并做名称归一。"""
        if not isinstance(data, dict):
            data = {}

        def list_of_dict(v: Any) -> List[Dict[str, Any]]:
            if not isinstance(v, list):
                return []
            return [x for x in v if isinstance(x, dict)]

        normalized = {
            "new_characters": list_of_dict(data.get("new_characters")),
            "new_treasures": list_of_dict(data.get("new_treasures")),
            "new_techniques": list_of_dict(data.get("new_techniques")),
            "new_organizations": list_of_dict(data.get("new_organizations")),
            "new_locations": list_of_dict(data.get("new_locations")),
            "status_changes": list_of_dict(data.get("status_changes")),
            "entity_events": list_of_dict(data.get("entity_events")),
            "exits": list_of_dict(data.get("exits")),
            "status_file_updates": data.get("status_file_updates") if isinstance(data.get("status_file_updates"), dict) else {},
        }

        # new_characters 去重 + 过滤占位名
        char_seen = set()
        cleaned_chars = []
        for raw in normalized["new_characters"]:
            name = self._normalize_entity_name(raw.get("name", ""))
            if not name:
                continue
            if name in {"主角", "男主", "女主", "路人", "路人甲", "某人", "无名氏"}:
                continue
            key = self._name_key(name)
            if key in char_seen:
                continue
            char_seen.add(key)
            cleaned_chars.append({
                "name": name,
                "importance": self._safe_text(raw.get("importance", "minor")),
                "identity": self._safe_text(raw.get("identity", "未知")),
                "relation": self._safe_text(raw.get("relation", "待补充")),
                "appearance": self._safe_text(raw.get("appearance", "待补充")),
                "personality": self._safe_text(raw.get("personality", "待补充")),
                "realm": self._safe_text(raw.get("realm", "未知")),
                "location": self._safe_text(raw.get("location", "未知")),
                "first_action": self._safe_text(raw.get("first_action", "初次登场")),
            })
        normalized["new_characters"] = cleaned_chars

        # 其余实体列表：统一名称、去空
        for key, name_field in [
            ("new_treasures", "name"),
            ("new_techniques", "name"),
            ("new_organizations", "name"),
            ("new_locations", "name"),
        ]:
            dedup = set()
            cleaned = []
            for raw in normalized[key]:
                name = self._normalize_entity_name(raw.get(name_field, ""))
                if not name:
                    continue
                nkey = self._alias_key(name) if key == "new_techniques" else self._name_key(name)
                if nkey in dedup:
                    continue
                dedup.add(nkey)
                item = {k: self._safe_text(v) for k, v in raw.items()}
                item[name_field] = name
                cleaned.append(item)
            normalized[key] = cleaned

        cleaned_status_changes = []
        for raw in normalized["status_changes"]:
            item = {k: self._safe_text(v) for k, v in raw.items()}
            item["name"] = self._normalize_entity_name(item.get("name", ""))
            item["status"] = self._safe_text(item.get("status", "")).strip()
            item["realm"] = self._safe_text(item.get("realm", "")).strip()
            item["location"] = self._safe_text(item.get("location", "")).strip()
            item["change"] = self._safe_text(item.get("change", "")).strip()
            if not item["status"] and item["change"]:
                item["status"] = item["change"]
            if item["name"]:
                cleaned_status_changes.append(item)
        normalized["status_changes"] = cleaned_status_changes

        for key in ["entity_events", "exits"]:
            cleaned = []
            for raw in normalized[key]:
                item = {k: self._safe_text(v) for k, v in raw.items()}
                if "name" in item:
                    item["name"] = self._normalize_entity_name(item["name"])
                cleaned.append(item)
            normalized[key] = cleaned

        sfu = normalized["status_file_updates"]
        # 保证关键字段为列表/字典，防止后续遍历异常
        for lk in ["character_updates", "resource_updates", "new_items"]:
            if not isinstance(sfu.get(lk), list):
                sfu[lk] = []
        if not isinstance(sfu.get("troop_casualties"), dict):
            sfu["troop_casualties"] = {}
        normalized["status_file_updates"] = sfu
        return normalized

    def _extract_roster_entries(self, roster_text: str) -> List[Dict[str, str]]:
        entries: List[Dict[str, str]] = []
        if not roster_text:
            return entries

        for line in roster_text.splitlines():
            if "**" not in line:
                continue
            m = re.search(r"\*\*(.+?)\*\*", line)
            if not m:
                continue
            name = self._normalize_entity_name(m.group(1))
            if not name:
                continue
            after = line[m.end():].strip(" ｜|")
            parts = [p.strip() for p in re.split(r"[｜|]", after) if p.strip()]
            identity = parts[0] if len(parts) >= 1 else "未知"
            note = parts[1] if len(parts) >= 2 else ""
            entries.append({"name": name, "identity": identity, "note": note})
        return entries

    def _ensure_character_profiles_from_roster(self, chapter_hint: int = 0) -> int:
        """规则兜底：活跃角色表里有但角色库缺失时，自动补建基础档案。"""
        roster_file = self.project_root / "设定集" / "角色库" / "活跃角色.md"
        if not roster_file.exists():
            return 0

        roster_text = roster_file.read_text(encoding="utf-8")
        entries = self._extract_roster_entries(roster_text)
        if not entries:
            return 0

        char_lib = self.project_root / "设定集" / "角色库"
        for c in ["主要角色", "次要角色", "反派角色"]:
            (char_lib / c).mkdir(parents=True, exist_ok=True)

        created = 0
        for entry in entries:
            name = entry["name"]
            if self._find_character_file_by_name(name):
                continue
            identity = entry.get("identity", "未知")
            note = entry.get("note", "")
            category = self._infer_character_category(identity=identity)
            chapter_match = re.search(r"第(\d+)章", note)
            first_chapter = int(chapter_match.group(1)) if chapter_match else (chapter_hint or 0)
            chapter_text = f"第{first_chapter}章" if first_chapter > 0 else "未知章节"

            content = f"""# {name}

## 基本信息
- **身份**：{identity or "未知"}
- **首次出场**：{chapter_text}
- **当前境界**：未知
- **当前状态**：存活
- **当前地点**：未知
- **最后更新章节**：{chapter_text}

## 与主角关系
待补充

## 外貌描写
待补充

## 性格特点
待补充

## 关键事件时间线
- {chapter_text}：由活跃角色表补建档案

---
*档案由系统自动补建（活跃角色表兜底）*
"""
            (char_lib / category / f"{name}.md").write_text(content, encoding="utf-8")
            created += 1

        return created

    def _ensure_basic_info_field(self, content: str, label: str, default_value: str) -> tuple[str, bool]:
        """确保角色档案在"基本信息"中存在指定字段。"""
        field_pattern = rf"- \*\*{re.escape(label)}\*\*："
        if re.search(field_pattern, content):
            return content, False

        lines = content.splitlines()
        basic_start = -1
        basic_end = len(lines)

        for i, line in enumerate(lines):
            if re.match(r"^##\s*基本信息\s*$", line.strip()):
                basic_start = i
                break

        if basic_start >= 0:
            for i in range(basic_start + 1, len(lines)):
                if lines[i].strip().startswith("## "):
                    basic_end = i
                    break
        else:
            insert_at = 1 if lines and lines[0].startswith("#") else 0
            section = ["", "## 基本信息", f"- **{label}**：{default_value}", ""]
            lines[insert_at:insert_at] = section
            return "\n".join(lines), True

        order = ["身份", "首次出场", "当前境界", "当前状态", "当前地点", "最后更新章节"]
        target_order = order.index(label) if label in order else len(order)
        insert_pos = basic_end

        for i in range(basic_start + 1, basic_end):
            m = re.search(r"- \*\*(.+?)\*\*：", lines[i])
            if not m:
                continue
            existing_label = m.group(1).strip()
            existing_order = order.index(existing_label) if existing_label in order else len(order)
            if existing_order > target_order:
                insert_pos = i
                break

        lines.insert(insert_pos, f"- **{label}**：{default_value}")
        return "\n".join(lines), True

    def _set_basic_info_field(self, content: str, label: str, value: str) -> tuple[str, bool]:
        """设置角色档案"基本信息"字段，字段不存在时自动补齐。"""
        text = self._safe_text(value).strip()
        if not text:
            return content, False

        pattern = rf"(- \*\*{re.escape(label)}\*\*：)(.*)"
        if re.search(pattern, content):
            updated = re.sub(pattern, lambda m: f"{m.group(1)}{text}", content, count=1)
            return updated, updated != content

        return self._ensure_basic_info_field(content, label, text)

    def _get_basic_info_field(self, content: str, label: str) -> str:
        """读取角色档案"基本信息"字段值，兼容 markdown 加粗写法。"""
        if not content:
            return ""
        pattern = rf"(?:^|\n)\s*(?:-\s*)?(?:\*{{0,2}})?{re.escape(label)}(?:\*{{0,2}})?\s*[：:]\s*(.+)"
        m = re.search(pattern, content, re.MULTILINE)
        return self._safe_text(m.group(1)).strip() if m else ""

    def _append_character_timeline(self, content: str, chapter: int, event_desc: str) -> tuple[str, bool]:
        """向角色档案追加关键事件时间线。"""
        desc = self._safe_text(event_desc).strip()
        if not desc:
            return content, False

        entry = f"- 第{chapter}章：{desc}"
        if entry in content:
            return content, False

        lines = content.splitlines()
        section_start = -1
        section_end = len(lines)
        for i, line in enumerate(lines):
            if re.match(r"^##\s*关键事件时间线\s*$", line.strip()):
                section_start = i
                break

        if section_start >= 0:
            for i in range(section_start + 1, len(lines)):
                if lines[i].strip().startswith("## "):
                    section_end = i
                    break
            lines.insert(section_end, entry)
            return "\n".join(lines), True

        suffix = "\n" if content.endswith("\n") else "\n\n"
        updated = content + f"{suffix}## 关键事件时间线\n{entry}\n"
        return updated, True

    def _ensure_character_schema(self, chapter_hint: int = 0) -> int:
        """为现有角色补齐结构化字段（境界/状态/地点）。"""
        if chapter_hint > 0 and self._schema_ensure_chapter == chapter_hint:
            return 0
        default_chapter = f"第{chapter_hint}章" if chapter_hint > 0 else "未知章节"
        changed = 0
        for f in self._iter_character_files():
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue

            original = content
            for label, default in [
                ("当前境界", "未知"),
                ("当前状态", "存活"),
                ("当前地点", "未知"),
                ("最后更新章节", default_chapter),
            ]:
                content, _ = self._ensure_basic_info_field(content, label, default)

            # 历史脏数据兜底：未知状态默认视为"存活"
            current_status = self._get_basic_info_field(content, "当前状态")
            if current_status in {"", "未知", "待补充", "未记录"}:
                content, _ = self._set_basic_info_field(content, "当前状态", "存活")

            # 历史脏数据兜底：最后更新章节为占位值时回填当前章
            last_update = self._get_basic_info_field(content, "最后更新章节")
            if last_update in {"", "未知章节", "第?章"} and chapter_hint > 0:
                content, _ = self._set_basic_info_field(content, "最后更新章节", default_chapter)

            if content != original:
                f.write_text(content, encoding="utf-8")
                changed += 1
        if chapter_hint > 0:
            self._schema_ensure_chapter = chapter_hint
        return changed

    def _extract_protagonist_name_from_card(self, card_text: str) -> str:
        """从主角卡文本提取主角名。"""
        if not card_text:
            return ""
        patterns = [
            r"^>\s*主角[：:]\s*([^｜|\n]+)",
            r"\*?\*?姓名\*?\*?[：:]\s*([^\s（(]+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, card_text, re.MULTILINE)
            if not m:
                continue
            name = self._normalize_entity_name(m.group(1))
            if name and "待填写" not in name and "待定" not in name:
                return name
        return ""

    def _sync_protagonist_profile(self, protagonist_name: str) -> None:
        """同步主角到 state/角色库/活跃角色表，避免数据源分裂。"""
        name = self._normalize_entity_name(protagonist_name)
        if not name:
            return

        # 1) 同步 state.json
        def apply_protagonist_state(s: Dict[str, Any]) -> None:
            s.setdefault("protagonist_state", {})
            if s["protagonist_state"].get("name") != name:
                s["protagonist_state"]["name"] = name

        self._update_state(apply_protagonist_state)

        # 2) 确保主角档案存在
        char_lib = self.project_root / "设定集" / "角色库"
        main_dir = char_lib / "主要角色"
        main_dir.mkdir(parents=True, exist_ok=True)

        existing_file = self._find_character_file_by_name(name)
        canonical_name = existing_file.stem if existing_file else name
        target_file = existing_file
        if existing_file is None:
            profile_path = main_dir / f"{name}.md"
            profile_path.write_text(
                f"""# {name}

## 基本信息
- **身份**：主角
- **首次出场**：第1章
- **当前境界**：未知
- **当前状态**：存活
- **当前地点**：未知
- **最后更新章节**：第1章

## 与主角关系
主角本人

## 外貌描写
待补充

## 性格特点
待补充

## 关键事件时间线
- 第1章：项目初始化建档

---
*档案由主角卡同步创建*
""",
                encoding="utf-8",
            )
            canonical_name = name
            target_file = profile_path

        # 兼容旧档案：补齐结构化字段
        if target_file and target_file.exists():
            try:
                content = target_file.read_text(encoding="utf-8")
                original = content
                for label, default in [
                    ("当前境界", "未知"),
                    ("当前状态", "存活"),
                    ("当前地点", "未知"),
                    ("最后更新章节", "第1章"),
                ]:
                    content, _ = self._ensure_basic_info_field(content, label, default)
                if content != original:
                    target_file.write_text(content, encoding="utf-8")
            except Exception:
                pass

        # 3) 确保活跃角色表包含主角
        roster_file = char_lib / "活跃角色.md"
        roster_file.parent.mkdir(parents=True, exist_ok=True)
        with self._locked_file(roster_file):
            if roster_file.exists():
                roster_text = roster_file.read_text(encoding="utf-8")
                roster_lines = roster_text.splitlines()
            else:
                roster_lines = [
                    "# 活跃角色表（初始化）",
                    "",
                    "## 活跃角色",
                    "",
                    "## 已下线（仅保留记录）",
                ]

            existing_keys = {self._name_key(e["name"]) for e in self._extract_roster_entries("\n".join(roster_lines))}
            protagonist_key = self._name_key(canonical_name)
            if protagonist_key not in existing_keys:
                new_entry = f"- **{canonical_name}**｜主角｜第1章登场"
                insert_idx = len(roster_lines)
                for i, line in enumerate(roster_lines):
                    if "## 已下线" in line:
                        insert_idx = i
                        break
                roster_lines.insert(insert_idx, new_entry)
                roster_file.write_text("\n".join(roster_lines) + "\n", encoding="utf-8")

    # ==================== webnovel-init ====================

    async def execute_init_stream(
        self,
        title: str,
        genre: str,
        substyle: str = "",
        protagonist_name: str = "",
        golden_finger_name: str = "",
        golden_finger_type: str = "",
        mode: str = "standard",
        additional_info: str = "",
        target_words: Optional[int] = None
    ):
        """流式执行 webnovel-init Skill 完整工作流"""
        def make_step(step, name, status="pending"):
            return json.dumps({"type": "step", "step": step, "name": name, "status": status}, ensure_ascii=False)

        # Step 1: 加载题材套路
        yield make_step(1, "加载题材套路", "processing")
        genre_tropes = self._load_reference("webnovel-init", "genre-tropes.md")
        yield make_step(1, "加载题材套路", "completed" if genre_tropes else "warning")

        # Step 2: 加载数据规范
        yield make_step(2, "加载数据规范", "processing")
        data_flow = self._load_reference("webnovel-init", "system-data-flow.md")
        yield make_step(2, "加载数据规范", "completed" if data_flow else "warning")

        # Step 5.5: 加载题材模板
        yield make_step("5.5", f"加载题材模板: {genre}", "processing")
        genre_template = self._load_genre_template(genre)
        yield make_step("5.5", f"加载题材模板: {genre}", "completed" if genre_template else "warning")

        # Step 6: 金手指设计 (Standard+)
        if mode in ("standard", "deep"):
            yield make_step(6, "加载金手指设计参考", "processing")
            selling_points = self._load_reference("webnovel-init", "creativity/selling-points.md")
            yield make_step(6, "加载金手指设计参考", "completed" if selling_points else "warning")

        # Step 8: 生成项目文件
        yield make_step(8, "生成项目文件骨架", "processing")
        try:
            from init_project import init_project
            init_kwargs = dict(
                project_dir=str(self.project_root),
                title=title,
                genre=genre,
                substyle=substyle,
                protagonist_name=protagonist_name,
                golden_finger_name=golden_finger_name,
                golden_finger_type=golden_finger_type
            )
            if target_words is not None:
                init_kwargs["target_words"] = target_words
            init_project(**init_kwargs)
            yield make_step(8, "生成项目文件骨架", "completed")
            
            # Step 9: AI 自动填充内容
            has_critical_failure = False
            if self.ai_service:
                async for status in self._ai_fill_init_content_stream(
                    title,
                    genre,
                    substyle,
                    protagonist_name,
                    golden_finger_name,
                    golden_finger_type,
                    additional_info,
                ):
                    yield json.dumps(status, ensure_ascii=False)
                    if isinstance(status, dict) and status.get("status") == "failed":
                        has_critical_failure = True

            if has_critical_failure:
                yield json.dumps({"type": "done", "success": False, "message": f"项目 '{title}' 初始化部分失败，请检查步骤状态"}, ensure_ascii=False)
            else:
                yield json.dumps({"type": "done", "success": True, "message": f"项目 '{title}' 初始化完成"}, ensure_ascii=False)
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"项目初始化失败: {str(e)}"}, ensure_ascii=False)

    async def _ai_fill_init_content_stream(self, title, genre, substyle, protagonist, gf_name, gf_type, additional_info=""):
        """流式填充 AI 初始化内容 - 使用串行调用确保一致性"""
        # 加载知识库
        genre = canonical_genre_id(genre)
        effective_substyle = self._get_effective_substyle(genre, substyle)
        try:
            genre_tropes = self._load_reference("webnovel-init", "genre-tropes.md")
            genre_template = self._load_genre_template(genre)
        except Exception:
            genre_tropes = ""
            genre_template = ""
        trope_focus = self._load_genre_trope_focus(genre, genre_tropes, max_chars=1200)
        style_guide = self._load_genre_style_guide(genre, max_chars=1800)
        style_examples = self._load_genre_style_examples(genre, effective_substyle, max_chars=1000)
        independent_stage_prompt = self._build_independent_stage_prompt_block(
            genre,
            effective_substyle,
            stage="初始化/总纲规划",
        )
        substyle_instruction = self._build_substyle_instruction(genre, effective_substyle, stage="初始化/总纲规划")
        substyle_examples = self._load_substyle_examples(genre, effective_substyle, max_chars=700)
        genre_guard = self._build_genre_guard_instruction(genre, stage="初始化/总纲规划")
        positive_style_instruction = self._build_genre_positive_style_instruction(genre, stage="初始化/总纲规划")

        base_context = f"""【小说信息】
- 书名：《{title}》
- 题材：{genre}
- 子风格：{effective_substyle or "（未指定，按题材默认）"}
- 主角名：{protagonist or "（待定）"}
- 金手指：{gf_name or "（待定）"} - {gf_type or "（待定）"}
【用户补充设定】
{additional_info if additional_info else "（无）"}
{independent_stage_prompt if independent_stage_prompt else ""}
【题材锁定】
{genre_guard}
【题材笔调校准】
{positive_style_instruction}
【子风格锁定】
{substyle_instruction if substyle_instruction else "（无）"}
【题材参考（仅限当前题材）】
{trope_focus if trope_focus else ""}
{style_guide if style_guide else ""}
【子风格示例（按当前子风格抽取）】
{substyle_examples if substyle_examples else ""}
【题材示例（按当前题材动态加载）】
{style_examples if style_examples else ""}
要求：只学习句法与节奏，不照抄原句。
{genre_template[:600] if genre_template else ""}"""

        # ========== 第1步：生成世界观 ==========
        yield {"type": "step", "step": "9a", "name": "AI 构思世界观", "status": "processing"}
        try:
            prompt = f"""{base_context}

请为这本{genre}小说设计【世界观设定】，包括：
1. 世界背景（时代、地理、社会结构）
2. 核心规则（什么是被允许的，什么是禁忌）
3. 主要势力分布
4. 独特的世界特色

要求：设定新颖、符合{genre}文风、逻辑自洽。使用 Markdown 格式。"""
            
            world_content = "# 世界观\n\n"
            async for chunk in self.ai_service.chat_stream([{"role": "user", "content": prompt}], temperature=0.8, max_tokens=2000):
                if not chunk or chunk.startswith("[ERROR]"):
                    continue
                world_content += chunk
                yield {"type": "content", "chunk": chunk, "target": "worldview"}
            
            (self.project_root / "设定集" / "世界观.md").write_text(world_content, encoding="utf-8")
            yield {"type": "step", "step": "9a", "name": "AI 构思世界观", "status": "completed"}
        except Exception as e:
            yield {"type": "step", "step": "9a", "name": "AI 构思世界观", "status": "failed", "error": str(e)}
            world_content = ""

        # ========== 第2步：生成力量体系（基于世界观） ==========
        yield {"type": "step", "step": "9b", "name": "AI 设计力量体系", "status": "processing"}
        try:
            prompt = f"""{base_context}

【已确定的世界观】
{world_content[:1500]}

请基于上述世界观，设计【力量体系】，包括：
1. 修炼/能力等级划分（至少6-10个等级）
2. 每个等级的特征和能力表现
3. 升级条件和方式
4. 特殊能力/天赋分类

要求：与世界观匹配、层次分明、有爽点递进感。使用 Markdown 格式。"""
            
            power_content = "# 力量体系\n\n"
            async for chunk in self.ai_service.chat_stream([{"role": "user", "content": prompt}], temperature=0.8, max_tokens=2000):
                if not chunk or chunk.startswith("[ERROR]"):
                    continue
                power_content += chunk
                yield {"type": "content", "chunk": chunk, "target": "power"}
            
            (self.project_root / "设定集" / "力量体系.md").write_text(power_content, encoding="utf-8")
            yield {"type": "step", "step": "9b", "name": "AI 设计力量体系", "status": "completed"}
        except Exception as e:
            yield {"type": "step", "step": "9b", "name": "AI 设计力量体系", "status": "failed", "error": str(e)}
            power_content = ""

        # ========== 第3步：生成主角卡（基于世界观+力量体系） ==========
        yield {"type": "step", "step": "9c", "name": "AI 设计主角卡", "status": "processing"}
        try:
            prompt = f"""{base_context}

【已确定的世界观】
{world_content[:1000]}

【已确定的力量体系】
{power_content[:1000]}

请基于上述设定，设计【主角人物卡】，包括：
1. 基本信息（姓名必须是：{protagonist or "请自行取名"}、年龄、身份）
2. 性格特点（3-5个关键词+详细描述）
3. 金手指详细设计（名称：{gf_name or "请自行设计"}，类型：{gf_type or "请自行设计"}）
   - 能力描述
   - 成长阶段
   - 使用限制
4. 初始状态（在力量体系中的位置、拥有的资源）
5. 核心目标/动机

要求：人物鲜明、金手指有成长空间、符合爽文节奏。使用 Markdown 格式。"""
            
            char_content = "# 主角卡\n\n"
            async for chunk in self.ai_service.chat_stream([{"role": "user", "content": prompt}], temperature=0.8, max_tokens=2500):
                if not chunk or chunk.startswith("[ERROR]"):
                    continue
                char_content += chunk
                yield {"type": "content", "chunk": chunk, "target": "protagonist"}
            
            (self.project_root / "设定集" / "主角卡.md").write_text(char_content, encoding="utf-8")
            parsed_name = self._extract_protagonist_name_from_card(char_content) or self._normalize_entity_name(protagonist or "")
            if parsed_name:
                self._sync_protagonist_profile(parsed_name)
            yield {"type": "step", "step": "9c", "name": "AI 设计主角卡", "status": "completed"}
        except Exception as e:
            yield {"type": "step", "step": "9c", "name": "AI 设计主角卡", "status": "failed", "error": str(e)}

        # 3. 生成总纲 - 使用流式
        yield {"type": "step", "step": 10, "name": "AI 规划全书总纲", "status": "processing"}
        try:
            world = self._read_file(self.project_root / "设定集" / "世界观.md")
            power = self._read_file(self.project_root / "设定集" / "力量体系.md")
            char = self._read_file(self.project_root / "设定集" / "主角卡.md")

            prompt = f"""请为《{title}》规划全书总纲（约600-1000章体量，分为12卷）。

{independent_stage_prompt if independent_stage_prompt else ""}

【题材锁定】
{genre_guard}

【题材笔调校准】
{positive_style_instruction}

【子风格锁定】
{substyle_instruction if substyle_instruction else "（无）"}

【设定参考】
{world[:800]}
{power[:500]}
{char[:500]}

【用户补充设定】
{additional_info if additional_info else "（无）"}

【题材核心节奏】
{trope_focus if trope_focus else "（无）"}
{style_guide if style_guide else ""}

【子风格示例（按当前子风格抽取）】
{substyle_examples if substyle_examples else "（无）"}

【题材示例（按当前题材动态加载）】
{style_examples if style_examples else "（无）"}
要求：学习风格而非复写句子。

【要求】
1. 每卷必须包含：标题、预计章数（如50-80章）、核心冲突、关键爽点、卷末高潮
2. 节奏层层递进，符合{genre} / {effective_substyle} 的爽文结构
3. 使用 Markdown 格式，每卷格式示例：
   ## 第X卷 《卷名》（约XX章）
   - **核心冲突**：...
   - **关键爽点**：...
   - **卷末高潮**：..."""

            # 使用流式 AI 调用
            outline_content = ""
            async for chunk in self.ai_service.chat_stream(
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=5000
            ):
                if not chunk:
                    continue
                if chunk.startswith("[ERROR]"):
                    yield {"type": "step", "step": 10, "name": "AI 规划全书总纲", "status": "failed", "error": chunk}
                    return
                outline_content += chunk
                # Emit content chunk for frontend streaming
                yield {"type": "content", "chunk": chunk, "target": "total_outline"}
            
            (self.project_root / "大纲" / "总纲.md").write_text(outline_content, encoding="utf-8")
            self._clear_outline_invalidation_state()
            yield {"type": "step", "step": 10, "name": "AI 规划全书总纲", "status": "completed"}
        except Exception as e:
            yield {"type": "step", "step": 10, "name": "AI 规划全书总纲", "status": "failed", "error": str(e)}

        # 4. 创建初始卷和章节（避免前端显示空）
        yield {"type": "step", "step": 11, "name": "初始化章节结构", "status": "processing"}
        try:
            # 创建第一卷大纲
            vol1_path = self.project_root / "大纲" / "第1卷.md"
            if not vol1_path.exists():
                vol1_path.write_text("# 第1卷\n\n（点击 AI 规划本卷自动生成）", encoding="utf-8")

            # 创建第一章正文
            chap1_dir = self.project_root / "正文"
            chap1_dir.mkdir(exist_ok=True)
            chap1_path = chap1_dir / "第1章.md"
            if not chap1_path.exists():
                chap1_path.write_text("# 第1章\n", encoding="utf-8")
            
            yield {"type": "step", "step": 11, "name": "初始化章节结构", "status": "completed"}
        except Exception as e:
             yield {"type": "step", "step": 11, "name": "初始化章节结构", "status": "failed", "error": str(e)}


    async def execute_init(
        self,
        title: str,
        genre: str,
        substyle: str = "",
        protagonist_name: str = "",
        golden_finger_name: str = "",
        golden_finger_type: str = "",
        mode: str = "standard",
        additional_info: str = "",
        target_words: Optional[int] = None
    ) -> Dict[str, Any]:
        """执行 webnovel-init Skill 完整工作流 (保留兼容性)"""
        # 简单包装 execute_init_stream 以保持返回 Dict 格式
        steps = []
        success = True
        async for update_str in self.execute_init_stream(
            title=title,
            genre=genre,
            substyle=substyle,
            protagonist_name=protagonist_name,
            golden_finger_name=golden_finger_name,
            golden_finger_type=golden_finger_type,
            mode=mode,
            additional_info=additional_info,
            target_words=target_words,
        ):
            update = json.loads(update_str)
            if update["type"] == "step":
                # 合并步骤状态
                existing = next((s for s in steps if s.get("step") == update["step"]), None)
                if existing:
                    existing.update(update)
                else:
                    steps.append(update)
            elif update["type"] == "error":
                success = False
        return {"steps": steps, "success": success}

    async def execute_generate_synopsis(self) -> Dict[str, Any]:
        """AI 根据现有大纲和设定生成小说简介"""
        if not self.ai_service:
            return {"success": False, "error": "AI Service not configured"}
            
        try:
            state = self._load_state() or {}
            project_info = state.get("project_info", {})
            title = project_info.get("title", "未命名项目")
            genre = project_info.get("genre", "修仙")
            substyle = canonical_substyle_id(genre, project_info.get("substyle", state.get("substyle", "")))
            style_bundle, normalized_genre, normalized_substyle = self._build_stage_style_bundle(
                genre,
                substyle,
                stage="简介生成",
                genre_style_chars=900,
                genre_examples_chars=800,
                substyle_examples_chars=700,
            )
            substyle_display = normalized_substyle or "默认子风格"
            style_section = f"【当前阶段题材协议】\n{style_bundle}\n\n" if style_bundle else ""
            
            world = self._read_file(self.project_root / "设定集" / "世界观.md")
            char = self._read_file(self.project_root / "设定集" / "主角卡.md")
            outline = self._read_file(self.project_root / "大纲" / "总纲.md")
            protagonist_state = state.get("protagonist_state", {}) if isinstance(state.get("protagonist_state"), dict) else {}
            protagonist_name = self._extract_protagonist_name_from_card(char) or self._safe_text(protagonist_state.get("name", "")).strip()
            protagonist_name = self._normalize_entity_name(protagonist_name)
            if protagonist_name:
                # 主角名以主角卡为准，同步到 state，避免后续链路读到脏值。
                self._sync_protagonist_profile(protagonist_name)
            
            prompt = f"""{style_section}请为小说《{title}》写一份吸引人的小说简介（200-500字）。
            
【题材】
{normalized_genre} / {substyle_display}

【主角姓名（硬约束）】
主角姓名必须是「{protagonist_name or "主角"}」。
严禁改名、谐音改名、同音字替换（例如把"林闲"写成"沈闲"）。

【设定参考】
{world[:1000]}
{char[:1000]}

【剧情大纲参考】
{outline[:2000]}

【任务】
1. 写一份简介，要求：钩子直接、文风严格符合上述题材/子风格创作协议、展现核心冲突或金手指爽点。
2. 简介要能吸引读者产生阅读愿望。
3. 请直接输出简介内容，不要带有"好的"、"这是简介"等废话。
4. 简介中出现主角姓名时，必须严格使用「{protagonist_name or "主角"}」。"""

            synopsis = await self.ai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=1000
            )
            synopsis = self._safe_text(synopsis).strip()
            if not synopsis:
                return {"success": False, "error": "AI returned empty synopsis"}

            # 兜底：若模型仍未使用正确主角名，进行一次低温修正规范化。
            if protagonist_name and protagonist_name not in synopsis:
                fix_prompt = f"""{style_section}请在不改变剧情信息与文风的前提下，修正下方简介中的主角姓名。
要求：
1. 主角姓名统一为「{protagonist_name}」。
2. 删除/替换所有其他疑似主角名（如同音字、误写名）。
3. 仅输出修正后的简介正文。

原简介：
{synopsis}
"""
                fixed = await self.ai_service.chat(
                    [{"role": "user", "content": fix_prompt}],
                    temperature=0.2,
                    max_tokens=1000
                )
                fixed_synopsis = self._safe_text(fixed).strip()
                if fixed_synopsis:
                    synopsis = fixed_synopsis
            
            # 更新状态
            def apply_synopsis(s: Dict[str, Any]) -> None:
                project = s.setdefault("project_info", {})
                project["description"] = synopsis

            self._update_state(apply_synopsis)
            
            return {"success": True, "synopsis": synopsis}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_generate_titles(self) -> Dict[str, Any]:
        """AI 根据现有题材和设定灵感起名"""
        if not self.ai_service:
            return {"success": False, "error": "AI Service not configured"}
            
        try:
            state = self._load_state() or {}
            project_info = state.get("project_info", {})
            genre = project_info.get("genre", "修仙")
            substyle = canonical_substyle_id(genre, project_info.get("substyle", state.get("substyle", "")))
            style_bundle, normalized_genre, normalized_substyle = self._build_stage_style_bundle(
                genre,
                substyle,
                stage="书名生成",
                genre_style_chars=900,
                genre_examples_chars=900,
                substyle_examples_chars=700,
            )
            substyle_display = normalized_substyle or "默认子风格"
            style_section = f"【当前阶段题材协议】\n{style_bundle}\n\n" if style_bundle else ""
            
            world = self._read_file(self.project_root / "设定集" / "世界观.md")
            char = self._read_file(self.project_root / "设定集" / "主角卡.md")
            outline = self._read_file(self.project_root / "大纲" / "总纲.md")
            
            prompt = f"""{style_section}请为一部{normalized_genre}题材、子风格为{substyle_display}的小说起10个吸引人的书名。
            
【题材】
{normalized_genre} / {substyle_display}

【现有设定参考】
{world[:600] if world else "（暂无详细世界观）"}
{char[:600] if char else "（暂无详细主角卡）"}

【剧情大纲参考】
{outline[:1000] if outline else "（暂无详细大纲）"}

【要求】
1. 书名要严格符合上述题材/子风格创作协议和当前市场感受。
2. 风格多样化：有的霸气、有的文艺、有的直白（如：书名中包含金手指）。
3. 每一个书名后面必须附带简短的推荐理由（解析亮点）。
4. 格式严格要求：书名 | 推荐理由

例如：
大秦：开局祖龙求我监国 | 蹭大秦热度，开局爽点明确
只想躺平的我被迫无敌了 | 反套路，突显轻松搞笑风格

请直接输出列表，不要有序号。"""

            response = await self.ai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=1000
            )
            response = self._safe_text(response).strip()
            if not response:
                return {"success": False, "error": "AI returned empty titles response"}
            
            # 解析书名（按行分割）
            lines = response.strip().split("\n")
            titles = []
            for line in lines:
                # 去掉行首可能的序号 (如 1. )
                clean_line = re.sub(r"^\d+[\.、\s]+", "", line.strip())
                if "|" in clean_line:
                    parts = clean_line.split("|")
                    title = parts[0].strip()
                    reason = parts[1].strip()
                    if title:
                        titles.append({"title": title, "reason": reason})
                elif clean_line:
                     # 兼容没有 | 的情况
                     titles.append({"title": clean_line, "reason": "AI 推荐"})
            
            return {"success": True, "titles": titles[:10]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_generate_ending_plan(self, remaining_chapters: int = 5) -> Dict[str, Any]:
        """生成收尾规划，统一走题材/子风格 stage prompt 体系。"""
        if not self.ai_service:
            return {"success": False, "error": "AI Service not configured"}

        remaining = max(1, int(remaining_chapters or 1))

        try:
            state = self._load_state() or {}
            project_info = state.get("project_info", {}) if isinstance(state.get("project_info"), dict) else {}
            title = self._safe_text(project_info.get("title", "未命名项目")).strip() or "未命名项目"
            style_bundle, normalized_genre, normalized_substyle = self._build_project_stage_style_bundle(
                stage="收尾规划",
                genre_style_chars=1200,
                genre_examples_chars=1000,
                substyle_examples_chars=800,
            )
            substyle_display = normalized_substyle or "默认子风格"
            style_section = f"【当前阶段题材协议】\n{style_bundle}\n\n" if style_bundle else ""

            outline = self._read_file(self.project_root / "大纲" / "总纲.md")
            outline_for_prompt = self._compress_outline_for_prompt(outline, 12000) if outline else "（无）"
            protagonist_card = self._truncate_text(
                self._read_file(self.project_root / "设定集" / "主角卡.md"),
                2400,
                keep_tail=False,
            ) or "（无）"
            realtime_status = self._truncate_text(
                self._read_file(self.project_root / "设定集" / "实时状态.md"),
                2600,
                keep_tail=True,
            ) or "（无）"

            chapters_dir = self.project_root / "正文"
            chapter_files = sorted(chapters_dir.glob("第*章*.md")) if chapters_dir.exists() else []
            completed_chapters = len(chapter_files)
            last_chapter_num = 0
            last_chapter_name = ""
            for path in chapter_files:
                match = re.search(r"第0*(\d+)章", path.stem)
                if not match:
                    continue
                try:
                    last_chapter_num = max(last_chapter_num, int(match.group(1)))
                except ValueError:
                    continue
            if not last_chapter_num:
                try:
                    last_chapter_num = int(state.get("current_chapter", 0) or 0)
                except Exception:
                    last_chapter_num = 0
            if chapter_files:
                last_chapter_name = chapter_files[-1].stem
            next_chapter_num = max(1, last_chapter_num + 1)

            continuity_summary = ""
            if last_chapter_num > 0:
                continuity_summary = self._read_file(
                    self.project_root / "正文" / ".continuity" / f"第{last_chapter_num}章_状态.md"
                )
            continuity_for_prompt = self._truncate_text(
                continuity_summary,
                1800,
                keep_tail=True,
            ) if continuity_summary else "（无）"

            current_progress_lines = [
                f"- 已完成章节数：{completed_chapters}",
                f"- 当前已写到：第{last_chapter_num}章" if last_chapter_num else "- 当前已写到：尚未开始正文",
                f"- 最新章节文件：{last_chapter_name or '（无）'}",
                f"- 后续规划起始章节号：第{next_chapter_num}章",
                f"- 本次需要规划章数：{remaining}",
            ]
            current_progress = "\n".join(current_progress_lines)

            prompt = f"""{style_section}你是资深网文完结策划主编。请为小说《{title}》规划最后 {remaining} 章的收尾大纲。

【题材】
{normalized_genre} / {substyle_display}

【当前进度】
{current_progress}

【主角卡摘要】
{protagonist_card}

【实时状态摘要】
{realtime_status}

【最近连续性摘要】
{continuity_for_prompt}

【总纲】
{outline_for_prompt}

【任务】
1. 严格遵守上述题材/子风格创作协议，给出符合当前题材兑现方式的收尾方案。
2. 必须回收关键伏笔，保证节奏递进，并让结局与既有设定、总纲、主角状态一致。
3. 章节号必须从第{next_chapter_num}章开始连续编号，共 {remaining} 章。
4. 每章都要写清楚：章节号、标题、剧情概要、本章核心作用。
5. 只输出合法 JSON，不要 Markdown 代码块，不要解释。

【JSON 输出格式】
{{
  "ending_strategy": "收尾策略简述（200字内）",
  "ending_straregy": "同 ending_strategy，兼容旧前端字段",
  "chapters": [
    {{
      "chapter_num": {next_chapter_num},
      "title": "章节标题",
      "summary": "章节剧情概要（100字+）",
      "purpose": "本章核心作用"
    }}
  ]
}}"""

            data = await self._chat_json_with_retry(
                prompt,
                temperature=0.5,
                max_tokens=4200,
                retries=2,
            )
            if not data:
                return {"success": False, "error": "AI 规划失败: 未返回可解析 JSON"}

            strategy = self._safe_text(data.get("ending_strategy", data.get("ending_straregy", ""))).strip()
            if strategy:
                data["ending_strategy"] = strategy
                data["ending_straregy"] = strategy

            chapters = data.get("chapters", [])
            if not isinstance(chapters, list):
                chapters = []

            normalized_chapters: List[Dict[str, Any]] = []
            for idx, item in enumerate(chapters[:remaining], start=next_chapter_num):
                if not isinstance(item, dict):
                    continue
                chapter_num = item.get("chapter_num", idx)
                try:
                    chapter_num = int(str(chapter_num).strip())
                except Exception:
                    chapter_num = idx
                normalized_chapters.append(
                    {
                        "chapter_num": chapter_num,
                        "title": self._safe_text(item.get("title", "")).strip(),
                        "summary": self._safe_text(item.get("summary", "")).strip(),
                        "purpose": self._safe_text(item.get("purpose", "")).strip(),
                    }
                )
            if not normalized_chapters:
                return {"success": False, "error": "AI 规划失败: 未生成可用章节列表"}
            data["chapters"] = normalized_chapters
            return {"success": True, "plan": data}
        except Exception as e:
            return {"success": False, "error": f"AI 规划失败: {str(e)}"}

    def _save_state(self, state: Dict):
        """保存 state.json"""
        state_file = self.webnovel_dir / "state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with self._locked_file(state_file):
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _update_state(self, updater) -> Dict[str, Any]:
        """在同一文件锁内完成 state.json 的读-改-写，避免并发覆盖。"""
        state_file = self.webnovel_dir / "state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with self._locked_file(state_file):
            state: Dict[str, Any] = {}
            if state_file.exists():
                try:
                    state = json.loads(state_file.read_text(encoding="utf-8"))
                except Exception:
                    state = {}
            updater(state)
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            return state

    async def execute_replan_outline_stream(self, guidance: str = ""):
        """流式重新规划总纲"""
        def make_event(type, **kwargs):
            return json.dumps({"type": type, **kwargs}, ensure_ascii=False)

        yield make_event("step", name="加载设定上下文", status="processing")
        try:
            state = self._load_state() or {}
            project_info = state.get("project_info", {})
            title = project_info.get("title", "未命名项目")
            genre = project_info.get("genre", state.get("genre", "修仙"))
            substyle = canonical_substyle_id(genre, project_info.get("substyle", state.get("substyle", "")))
            
            world = self._read_file(self.project_root / "设定集" / "世界观.md")
            power = self._read_file(self.project_root / "设定集" / "力量体系.md")
            char = self._read_file(self.project_root / "设定集" / "主角卡.md")
            gold_finger = self._read_file(self.project_root / "设定集" / "金手指设计.md")
            entity_libraries = self._load_entity_libraries_summary()
            current_outline = self._read_file(self.project_root / "大纲" / "总纲.md")
            budgets = self._get_context_budgets("outline_replan")

            try:
                genre_tropes = self._load_reference("webnovel-init", "genre-tropes.md")
            except Exception:
                genre_tropes = ""
            yield make_event("step", name="加载设定上下文", status="completed")

            yield make_event("step", name="AI 规划总纲", status="processing")
            world_for_prompt = self._truncate_text(world, budgets.get("world", 1200), keep_tail=False)
            power_for_prompt = self._truncate_text(power, budgets.get("power", 1200), keep_tail=False)
            char_for_prompt = self._truncate_text(char, budgets.get("char", 1200), keep_tail=False)
            gold_finger_for_prompt = self._truncate_text(gold_finger, budgets.get("gold_finger", 1400), keep_tail=False)
            entity_for_prompt = self._truncate_text(entity_libraries, budgets.get("entity_libraries", 1400), keep_tail=False)
            trope_for_prompt = self._load_genre_trope_focus(genre, genre_tropes, budgets.get("genre_tropes", 1200))
            style_for_prompt = self._load_genre_style_guide(genre, max_chars=1800)
            independent_stage_prompt = self._build_independent_stage_prompt_block(
                genre,
                substyle,
                stage="总纲重写",
            )
            substyle_instruction = self._build_substyle_instruction(genre, substyle, stage="总纲重写")
            substyle_examples = self._load_substyle_examples(genre, substyle, max_chars=budgets.get("genre_examples", 700))
            example_for_prompt = self._load_genre_style_examples(genre, substyle, max_chars=budgets.get("genre_examples", 900))
            genre_guard = self._build_genre_guard_instruction(genre, stage="总纲重写")
            positive_style_instruction = self._build_genre_positive_style_instruction(genre, stage="总纲重写")
            guidance_for_prompt = self._truncate_text(guidance, budgets.get("guidance", 1600), keep_tail=False)
            outline_for_prompt = self._compress_outline_for_prompt(
                current_outline,
                budgets.get("current_outline", 12000),
            )

            prompt = f"""请为《{title}》重新规划全书总纲。

【题材】
{genre} / {substyle}

{independent_stage_prompt if independent_stage_prompt else ""}

【题材锁定】
{genre_guard}

【题材笔调校准】
{positive_style_instruction}

【子风格锁定】
{substyle_instruction if substyle_instruction else "（无）"}

【用户指导意见】
{guidance_for_prompt}

【设定参考】
{world_for_prompt}
{power_for_prompt}
{char_for_prompt}
{gold_finger_for_prompt}
{entity_for_prompt}

【参考：题材核心节奏】
{trope_for_prompt}
{style_for_prompt}
【参考：子风格示例（按当前子风格抽取）】
{substyle_examples if substyle_examples else "（无）"}
【参考：题材表达示例（按当前题材动态加载）】
{example_for_prompt if example_for_prompt else "（无）"}
要求：学习风格而非复写句子。

【当前文稿】
{outline_for_prompt}

【核心任务】
请**完整重写**上述总纲文件。如果当前文稿为空或仅有骨架，请尽情发挥。
结构要求：
1. 卷名格式：## 第X卷 《卷名》（约XX-XX章）
2. 为每一卷（建议10-12卷）设计：
   - **预计章数**：如"约50-60章"
   - **核心冲突**：本卷主要矛盾
   - **关键爽点**：让读者爽的高光时刻
   - **卷末高潮**：本卷结局
   - **关键伏笔**：为后续埋下的线索
3. 整体节奏要前松后紧，每一卷都要有明确的升级或地图切换。

格式示例：
## 第1卷 《崛起之初》（约50-60章）
- **预计章数**：50-60章
- **核心冲突**：废柴少年获得系统，从底层崛起
- **关键爽点**：首次打脸装逼，废柴逆袭
- **卷末高潮**：击败宗门内最大敌人

请输出完整的 Markdown 内容："""

            # 动态计算 max_tokens：根据目标章节数估算
            # 假设平均每卷 50 章，每卷摘要约 150 tokens
            # 对于 1200 章的小说（约 12 卷），需要约 12 * 150 = 1800 tokens
            # 加上格式和说明，设置为 12000 确保完整
            state = self._load_state() or {}
            target_chapters = state.get("project_info", {}).get("target_chapters", 600)
            estimated_volumes = max(1, (target_chapters + 49) // 50)  # 向上取整
            dynamic_max_tokens = max(6000, estimated_volumes * 200 + 2000)

            full_content = ""
            async for chunk in self.ai_service.chat_stream(
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=dynamic_max_tokens
            ):
                if not chunk:
                    continue
                if chunk.startswith("[ERROR]"):
                    yield make_event("error", message=chunk)
                    return
                full_content += chunk
                yield make_event("content", chunk=chunk)

            (self.project_root / "大纲" / "总纲.md").write_text(full_content, encoding="utf-8")
            self._clear_outline_invalidation_state()

            # 从大纲中提取主角名，确保主角档案和 state.json 同步
            protagonist_name = self._resolve_protagonist_name()
            if protagonist_name:
                self._sync_protagonist_profile(protagonist_name)

            yield make_event("step", name="AI 规划总纲", status="completed")
            yield make_event("done", success=True, message="总纲规划完成")

        except Exception as e:
            yield make_event("error", message=str(e))

    async def execute_replan_outline(self, guidance: str = "") -> Dict[str, Any]:
        """AI 重写总纲 (兼容版)"""
        full_content = ""
        success = False
        async for event_str in self.execute_replan_outline_stream(guidance):
            event = json.loads(event_str)
            if event["type"] == "content":
                full_content += event["chunk"]
            elif event["type"] == "done":
                success = event["success"]
        return {"success": success, "content": full_content}

    # ==================== webnovel-plan ====================

    async def execute_plan_stream(self, volume: int, chapters_count: int = 30):
        """流式执行 webnovel-plan Skill 完整工作流"""
        def make_event(type, **kwargs):
            return json.dumps({"type": type, **kwargs}, ensure_ascii=False)

        invalidation_reason = self._get_outline_invalidation_reason()
        if invalidation_reason and volume > 0:
            yield make_event(
                "error",
                message=f"{invalidation_reason} 请先重新生成总纲，再规划分卷大纲。",
            )
            return

        # Step 1-3: 加载各类指南和套路
        yield make_event("step", name="加载规划指南与题材套路", status="processing")
        cool_points = self._load_reference("webnovel-plan", "cool-points-guide.md")
        strand_weave = self._load_reference("webnovel-plan", "strand-weave-pattern.md")
        genre_tropes = self._load_reference("webnovel-init", "genre-tropes.md")
        yield make_event("step", name="加载规划指南与题材套路", status="completed")

        # Step 4: 加载项目数据与总纲
        yield make_event("step", name="分析总纲上下文", status="processing")
        state = self._load_state()
        full_outline = self._read_file(self.project_root / "大纲" / "总纲.md")
        budgets = self._get_context_budgets("outline_plan")
        
        volume_outline = ""
        if full_outline:
            # re 已在文件顶部导入
            pattern = rf"##\s*第\s*{volume}\s*卷[^\n]*\n(.*?)(?=##\s*第\s*\d+\s*卷|$)"
            match = re.search(pattern, full_outline, re.DOTALL)
            volume_outline = match.group(0).strip() if match else full_outline
        
        chapter_planning = self._load_reference("webnovel-plan", "outlining/chapter-planning.md")
        conflict_design = self._load_reference("webnovel-plan", "outlining/conflict-design.md")
        outline_structure = self._load_reference("webnovel-plan", "outlining/outline-structure.md")
        yield make_event("step", name="分析总纲上下文", status="completed")

        # Step 7: 生成详细大纲
        yield make_event("step", name="AI 规划详细大纲", status="processing")
        if self.ai_service:
            genre = state.get("project_info", {}).get("genre", "修仙") if state else "修仙"
            substyle = canonical_substyle_id(
                genre,
                state.get("project_info", {}).get("substyle", state.get("substyle", "")) if state else "",
            )
            title = state.get("project_info", {}).get("title", "未命名") if state else "未命名"
            
            # 加载设定集作为参考
            world = self._read_file(self.project_root / "设定集" / "世界观.md")
            power = self._read_file(self.project_root / "设定集" / "力量体系.md")
            char = self._read_file(self.project_root / "设定集" / "主角卡.md")
            gold_finger = self._read_file(self.project_root / "设定集" / "金手指设计.md")
            entity_libraries = self._load_entity_libraries_summary()
            
            # 加载上一卷详细大纲（确保连贯性）
            prev_volume_outline = ""
            outline_dir = self.project_root / "大纲"
            if volume > 1:
                # 尝试更灵活的查找（支持空格）
                target_vol_num = volume - 1
                if outline_dir.exists():
                    self._debug(f"[DEBUG] 正在寻找上一卷（第 {target_vol_num} 卷）大纲...")
                    files = sorted(outline_dir.glob("*.md"))
                    for f in files:
                        # 匹配 "第 X 卷" 或 "第X卷"
                        if re.search(rf"第\s*{target_vol_num}\s*卷", f.name):
                             self._debug(f"[DEBUG] 找到上一卷大纲文件: {f.name}")
                             prev_volume_outline = f.read_text(encoding="utf-8")
                             self._debug(f"[DEBUG] 读取内容长度: {len(prev_volume_outline)} 字符")
                             break
                             
                # 旧的简单查找逻辑作为备选（如果上面的没找到）
                if not prev_volume_outline:
                    prev_vol_files = list(outline_dir.glob(f"第{target_vol_num}卷*.md"))
                    if prev_vol_files:
                        prev_volume_outline = prev_vol_files[0].read_text(encoding="utf-8")
            
            # 计算本卷起始章节号（基于前几卷的章节数）
            start_chapter = 1
            if outline_dir.exists() and volume > 1:
                all_outline_files = list(outline_dir.glob("*.md"))
                
                for prev_vol in range(1, volume):
                    prev_content = ""
                    # 在所有文件中寻找匹配该卷的文件
                    for f in all_outline_files:
                         if re.search(rf"第\s*{prev_vol}\s*卷", f.name):
                             prev_content = f.read_text(encoding="utf-8")
                             break
                    
                    if prev_content:
                        # 找最大章节号
                        chap_matches = re.findall(r"第\s*(\d+)\s*章", prev_content)
                        if chap_matches:
                            max_chap = max(int(c) for c in chap_matches)
                            if max_chap >= start_chapter:
                                start_chapter = max_chap + 1
            
            end_chapter = start_chapter + chapters_count - 1

            volume_outline_for_prompt = self._compress_outline_for_prompt(
                volume_outline,
                budgets.get("volume_outline", 2600),
            )
            world_for_prompt = self._truncate_text(world, budgets.get("world", 1200), keep_tail=False)
            power_for_prompt = self._truncate_text(power, budgets.get("power", 1200), keep_tail=False)
            char_for_prompt = self._truncate_text(char, budgets.get("char", 1000), keep_tail=False)
            gold_finger_for_prompt = self._truncate_text(gold_finger, budgets.get("gold_finger", 1400), keep_tail=False)
            entity_for_prompt = self._truncate_text(entity_libraries, budgets.get("entity_libraries", 1400), keep_tail=False)
            chapter_planning_for_prompt = self._truncate_text(chapter_planning, budgets.get("chapter_planning", 1200), keep_tail=False)
            conflict_design_for_prompt = self._truncate_text(conflict_design, budgets.get("conflict_design", 1000), keep_tail=False)
            trope_for_prompt = self._load_genre_trope_focus(genre, genre_tropes, budgets.get("genre_tropes", 1000))
            style_for_prompt = self._load_genre_style_guide(genre, max_chars=1600)
            independent_stage_prompt = self._build_independent_stage_prompt_block(
                genre,
                substyle,
                stage="分卷大纲",
            )
            substyle_instruction = self._build_substyle_instruction(genre, substyle, stage="分卷大纲")
            substyle_examples = self._load_substyle_examples(genre, substyle, max_chars=budgets.get("genre_examples", 700))
            example_for_prompt = self._load_genre_style_examples(genre, substyle, max_chars=budgets.get("genre_examples", 900))
            genre_guard = self._build_genre_guard_instruction(genre, stage="分卷大纲")
            positive_style_instruction = self._build_genre_positive_style_instruction(genre, stage="分卷大纲")
            
            # 构建上一卷上下文摘要（取最后1500字，包含结尾剧情）
            prev_vol_context = ""
            if prev_volume_outline:
                prev_vol_context = f"""【上一卷（第 {volume - 1} 卷）详细大纲 - 用于衔接】
{self._truncate_text(prev_volume_outline, budgets.get("prev_volume_outline", 2600), keep_tail=True)}

⚠️ **衔接要求**：新卷第一章必须自然承接上一卷结尾的剧情走向，不能突然跳转或割裂！
"""

            opening_rule = (
                "2. **新卷第一章必须衔接上一卷结尾**，不能突然跳场景或时间跳跃！"
                if volume > 1
                else '2. **第1卷第1章必须作为全书开篇起笔**，禁止出现"承接上卷/承接开篇结尾/接上回"等表述。'
            )
            
            # 读取当前活跃角色表
            character_roster = ""
            character_file = self.project_root / "设定集" / "角色库" / "活跃角色.md"
            if character_file.exists():
                character_roster = self._read_file(character_file)
            
            character_context = ""
            if character_roster:
                character_context = f"""
【当前活跃角色表】
{self._truncate_text(character_roster, budgets.get("character_roster", 1800), keep_tail=True)}

⚠️ **角色规划要求**：本卷大纲必须包含"本卷角色规划"部分，列出：
1. **新登场角色**：本卷新出现的重要角色（名字、身份、首次出场章节、入场方式）
2. **下线角色**：本卷死亡或离开剧情的角色（名字、下线章节、下线方式）
3. **状态变化**：角色重要状态变化（如怀孕、生产、突破等）
"""
            
            system_prompt = f"""你是一位专业的网文大纲策划师。请严格根据【总纲】和【设定】，为第 {volume} 卷生成详细大纲。

【小说信息】
- 书名：《{title}》
- 题材：{genre}
- 子风格：{substyle}

{independent_stage_prompt if independent_stage_prompt else ""}

【题材锁定】
{genre_guard}

【题材笔调校准】
{positive_style_instruction}

【子风格锁定】
{substyle_instruction if substyle_instruction else "（无）"}

{prev_vol_context}

{character_context}

【第 {volume} 卷总纲摘要】
{volume_outline_for_prompt if volume_outline_for_prompt else "（暂无，请自行构思）"}

【世界观设定】
{world_for_prompt if world_for_prompt else "（暂无）"}

【力量体系】
{power_for_prompt if power_for_prompt else "（暂无）"}

【主角设定】
{char_for_prompt if char_for_prompt else "（暂无）"}

【金手指/系统设定】
{gold_finger_for_prompt if gold_finger_for_prompt else "（暂无）"}

【实体库标准名】
{entity_for_prompt if entity_for_prompt else "（暂无）"}

【规划参考】
{chapter_planning_for_prompt if chapter_planning_for_prompt else ""}
{conflict_design_for_prompt if conflict_design_for_prompt else ""}
{trope_for_prompt if trope_for_prompt else ""}
{style_for_prompt if style_for_prompt else ""}
【子风格示例（按当前子风格抽取）】
{substyle_examples if substyle_examples else "（无）"}
【题材示例（按当前题材动态加载）】
{example_for_prompt if example_for_prompt else "（无）"}
要求：学习表达风格，不照抄句子。

【输出要求】
1. 第一行必须是卷标题，格式：# 第 {volume} 卷：【卷名】（第 {start_chapter}-{end_chapter} 章）
{opening_rule}
3. 必须严格遵循上方总纲摘要中的剧情走向和爽点
4. 生成第 {start_chapter} 章到第 {end_chapter} 章，共 {chapters_count} 章的详细大纲
5. 章节编号必须从 {start_chapter} 开始，依次递增！
6. 每章格式：**第X章：章节标题**，包含主要情节、爽点设计
7. 确保人物名、地点名、势力名与设定一致
8. 使用 Markdown 格式
9. **在大纲末尾添加"本卷角色规划"部分**（如果有活跃角色表）

⚠️ **【极重要】数值变化必须明确标注**：
涉及战斗、伤亡、资源消耗的章节，必须在大纲中**明确写出具体数字或估算范围**！
✅ 正确示例：
   - 【伤亡】外围死士阵亡约2000人，仅存约1200人
   - 【消耗】爆炎符消耗50张，剩余约30张
   - 【气运】家族气运-500（因人员死亡）
   - 【状态】顾承厄重伤（内脏震荡，需休养3天）
❌ 错误示例：
   - "死伤惨重"（太模糊！必须写具体数字）
   - "消耗了大量资源"（必须说明消耗了什么、多少）"""

            # 动态计算 max_tokens：基础 2000 + 每章 250 tokens
            # 60章需要约 17000 tokens，确保不会被截断
            dynamic_max_tokens = max(8000, 2000 + chapters_count * 250)

            full_content = ""
            async for chunk in self.ai_service.chat_stream(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请详细规划第 {volume} 卷的 {chapters_count} 章大纲"}
                ],
                temperature=0.7,
                max_tokens=dynamic_max_tokens
            ):
                if not chunk:
                    continue
                if chunk.startswith("[ERROR]"):
                    yield make_event("error", message=chunk)
                    return
                full_content += chunk
                yield make_event("content", chunk=chunk)

            outline_dir = self.project_root / "大纲"
            outline_dir.mkdir(parents=True, exist_ok=True)
            outline_file = outline_dir / f"第{volume}卷-详细大纲.md"
            outline_file.write_text(full_content, encoding="utf-8")

            # 删除初始化时创建的占位文件（避免同卷出现两个文件）
            placeholder = outline_dir / f"第{volume}卷.md"
            if placeholder.exists() and placeholder != outline_file:
                placeholder.unlink()
            
            # 自动为大纲中的新角色创建基础档案
            yield make_event("step", name="创建角色档案", status="processing")
            try:
                await self._create_character_files_from_outline(volume, full_content)
                # 确保主角档案存在于角色库和活跃角色表
                protagonist_name = self._resolve_protagonist_name()
                if protagonist_name:
                    self._sync_protagonist_profile(protagonist_name)
                yield make_event("step", name="创建角色档案", status="completed")
            except Exception as e:
                print(f"[角色系统] 创建角色档案失败: {e}")
                yield make_event("step", name="创建角色档案", status="skipped")
            
            yield make_event("step", name="AI 规划详细大纲", status="completed")
            yield make_event("done", success=True, path=str(outline_file), content=full_content)
        else:
            yield make_event("error", message="AI 服务未配置")

    async def execute_plan(self, volume: int, chapters_count: int = 30) -> Dict[str, Any]:
        """执行 webnovel-plan Skill (兼容版)"""
        full_content = ""
        success = False
        path = ""
        async for event_str in self.execute_plan_stream(volume, chapters_count):
            event = json.loads(event_str)
            if event["type"] == "content":
                full_content += event["chunk"]
            elif event["type"] == "done":
                success = event["success"]
                path = event.get("path", "")
        return {"success": success, "content": full_content, "path": path, "steps": []}

    async def execute_polish_outline_stream(self, volume: int, content: str, requirements: str):
        """流式执行大纲润色"""
        def make_event(type, **kwargs):
            return json.dumps({"type": type, **kwargs}, ensure_ascii=False)

        if not self.ai_service:
            yield make_event("error", message="AI 服务未配置")
            return

        yield make_event("step", name="AI 润色大纲", status="processing")
        budgets = self._get_context_budgets("outline_polish")
        content_for_prompt = self._compress_outline_for_prompt(content, budgets.get("content", 12000))
        requirements_for_prompt = self._truncate_text(requirements, budgets.get("requirements", 1800), keep_tail=False)
        genre = self._get_project_genre()
        substyle = self._get_project_substyle()
        independent_stage_prompt = self._build_independent_stage_prompt_block(
            genre,
            substyle,
            stage="大纲润色",
        )
        genre_guard = self._build_genre_guard_instruction(genre, stage="大纲润色")
        positive_style_instruction = self._build_genre_positive_style_instruction(genre, stage="大纲润色")
        substyle_instruction = self._build_substyle_instruction(genre, substyle, stage="大纲润色")
        style_for_prompt = self._load_genre_style_guide(genre, max_chars=1800)
        substyle_examples_for_prompt = self._load_substyle_examples(
            genre,
            substyle,
            max_chars=budgets.get("genre_examples", 700),
        )
        style_examples_for_prompt = self._load_genre_style_examples(
            genre,
            substyle,
            max_chars=budgets.get("genre_examples", 900),
        )
        
        system_prompt = """你是一位专业的网文大纲医生。请根据用户的修改要求，对已有的大纲进行润色和优化。
        
        【核心任务】
        根据用户的【修改要求】，重写或优化大纲内容。
        
        【注意事项】
        1. **结构保持**：尽量保持原有的章节号和整体架构，除非用户要求重组。
        2. **针对性修改**：如果是要求"增加数值"，请在每章末尾补充具体的伤亡/消耗统计。
        3. **格式规范**：输出标准的 Markdown 大纲。
        4. **完整性**：输出完整的大纲内容，不要只输出修改片段。
        
        【数值标记规范（关键）】
        如果用户要求添加数值，请参考以下格式：
        - 【伤亡】xxx (如：死士阵亡500人)
        - 【消耗】xxx (如：气运消耗200点)
        - 【状态】xxx (如：重伤、突破)

        """ + (independent_stage_prompt + "\n\n" if independent_stage_prompt else "") + """

        【题材锁定（最高优先级）】
        当前题材：""" + genre + """
        """ + genre_guard + """
        """ + positive_style_instruction + """
        """ + substyle_instruction + """
        若修改要求未明确要求跨题材试验，文风必须严格锁定在当前题材范式内。

        【题材风格参考】
        """ + (style_for_prompt if style_for_prompt else "（无）") + """

        【子风格示例（按当前子风格抽取）】
        """ + (substyle_examples_for_prompt if substyle_examples_for_prompt else "（无）") + """

        【题材示例（按当前题材动态加载）】
        """ + (style_examples_for_prompt if style_examples_for_prompt else "（无）") + """
        要求：只学习语气与节奏，不照抄原句。
        """
        
        user_prompt = f"""【已有大纲】
{content_for_prompt}

【用户的修改要求】
{requirements_for_prompt}

请根据要求润色大纲（直接输出正文）："""

        full_content = ""
        async for chunk in self.ai_service.chat_stream(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=8000
        ):
            if not chunk:
                continue
            if chunk.startswith("[ERROR]"):
                yield make_event("error", message=chunk)
                return
            full_content += chunk
            yield make_event("content", chunk=chunk)
            
        # 自动保存
        if volume == 0:
             outline_file = self.project_root / "大纲" / "总纲.md"
        else:
             outline_file = self.project_root / "大纲" / f"第{volume}卷-详细大纲.md"
             
        try:
            outline_file.parent.mkdir(parents=True, exist_ok=True)
            outline_file.write_text(full_content, encoding="utf-8")
        except Exception as e:
            print(f"Error saving polished outline: {e}")
        
        yield make_event("step", name="AI 润色大纲", status="completed")
        yield make_event("done", success=True, content=full_content)

    # ==================== webnovel-write ====================

    async def execute_write_stream(self, chapter: int, word_count: int = 3500):
        """流式执行 webnovel-write Skill 完整工作流"""
        def make_event(type, **kwargs):
            return json.dumps({"type": type, **kwargs}, ensure_ascii=False)

        # DEBUG: 打印当前使用的项目路径
        self._debug(f"{'=' * 60}")
        self._debug(f"[DEBUG] 当前项目路径: {self.project_root}")
        self._debug(f"[DEBUG] 大纲目录: {self.project_root / '大纲'}")
        self._debug(f"[DEBUG] 正文目录: {self.project_root / '正文'}")
        self._debug(f"{'=' * 60}")

        invalidation_reason = self._get_outline_invalidation_reason()
        if invalidation_reason:
            yield make_event(
                "error",
                message=f"{invalidation_reason} 请先重新生成总纲/卷纲，再继续写作。",
            )
            return

        # Step 1: Context Agent 搜集上下文
        yield make_event("step", name="Context Agent 搜集上下文", status="processing")
        context_pack = await self._execute_context_agent(chapter)
        yield make_event("step", name="Context Agent 搜集上下文", status="completed")

        # Step 1.5: 加载核心约束
        yield make_event("step", name="加载写作约束", status="processing")
        core_constraints = self._load_reference("webnovel-write", "core-constraints.md")
        chapter_outline = context_pack.get("core", {}).get("chapter_outline", "")
        yield make_event("step", name="加载写作约束", status="completed")

        # 结构兜底：未命中本章大纲时直接中断，避免脱纲创作
        if not chapter_outline or chapter_outline.strip() in {f"第{chapter}章"}:
            yield make_event("error", message=f"未找到第{chapter}章大纲，请先在卷大纲中补齐章节标题后再执行 AI 写作")
            return

        # Step 2: 生成章节内容
        yield make_event("step", name="AI 撰写正文 (流式)", status="processing")
        if self.ai_service:
            try:
                # 注意：这里我们需要对 _generate_chapter_content 进行改造或手动实现流式部分
                # 这里我们直接手动实现流式逻辑以获得更好的控制
                full_content = ""
                async for chunk in self._generate_chapter_content_stream(
                    chapter, context_pack, core_constraints, word_count
                ):
                    if not chunk:
                        continue
                    if chunk.startswith("[ERROR]"):
                        yield make_event("error", message=chunk)
                        return
                    full_content += chunk
                    yield make_event("content", chunk=chunk)

                # Step 2.2: 字数统计（仅记录，不截断 — 截断会破坏章节完整性）
                raw_len = len(full_content)
                if raw_len > 4000:
                    self._debug(f"[WRITE-LENGTH WARN] 第{chapter}章字数 {raw_len}，超过 4000 字目标，但不截断以保证章节完整性")

                yield make_event("step", name="AI 撰写正文 (流式)", status="completed")
                streamed_content = full_content

                # Step 2.5: 设定冲突守卫（扫描 + 自动修正）
                yield make_event("step", name="设定冲突扫描与修正", status="processing")
                try:
                    guard_result = await self._run_setting_conflict_guard(
                        chapter=chapter,
                        content=full_content,
                        context_pack=context_pack,
                    )
                    guarded_content = self._safe_text(guard_result.get("content", ""))
                    if guarded_content:
                        full_content = guarded_content
                    if full_content != streamed_content:
                        # 修正后回推一条"替换型内容事件"，让前端不必依赖 done.content 也能拿到最终稿。
                        yield make_event("content", chunk="", full=full_content, replace=True)
                    yield make_event("consistency_guard", result=guard_result.get("report", {}))
                except Exception as guard_err:
                    print(f"[一致性守卫] 运行失败: {guard_err}")
                    yield make_event("error", message=f"设定冲突守卫失败: {guard_err}", level="warning")
                yield make_event("step", name="设定冲突扫描与修正", status="completed")

                # Step 2.6: 读者正文清洗（移除记录型标签，保留纯阅读体验）
                yield make_event("step", name="正文展示清洗", status="processing")
                sanitized_content, sanitize_report = self._sanitize_reader_facing_content(full_content)
                removed_count = int(sanitize_report.get("removed_lines", 0)) + int(sanitize_report.get("removed_inline_tags", 0))
                if sanitized_content and sanitized_content != full_content:
                    full_content = sanitized_content
                    yield make_event("content", chunk="", full=full_content, replace=True)
                if removed_count > 0:
                    self._debug(f"[WRITE-SANITIZE DEBUG] 第{chapter}章清理记录标签 {removed_count} 处")
                yield make_event("step", name="正文展示清洗", status="completed")

                # Step 2.7: 结尾完整性修复（防半句截断）
                yield make_event("step", name="结尾完整性检查", status="processing")
                try:
                    if self._has_abrupt_tail(full_content):
                        repaired = await self._repair_abrupt_tail(
                            chapter=chapter,
                            genre=self._get_project_genre(),
                            chapter_outline=chapter_outline,
                            content=full_content,
                        )
                        repaired, repaired_report = self._sanitize_reader_facing_content(repaired)
                        repaired_removed = int(repaired_report.get("removed_lines", 0)) + int(
                            repaired_report.get("removed_inline_tags", 0)
                        )
                        if repaired_removed > 0:
                            self._debug(f"[TAIL-REPAIR SANITIZE] 第{chapter}章清理记录标签 {repaired_removed} 处")
                        if repaired and repaired != full_content:
                            full_content = repaired
                            yield make_event("content", chunk="", full=full_content, replace=True)
                except Exception as tail_err:
                    print(f"[TAIL-REPAIR ERROR] {tail_err}")
                    yield make_event("error", message=f"结尾完整性修复失败: {tail_err}", level="warning")
                yield make_event("step", name="结尾完整性检查", status="completed")
                
                # Step 3 & 4 (简化处理)
                yield make_event("step", name="AI 质量审查", status="processing")
                if self.ai_service:
                    # 使用完整的 execute_review 函数，包含角色档案等上下文
                    review_result = await self.execute_review(chapter_id=chapter, content=full_content)
                    
                    # DEBUG
                    raw = review_result.get('raw_review', '')
                    self._debug(f"[WRITE-REVIEW DEBUG] 审查返回 success={review_result.get('success')}, 长度={len(raw)}")
                    
                    # 发送审查结果
                    yield make_event("review", result=review_result)

                yield make_event("step", name="AI 质量审查", status="completed")
                
                # 统一链路：状态抽取改为保存时触发，避免流式写作与保存双通道重复更新
                yield make_event("step", name="等待保存后更新角色状态", status="processing")
                yield make_event("step", name="等待保存后更新角色状态", status="completed")
                
                # 注意：RAG 索引、连续性摘要、角色状态抽取都在用户手动保存后触发，
                # 避免"未采纳草稿"污染持久化数据。
                
                yield make_event("done", success=True, content=full_content)
            except Exception as e:
                yield make_event("error", message=str(e))
        else:
            yield make_event("error", message="AI 服务未配置")

    async def execute_write(self, chapter: int, word_count: int = 3500) -> Dict[str, Any]:
        """执行 webnovel-write Skill (兼容版)"""
        full_content = ""
        success = False
        async for event_str in self.execute_write_stream(chapter, word_count):
            event = json.loads(event_str)
            if event["type"] == "content":
                full_content += event["chunk"]
            elif event["type"] == "done":
                success = event["success"]
                done_content = self._safe_text(event.get("content", "")).strip()
                if done_content:
                    full_content = done_content
        return {"success": success, "content": full_content, "steps": []}

    async def execute_polish(self, chapter_id: int, content: str, suggestions: str, mode: str = "rewrite") -> Dict[str, Any]:
        """执行润色工作流（由于历史原因保留，新版前端建议使用 _stream 版本）"""
        # 调用 AI 进行润色
        if not self.ai_service:
             return {"success": False, "error": "AI Service not initialized"}

        if mode == "targeted_fix":
             try:
                 polished_content, patch_report = await self._run_targeted_fix_edit_pass(chapter_id, content, suggestions)
                 polished_content, sanitize_report = self._sanitize_reader_facing_content(polished_content)
                 removed_count = int(sanitize_report.get("removed_lines", 0)) + int(sanitize_report.get("removed_inline_tags", 0))
                 if removed_count > 0:
                     self._debug(f"[TARGETED-FIX SANITIZE] 清理记录标签 {removed_count} 处")
                 return {
                     "success": True,
                     "content": polished_content,
                     "tail_fix_applied": False,
                     "patch_report": patch_report,
                 }
             except Exception as e:
                 self._debug(f"[DEBUG] execute_polish(targeted_fix): 异常={str(e)}")
                 return {"success": False, "error": str(e)}

        prompt = self._build_polish_prompt(chapter_id, content, suggestions, mode=mode)
        if not self._safe_text(prompt).strip():
             return {"success": False, "error": f"Polish prompt is empty for mode={mode}"}
        self._debug(f"[DEBUG] execute_polish: 输入内容长度={len(content)}, suggestions={suggestions[:100] if suggestions else '(空)'}")
        
        try:
             polished_content = await self.ai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=12000
             )
             polished_content = self._safe_text(polished_content)
             polished_content, sanitize_report = self._sanitize_reader_facing_content(polished_content)
             removed_count = int(sanitize_report.get("removed_lines", 0)) + int(sanitize_report.get("removed_inline_tags", 0))
             if removed_count > 0:
                 self._debug(f"[POLISH-SANITIZE DEBUG] 清理记录标签 {removed_count} 处")

             genre = self._get_project_genre()
             chapter_outline = self._find_chapter_outline(chapter_id)
             tail_fix_applied = False
             if self._has_abrupt_tail(polished_content):
                 repaired = await self._repair_abrupt_tail(
                     chapter=chapter_id,
                     genre=genre,
                     chapter_outline=chapter_outline,
                     content=polished_content,
                 )
                 repaired, tail_sanitize_report = self._sanitize_reader_facing_content(repaired)
                 tail_removed = int(tail_sanitize_report.get("removed_lines", 0)) + int(
                     tail_sanitize_report.get("removed_inline_tags", 0)
                 )
                 if tail_removed > 0:
                     self._debug(f"[POLISH-TAIL-SANITIZE DEBUG] 清理记录标签 {tail_removed} 处")
                 if repaired and repaired != polished_content:
                     polished_content = repaired
                     tail_fix_applied = True

             self._debug(f"[DEBUG] execute_polish: AI输出长度={len(polished_content) if polished_content else 0}")
             self._debug(f"[DEBUG] execute_polish: AI输出前200字={polished_content[:200] if polished_content else '(空)'}")
             return {
                 "success": True,
                 "content": polished_content,
                 "tail_fix_applied": tail_fix_applied,
             }
        except Exception as e:
             self._debug(f"[DEBUG] execute_polish: 异常={str(e)}")
             return {"success": False, "error": str(e)}

    async def execute_polish_stream(self, chapter_id: int, content: str, suggestions: str, mode: str = "rewrite"):
        """执行润色工作流（流式输出）。持久化副作用统一在手动保存后触发。"""
        def make_event(type, **kwargs):
            return json.dumps({"type": type, **kwargs}, ensure_ascii=False)

        if not self.ai_service:
             yield make_event("error", message="AI Service not initialized")
             return

        if mode == "targeted_fix":
             try:
                 yield make_event("step", name="分析审查问题", status="processing")
                 await asyncio.sleep(0)
                 yield make_event("step", name="分析审查问题", status="completed")

                 yield make_event("step", name="生成局部修订补丁", status="processing")
                 full_content, patch_report = await self._run_targeted_fix_edit_pass(chapter_id, content, suggestions)
                 yield make_event("step", name="生成局部修订补丁", status="completed")

                 yield make_event("step", name="应用原文补丁", status="processing")
                 full_content, sanitize_report = self._sanitize_reader_facing_content(full_content)
                 removed_count = int(sanitize_report.get("removed_lines", 0)) + int(sanitize_report.get("removed_inline_tags", 0))
                 if removed_count > 0:
                     self._debug(f"[TARGETED-FIX SANITIZE] 清理记录标签 {removed_count} 处")
                 yield make_event("content", chunk="", full=full_content, replace=True)
                 yield make_event(
                     "step",
                     name=f"应用原文补丁（命中 {len((patch_report or {}).get('applied', []))} 处）",
                     status="completed",
                 )
                 yield make_event("done", content=full_content, patch_report=patch_report)
             except Exception as e:
                 yield make_event("error", message=str(e))
             return

        prompt = self._build_polish_prompt(chapter_id, content, suggestions, mode=mode)
        if not self._safe_text(prompt).strip():
             yield make_event("error", message=f"Polish prompt is empty for mode={mode}")
             return

        try:
             step_name = "AI 正在思考修订方案..." if mode == "targeted_fix" else "AI 正在思考润色方案..."
             yield make_event("step", name=step_name, status="processing")

             # 调用 AI 进行流式润色
             full_content = ""
             async for chunk in self.ai_service.chat_stream(
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=12000
             ):
                   if not chunk:  # 跳过 None 或空字符串
                       continue
                   if chunk.startswith("[ERROR]"):
                       yield make_event("error", message=chunk)
                       return
                   full_content += chunk
                   yield make_event("content", chunk=chunk)

             full_content, sanitize_report = self._sanitize_reader_facing_content(full_content)
             removed_count = int(sanitize_report.get("removed_lines", 0)) + int(sanitize_report.get("removed_inline_tags", 0))
             if removed_count > 0:
                 self._debug(f"[POLISH-SANITIZE DEBUG] 清理记录标签 {removed_count} 处")
             yield make_event("step", name=step_name, status="completed")

             genre = self._get_project_genre()
             chapter_outline = self._find_chapter_outline(chapter_id)
             yield make_event("step", name="结尾完整性检查", status="processing")
             try:
                 if self._has_abrupt_tail(full_content):
                     repaired = await self._repair_abrupt_tail(
                         chapter=chapter_id,
                         genre=genre,
                         chapter_outline=chapter_outline,
                         content=full_content,
                     )
                     repaired, tail_sanitize_report = self._sanitize_reader_facing_content(repaired)
                     tail_removed = int(tail_sanitize_report.get("removed_lines", 0)) + int(
                         tail_sanitize_report.get("removed_inline_tags", 0)
                     )
                     if tail_removed > 0:
                         self._debug(f"[POLISH-TAIL-SANITIZE DEBUG] 清理记录标签 {tail_removed} 处")
                     if repaired and repaired != full_content:
                         full_content = repaired
                         yield make_event("content", chunk="", full=full_content, replace=True)
             except Exception as tail_err:
                 yield make_event("error", message=f"结尾完整性修复失败: {tail_err}", level="warning")
             yield make_event("step", name="结尾完整性检查", status="completed")

             yield make_event("content", chunk="", full=full_content, replace=True)  # ensure frontend has full text

             yield make_event("done")

        except Exception as e:
             yield make_event("error", message=str(e))

    async def execute_review(self, chapter_id: int, content: str = None) -> Dict[str, Any]:
        """执行审查工作流 (使用 review.md Skill)"""
        review_budget = self._get_context_budgets("review")
        content = self._safe_text(content)
        genre = self._get_project_genre()

        # 1. 准备上下文
        chapter_outline = self._find_chapter_outline(chapter_id)
        
        # 获取上一章结尾摘要
        previous_ending = ""
        summaries = self._get_recent_summaries(chapter_id - 1, count=1)
        if summaries:
            previous_ending = f"上一章讲到：{summaries[0]}"
        
        # 尝试读取上一章的实际结尾（如果有文件的话）
        try:
             chapter_files = list((self.project_root / "正文").glob(f"第{chapter_id - 1}章*.md"))
             if chapter_files:
                 prev_content = chapter_files[0].read_text(encoding="utf-8")
                 previous_tail = self._truncate_text(
                     prev_content,
                     review_budget.get("previous_ending", 1200),
                     keep_tail=True,
                 )
                 previous_ending += f"\n\n【上一章实际结尾原文】\n{previous_tail}"
        except Exception:
            pass

        # 2. 加载 Prompt 和参考资料
        review_prompt_tmpl = self._load_project_prompt("review", genre=genre)
        core_constraints = self._load_reference("webnovel-write", "core-constraints.md") or ""
        
        # 加载 webnovel-review skill 中的参考文件
        common_mistakes = self._load_reference("webnovel-review", "common-mistakes.md") or ""
        cool_points = self._load_reference("webnovel-review", "cool-points-guide.md") or ""

        # 填空
        try:
            system_prompt = review_prompt_tmpl.format(
                core_constraints=core_constraints,
                common_mistakes=common_mistakes,
                cool_points=cool_points
            )
        except (KeyError, ValueError):
            # 兼容旧模板或处理 JSON 大括号（ValueError）
            # 如果包含 {scores} 这种 JSON 结构，format 会报错，此时直接用原字符串即可（假设新 prompt 不需要 format）
            system_prompt = review_prompt_tmpl.replace("{core_constraints}", core_constraints).replace("{common_mistakes}", common_mistakes).replace("{cool_points}", cool_points)
        
        # 3. 加载设定文件（用于审核设定一致性）
        gold_finger = self._read_file(self.project_root / "设定集" / "金手指设计.md") or ""
        character_roster = self._read_file(self.project_root / "设定集" / "角色库" / "活跃角色.md") or ""
        worldview = self._read_file(self.project_root / "设定集" / "世界观.md") or ""
        realtime_status = self._read_file(self.project_root / "设定集" / "实时状态.md") or ""
        
        # 3.5 加载角色档案摘要（用于检查角色身份/门派是否正确）
        character_details = self._load_character_details_for_review()
        self._debug(f"[DEBUG] 角色档案摘要长度: {len(character_details)} 字符")

        chapter_outline_for_review = self._truncate_text(
            chapter_outline,
            review_budget.get("chapter_outline", 2200),
            keep_tail=False,
        )
        previous_ending_for_review = self._truncate_text(
            previous_ending,
            review_budget.get("previous_ending", 1200),
            keep_tail=True,
        )
        gold_finger_for_review = self._truncate_text(
            gold_finger,
            review_budget.get("gold_finger", 1400),
            keep_tail=False,
        )
        worldview_for_review = self._truncate_text(
            worldview,
            review_budget.get("worldview", 1400),
            keep_tail=False,
        )
        realtime_status_for_review = self._truncate_text(
            realtime_status,
            review_budget.get("realtime_status", 1400),
            keep_tail=True,
        )
        character_details_for_review = self._truncate_text(
            character_details,
            review_budget.get("character_details", 3200),
            keep_tail=True,
        )
        entity_summary_for_review = self._truncate_text(
            self._load_entity_libraries_summary(),
            review_budget.get("entity_libraries", 1800),
            keep_tail=False,
        )
        content_for_review = self._truncate_text(
            content,
            review_budget.get("content", 9000),
            keep_tail=True,
        )
        should_block_weird_terms = self._should_block_weird_style_terms(
            genre,
            chapter_outline,
            worldview,
            gold_finger,
        )

        # 4. 组装 User Content
        user_content = f"请审查第 {chapter_id} 章（当前题材：{genre}）：\n\n"
        if chapter_outline_for_review:
            user_content += f"【本章大纲（必须严格一致）】\n{chapter_outline_for_review}\n\n"
        if should_block_weird_terms:
            user_content += """【风格跑偏重点检查】
本书当前不是规则怪谈/诡异流。若正文出现明显怪谈母题（如守则闯关、SAN值、污染传播、诡域副本等），请明确标记为"风格跑偏"。\n\n"""
        if self._normalize_genre_key(genre) == "xuanhuan":
            user_content += """【玄幻笔调重点检查】
若正文整体阅读体验是"压抑求生/潜伏惊悚"，而非"修炼成长/资源争夺/反制上位"，请明确标记为"玄幻笔调不足"。\n\n"""
            protagonist_expected = self._normalize_entity_name((self._load_state() or {}).get("protagonist_state", {}).get("name", ""))
            protagonist_expected = re.sub(r"^\*+|\*+$", "", protagonist_expected).strip()
            if protagonist_expected:
                user_content += f"""【主角名一致性检查】
当前项目主角名应为：{protagonist_expected}。若正文主角核心称呼长期不一致，请标记为"主角命名漂移"。\n\n"""
        
        if previous_ending_for_review:
            user_content += f"【上一章结尾（用于检查角色状态连续性）】\n{previous_ending_for_review}\n\n"
        
        # 添加设定参考（用于检查设定一致性）
        # 添加设定参考（用于检查设定一致性）
        if character_roster:
            # 分离活跃和已下线角色
            active_roster = character_roster
            offline_roster = ""
            if "## 已下线" in character_roster:
                parts = character_roster.split("## 已下线")
                active_roster = parts[0]
                offline_roster = parts[1]
            
            active_roster_for_review = self._truncate_text(
                active_roster,
                review_budget.get("active_roster", 2200),
                keep_tail=True,
            )
            user_content += f"【活跃角色表（用于检查角色名是否正确）】\n{active_roster_for_review}\n\n"
            
            # 提取已下线角色名单并作为禁忌
            dead_list = []
            if offline_roster:
                # 简单正则提取名字：- **名字**
                dead_list = re.findall(r"- \*\*(.+?)\*\*", offline_roster)
            
            if dead_list:
                dead_str = "、".join(dead_list)
                user_content += f"""【⚠️ 严重警告：已死亡/下线角色黑名单】
以下角色已经死亡或彻底下线，绝对禁止在正文中以活人身份出现、说话或行动（除非是回忆或被提及）：
{dead_str}

如果正文中出现了上述角色（且不是回忆），必须标记为【严重剧情BUG】！
\n"""
        
        if gold_finger_for_review:
            user_content += f"【本书金手指/系统设计（用于检查术语是否正确）】\n{gold_finger_for_review}\n\n"
        
        if worldview_for_review:
            user_content += f"【世界观设定（用于检查设定是否一致）】\n{worldview_for_review}\n\n"
        
        if entity_summary_for_review:
            user_content += f"【设定库参考（用于检查名称一致性）】\n{entity_summary_for_review}\n\n"
        
        # 添加实时状态（用于检查数值一致性）
        if realtime_status_for_review:
            user_content += f"【实时状态数值（用于检查数字是否与记录一致）】\n{realtime_status_for_review}\n\n"
        
        # 添加角色档案摘要（用于检查角色身份/门派是否正确）
        if character_details_for_review:
            user_content += f"""【⚠️ 角色身份档案（最高优先级 - 用于检查门派/势力是否正确）】
以下是角色的真实身份和所属势力，如果正文中角色自称的门派与档案不符，必须标记为【严重设定BUG】！
例如：某角色档案显示是"落云宗长老"，但正文中他说"我是天火门长老" → ❌ 严重错误！
{character_details_for_review}

"""
            
        user_content += f"【正文内容（已压缩抽样）】\n{content_for_review}\n\n"
        
        # 直接返回纯文本审查结果，不再强制JSON
        user_content += "\n请直接用自然语言写审查意见，300字以内，不需要JSON格式。\n"

        # 4. 调用 AI
        try:
             result_chunks = []
             async for chunk in self.ai_service.chat_stream(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                temperature=0.3,
                max_tokens=1500
             ):
                 if chunk:
                     result_chunks.append(chunk)
             result_str = "".join(result_chunks).strip()
             
             # 清理可能的Markdown代码块标记
             if result_str.startswith("```"):
                 result_str = result_str.split("\n", 1)[-1]
             if result_str.endswith("```"):
                 result_str = result_str.rsplit("```", 1)[0].strip()
             
             self._debug(f"[REVIEW DEBUG] 审查结果 ({len(result_str)}字): {result_str[:200]}")
             
             return {
                 "success": True,
                 "raw_review": result_str
             }

        except Exception as e:
             return {"success": False, "error": str(e)}

    # ==================== Auto State Extraction ====================
    async def execute_state_extraction(self, chapter_id: int, content: str) -> Dict[str, Any]:
        """AI 自动设定收容与状态追踪 (方案B核心)"""
        if not getattr(self, "ai_service", None):
            return {"success": False, "error": "AI Service not initialized"}
            
        # 1. 读取 prompt 模板
        tmpl = self._load_project_prompt("extract_state")
        
        # 2. 准备上下文 (核心约束/存量设定)
        state_data = self._load_state() or {}
        core_constraints = state_data.get("core_settings", "无")
        style_bundle, normalized_genre, normalized_substyle = self._build_project_stage_style_bundle(
            stage="状态抽取",
            genre_style_chars=500,
            genre_examples_chars=0,
            substyle_examples_chars=0,
        )
        substyle_display = normalized_substyle or "默认子风格"
        style_section = (
            f"\n\n【当前阶段题材协议】\n{style_bundle}\n\n【题材】\n{normalized_genre} / {substyle_display}\n"
            if style_bundle
            else ""
        )
        
        system_prompt = (
            tmpl.replace("{core_constraints}", str(core_constraints)).replace("{content}", content) + style_section
        )
        
        # 3. 请求 AI (要求 JSON 格式)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请对第{chapter_id}章提取设定和状态，请直接输出合法的JSON格式，禁止输出Markdown代码块，不用回答任何废话。"}
        ]
        
        self._debug(f"[EXTRACT DEBUG] 开始提取第 {chapter_id} 章设定...")
        try:
            result_chunks = []
            async for chunk in self.ai_service.chat_stream(messages, temperature=0.1):
                if chunk is not None:
                    result_chunks.append(chunk)
            
            result_str = "".join(result_chunks).strip()
            
            # 尝试解析 JSON
            if "```json" in result_str:
                json_str = result_str.split("```json")[1].split("```")[0].strip()
            elif "```" in result_str:
                json_str = result_str.split("```")[1].split("```")[0].strip()
            else:
                json_str = result_str
                
            data = json.loads(json_str)
            
            # 4. 落盘: 新建立体设定文件（复用统一去重+命名归一）
            new_entities = data.get("new_entities", [])
            category_map = {
                "角色": "角色库",
                "角色库": "角色库",
                "人物": "角色库",
                "宝物": "宝物库",
                "法宝": "宝物库",
                "功法": "功法库",
                "武技": "功法库",
                "势力": "势力库",
                "组织": "势力库",
                "地点": "地点库",
                "场景": "地点库",
            }

            for entity in new_entities:
                raw_category = self._safe_text(entity.get("category", "其他")).strip()
                category = category_map.get(raw_category, raw_category)
                if category not in {"角色库", "宝物库", "功法库", "势力库", "地点库"}:
                    continue
                name = self._normalize_entity_name(entity.get("name", ""))
                desc = self._safe_text(entity.get("description", "")).strip()
                
                if name and desc:
                    if category == "角色库":
                        role_dir = self.project_root / "设定集" / "角色库" / "次要角色"
                        role_dir.mkdir(parents=True, exist_ok=True)
                        existing_file = self._find_character_file_by_name(name)
                        file_path = existing_file or (role_dir / f"{name}.md")
                    else:
                        cat_dir = self.project_root / "设定集" / category
                        cat_dir.mkdir(parents=True, exist_ok=True)
                        existing_file = self._find_entity_file_in_dir(cat_dir, name)
                        file_path = existing_file or (cat_dir / f"{name}.md")
                    canonical_name = file_path.stem
                    header = f"# {name}\n\n- **分类**: {category}\n- **首次出现**: 第{chapter_id}章\n\n## 设定描述\n"
                    
                    with self._locked_file(file_path):
                        if file_path.exists():
                            # 追加模式
                            with file_path.open("a", encoding="utf-8") as f:
                                f.write(f"\n### 第{chapter_id}章更新\n{desc}\n")
                        else:
                            # 新建模式
                            with file_path.open("w", encoding="utf-8") as f:
                                f.write(header.replace(f"# {name}", f"# {canonical_name}") + desc + "\n")
            
            # 5. 落盘: 更新 state.json 中的 dynamic_state
            state_updates = data.get("state_updates", [])
            if state_updates:
                def apply_dynamic_state(s: Dict[str, Any]) -> None:
                    dynamic = s.setdefault("dynamic_state", {})
                    for update in state_updates:
                        target = self._normalize_entity_name(update.get("target", ""))
                        key = self._safe_text(update.get("key", "")).strip()
                        new_val = update.get("new_value", "")
                        if not target or not key:
                            continue
                        row = dynamic.setdefault(target, {})
                        row[key] = new_val
                        row["_last_updated_chapter"] = chapter_id

                self._update_state(apply_dynamic_state)
                
            self._debug(f"[EXTRACT DEBUG] 提取成功: 发现 {len(new_entities)} 个新实体, {len(state_updates)} 项状态更新")
            return {"success": True, "entities": new_entities, "updates": state_updates}
            
        except Exception as e:
            self._debug(f"[EXTRACT DEBUG] ❌ 提取失败: {e}")
            return {"success": False, "error": str(e)}

    # ==================== Context Agent ====================

    async def _execute_context_agent(self, chapter: int) -> Dict[str, Any]:
        """执行 context-agent 工作流"""
        context_pack = {"core": {}, "scene": {}, "global": {}, "rag": {}, "alerts": {}}

        try:
            # Step 1: 读取大纲
            chapter_outline = self._find_chapter_outline(chapter)
            context_pack["core"]["chapter_outline"] = chapter_outline
            
            # Step 1.1: 读取完整大纲文件（用于下一章预览）
            full_outline = self._read_full_outline(chapter)
            context_pack["core"]["outline"] = full_outline

            # Step 2: 获取主角状态
            state = self._load_state()
            protagonist_info = {}
            if state:
                protagonist_info = state.get("protagonist_state", {})
            
            # 如果主角名为空，从主角卡文件中解析
            if not protagonist_info.get("name"):
                char_card = self._read_file(self.project_root / "设定集" / "主角卡.md")
                if char_card:
                    parsed_name = self._extract_protagonist_name_from_card(char_card)
                    if parsed_name:
                        protagonist_info["name"] = parsed_name
                    # 解析性格或其他信息
                    personality_match = re.search(r"\*?\*?性格\*?\*?[：:]\s*(.+?)(?:\n|$)", char_card)
                    if personality_match:
                        protagonist_info["personality"] = personality_match.group(1).strip()
            
            context_pack["core"]["protagonist_snapshot"] = protagonist_info
            current_genre = self._get_project_genre()
            current_substyle = self._get_project_substyle()
            context_pack["global"]["genre"] = current_genre
            context_pack["global"]["substyle"] = current_substyle
            genre_style_guide = self._load_genre_style_guide(current_genre, max_chars=3600)
            if genre_style_guide:
                context_pack["global"]["genre_style_guide"] = genre_style_guide

            # Step 2.5: 读取活跃角色表
            character_roster = ""
            character_file = self.project_root / "设定集" / "角色库" / "活跃角色.md"
            if character_file.exists():
                character_roster = self._read_file(character_file)
            context_pack["core"]["character_roster"] = character_roster

            # Step 2.6: 读取金手指设计（用于动态生成设定约束）
            gold_finger = ""
            gold_finger_file = self.project_root / "设定集" / "金手指设计.md"
            if gold_finger_file.exists():
                gold_finger = self._read_file(gold_finger_file)
            context_pack["core"]["gold_finger"] = gold_finger

            # Step 2.7: 读取实时状态（关键数值追踪）
            realtime_status = ""
            status_file = self.project_root / "设定集" / "实时状态.md"
            if status_file.exists():
                realtime_status = self._read_file(status_file)
            context_pack["core"]["realtime_status"] = realtime_status

            # Step 3: 获取最近章节摘要
            context_pack["core"]["recent_summaries"] = self._get_recent_summaries(chapter, 3)


            # Step 1.5: 获取上一章结尾用于衔接
            prev_chapter_num = chapter - 1
            self._debug(f"[DEBUG] 上一章编号: {prev_chapter_num}")  # Debug: 打印上一章编号
            if prev_chapter_num > 0:
                # 尝试找到上一章文件
                chapters_dir = self.project_root / "正文"
                prev_files = list(chapters_dir.glob(f"第{prev_chapter_num}章*.md"))
                self._debug(f"[DEBUG] 找到的上一章文件: {[f.name for f in prev_files]}")  # Debug: 打印找到的文件
                if prev_files:
                    prev_content = self._read_file(prev_files[0])
                    self._debug(f"[DEBUG] 读取上一章文件: {prev_files[0].name}, 内容长度: {len(prev_content)} 字符")  # Debug
                    # 去掉可能的摘要部分
                    if "## 本章摘要" in prev_content:
                        prev_content = prev_content.split("## 本章摘要")[0]
                    # 仅按写作预算加载上一章结尾，避免后续二次截断造成冗余读取
                    prev_ending_budget = self._get_context_budgets("write").get("previous_ending", 600)
                    context_pack["core"]["previous_chapter_ending"] = prev_content.strip()[-prev_ending_budget:]
                
                # 读取上一章的连续性摘要
                continuity_file = chapters_dir / ".continuity" / f"第{prev_chapter_num}章_状态.md"
                if continuity_file.exists():
                    context_pack["core"]["continuity_summary"] = self._read_file(continuity_file)

            # Step 4: 写作阶段停用 RAG 回灌，避免历史章节措辞污染当前文风。
            context_pack["rag"]["related_scenes"] = []

            # Step 5: 搜索设定集
            worldview = self._read_file(self.project_root / "设定集" / "世界观.md")
            power_system = self._read_file(self.project_root / "设定集" / "力量体系.md")
            context_pack["global"]["worldview_skeleton"] = worldview if worldview else ""
            context_pack["global"]["power_system_skeleton"] = power_system if power_system else ""
            
            # Step 6: 加载设定库摘要（宝物/功法/势力/地点）
            entity_summary = self._load_entity_libraries_summary()
            if entity_summary:
                context_pack["global"]["entity_libraries"] = entity_summary

        except Exception as e:
            context_pack["alerts"]["error"] = str(e)

        return context_pack

    # ==================== 辅助方法 ====================

    def _load_reference(self, skill: str, ref_path: str) -> str:
        """加载 Skill 参考文档"""
        ref_file = SKILLS_DIR / skill / "references" / ref_path
        return self._read_file(ref_file)

    def _load_project_prompt(self, slot_id: str, genre: str = "", substyle: str = "") -> str:
        effective_genre = genre or self._get_project_genre()
        effective_substyle = substyle or self._get_project_substyle()
        return self._safe_text(
            get_project_prompt_content(
                self.project_root,
                slot_id,
                effective_genre,
                effective_substyle,
            )
        ).strip()

    def _load_template(self, template_name: str) -> str:
        """加载模板文件"""
        template_file = TEMPLATES_DIR / template_name
        return self._read_file(template_file)

    def _resolve_claude_dir(self, start_path: Optional[Path] = None) -> Path:
        """智能查找 .claude 目录，兼容项目根目录与插件目录。"""
        curr = start_path or self.project_root
        for _ in range(5):
            if (curr / ".claude").exists():
                return curr / ".claude"
            if curr.parent == curr:
                break
            curr = curr.parent
        return PROJECT_ROOT / ".claude"

    def _get_writer_prompts_dir(self) -> Path:
        claude_dir = self._resolve_claude_dir(self.project_root)
        prompt_dir = claude_dir / "skills" / "webnovel-write" / "prompts"
        if prompt_dir.exists():
            return prompt_dir
        return SKILLS_DIR / "webnovel-write" / "prompts"

    def _format_prompt_text(self, template: str, **kwargs: Any) -> str:
        if not template:
            return ""
        safe_kwargs = {k: self._safe_text(v) for k, v in kwargs.items()}
        try:
            return template.format(**safe_kwargs)
        except (KeyError, ValueError):
            text = template
            for k, v in safe_kwargs.items():
                text = text.replace(f"{{{k}}}", v)
            return text

    def _adapt_independent_prompt_for_stage(self, prompt: str, stage: str) -> str:
        text = self._safe_text(prompt).strip()
        stage_name = self._safe_text(stage).strip() or "当前创作阶段"
        if not text or any(k in stage_name for k in ["正文", "章节"]):
            return text
        text = text.replace("独立写作 prompt", "独立创作 prompt")
        text = text.replace("正文专属协议", f"当前创作阶段（{stage_name}）专属协议")
        return text

    def _load_genre_writer_prompt(self, genre: str, stage: str = "章节写作") -> str:
        template = self._load_project_prompt("genre_writer", genre=genre)
        if not template:
            return ""
        return self._adapt_independent_prompt_for_stage(self._format_prompt_text(
            template,
            genre=canonical_genre_id(genre),
            stage=stage,
        ), stage)

    def _load_substyle_writer_prompt(self, genre: str, substyle: str = "", stage: str = "章节写作") -> str:
        effective_substyle = self._get_effective_substyle(genre, substyle)
        if not effective_substyle:
            return ""
        template = self._load_project_prompt(
            "substyle_writer",
            genre=genre,
            substyle=effective_substyle,
        )
        if not template:
            return ""
        return self._adapt_independent_prompt_for_stage(self._format_prompt_text(
            template,
            genre=canonical_genre_id(genre),
            substyle=effective_substyle,
            stage=stage,
        ), stage)

    def _build_independent_stage_prompt_block(self, genre: str, substyle: str = "", stage: str = "章节写作") -> str:
        stage_name = self._safe_text(stage).strip() or "当前创作阶段"
        note = (
            f'以下约束源自题材独立 prompt。若其中出现"正文/章末"等章节级表述，'
            f"请等价映射为当前阶段（{stage_name}）的风格与结构约束。"
        )
        blocks: List[str] = []

        genre_prompt = self._load_genre_writer_prompt(genre, stage=stage_name)
        if genre_prompt:
            blocks.append(f"【题材独立创作协议】\n{note}\n{genre_prompt}")

        substyle_prompt = self._load_substyle_writer_prompt(genre, substyle, stage=stage_name)
        if substyle_prompt:
            blocks.append(f"【子风格独立创作协议】\n{note}\n{substyle_prompt}")

        return "\n\n".join(blocks)

    def _build_stage_style_bundle(
        self,
        genre: str,
        substyle: str = "",
        *,
        stage: str,
        genre_style_chars: int = 0,
        genre_examples_chars: int = 0,
        substyle_examples_chars: int = 0,
    ) -> tuple[str, str, str]:
        normalized_genre = canonical_genre_id(genre) or self._safe_text(genre).strip() or "玄幻"
        normalized_substyle = canonical_substyle_id(normalized_genre, substyle)

        parts: List[str] = []
        independent_prompt = self._build_independent_stage_prompt_block(
            normalized_genre,
            normalized_substyle,
            stage=stage,
        )
        if independent_prompt:
            parts.append(independent_prompt)

        genre_guard = self._build_genre_guard_instruction(normalized_genre, stage=stage)
        if genre_guard:
            parts.append(f"【题材锁定】\n{genre_guard}")

        positive_style = self._build_genre_positive_style_instruction(normalized_genre, stage=stage)
        if positive_style:
            parts.append(f"【题材笔调校准】\n{positive_style}")

        substyle_instruction = self._build_substyle_instruction(
            normalized_genre,
            normalized_substyle,
            stage=stage,
        )
        if substyle_instruction:
            parts.append(f"【子风格锁定】\n{substyle_instruction}")

        if genre_style_chars > 0:
            style_guide = self._load_genre_style_guide(normalized_genre, max_chars=genre_style_chars)
            if style_guide:
                parts.append(f"【题材风格参考】\n{style_guide}")

        if substyle_examples_chars > 0:
            substyle_examples = self._load_substyle_examples(
                normalized_genre,
                normalized_substyle,
                max_chars=substyle_examples_chars,
            )
            if substyle_examples:
                parts.append(
                    "【子风格示例（只学节奏与侧重点，不照抄）】\n"
                    f"{substyle_examples}"
                )

        if genre_examples_chars > 0:
            genre_examples = self._load_genre_style_examples(
                normalized_genre,
                normalized_substyle,
                max_chars=genre_examples_chars,
            )
            if genre_examples:
                parts.append(
                    "【题材表达示例（只学语气与句法，不照抄）】\n"
                    f"{genre_examples}"
                )

        return "\n\n".join(parts), normalized_genre, normalized_substyle

    def _build_project_stage_style_bundle(
        self,
        *,
        stage: str,
        genre_style_chars: int = 0,
        genre_examples_chars: int = 0,
        substyle_examples_chars: int = 0,
    ) -> tuple[str, str, str]:
        return self._build_stage_style_bundle(
            self._get_project_genre(),
            self._get_project_substyle(),
            stage=stage,
            genre_style_chars=genre_style_chars,
            genre_examples_chars=genre_examples_chars,
            substyle_examples_chars=substyle_examples_chars,
        )

    def _build_chapter_hard_constraints_prompt(
        self,
        *,
        core_constraints: str,
        worldview: str,
        protagonist_name: str,
        protagonist_desc: str,
        word_count: int,
    ) -> str:
        """章节正文的通用硬约束。这里只保留不涉及文风的底线，不参与题材表达。"""
        safe_constraints = self._safe_text(core_constraints).strip() or "保持剧情清晰、节奏稳定，严格执行大纲。"
        safe_worldview = self._safe_text(worldview).strip() or "（无）"
        safe_name = self._safe_text(protagonist_name).strip() or "主角"
        safe_desc = self._safe_text(protagonist_desc).strip()
        safe_desc = safe_desc or "（以设定和大纲为准）"

        # 主路径：从 slot 系统加载模板
        template = self._load_project_prompt("chapter_hard_constraints")
        if template:
            return self._format_prompt_text(
                template,
                core_constraints=safe_constraints,
                worldview=safe_worldview,
                protagonist_name=safe_name,
                protagonist_desc=safe_desc,
                word_count=str(word_count),
                word_count_max=str(word_count + 600),
            )

        # Fallback：原始硬编码
        return f"""你是一位专业的网文作者。

【章节硬约束（非题材模板）】
1. 必须严格执行本章大纲中的剧情点、爽点、损耗和收益，禁止脱离大纲自由发挥。
2. 地名、人名、势力名、物品名、系统词条、境界名必须与大纲和设定严格一致，禁止擅自改名或替换。
3. 只写本章大纲允许的内容，下一章的核心动作、高潮、结果必须留给下一章。
4. 章节必须写实时发生的过程，禁止使用"几日后""三天后""半月后"等时间跳跃词直接略过过程。
5. 输出必须是小说正文，标题使用 `# 第X章 标题` 格式，禁止输出解释、分析、代码块或后台标签。
6. 正文字数控制在 {word_count}-{word_count + 600} 字，严禁超过 4000 字；剧情点多时优先压缩重复解释，不得注水。

【核心约束】
{safe_constraints}

【世界观】
{safe_worldview}

【主角信息】
{safe_name} - {safe_desc}
"""

    def _get_project_genre(self) -> str:
        state = self._load_state() or {}
        if not isinstance(state, dict):
            return "玄幻"

        project_info = state.get("project_info", {})
        genre = ""
        if isinstance(project_info, dict):
            genre = self._safe_text(project_info.get("genre", "")).strip()
        if not genre:
            genre = self._safe_text(state.get("genre", "")).strip()
        return canonical_genre_id(genre or "玄幻") or "玄幻"

    def _get_project_substyle(self) -> str:
        state = self._load_state() or {}
        if not isinstance(state, dict):
            return ""

        project_info = state.get("project_info", {})
        genre = self._get_project_genre()
        substyle = ""
        if isinstance(project_info, dict):
            substyle = self._safe_text(project_info.get("substyle", "")).strip()
        if not substyle:
            substyle = self._safe_text(state.get("substyle", "")).strip()
        return canonical_substyle_id(genre, substyle)

    def _clear_outline_invalidation_state(self) -> None:
        def clear_flags(state: Dict[str, Any]) -> None:
            project_info = state.setdefault("project_info", {})
            project_info["outline_invalidated"] = False
            project_info["outline_invalidation_reason"] = ""
            project_info.pop("outline_invalidated_at", None)

        self._update_state(clear_flags)

    def _get_outline_invalidation_reason(self) -> str:
        state = self._load_state() or {}
        if not isinstance(state, dict):
            return ""
        project_info = state.get("project_info", {})
        if isinstance(project_info, dict) and project_info.get("outline_invalidated"):
            return self._safe_text(project_info.get("outline_invalidation_reason", "")).strip()
        return ""

    def _load_genre_template(self, genre: str) -> str:
        """加载题材模板。优先模板文件，不存在时回退到 genres 细分知识库。"""
        raw_genre = self._safe_text(genre).strip()

        template_candidates = [raw_genre] if raw_genre else []
        all_aliases = get_template_aliases()
        template_candidates.extend(all_aliases.get(raw_genre, []))
        for candidate in template_candidates:
            if not candidate:
                continue
            content = self._read_file(TEMPLATES_DIR / "genres" / f"{candidate}.md")
            if content:
                return content

        # 回退到 .claude/genres 子目录（多文件知识库）
        genre_key = self._normalize_genre_key(raw_genre)
        genre_dir = self._resolve_genre_knowledge_dir(raw_genre)
        if not genre_dir:
            return ""

        ordered_files = get_template_preferred_files(genre_key)
        selected_files: List[Path] = []
        for name in ordered_files:
            file = genre_dir / name
            if file.exists():
                selected_files.append(file)
        if not selected_files:
            selected_files = sorted(genre_dir.glob("*.md"))[:3]

        sections: List[str] = []
        for f in selected_files[:4]:
            text = self._read_file(f)
            if not text:
                continue
            sections.append(f"## {f.stem}\n{text}")
        return "\n\n".join(sections)

    def _load_genre_style_guide(self, genre: str, max_chars: int = 2600) -> str:
        guide = self._load_genre_template(genre)
        return self._truncate_text(guide, max_chars, keep_tail=False) if guide else ""

    def _load_character_details_for_review(self) -> str:
        """加载角色档案摘要（名字、身份、门派）用于审核时检查角色设定一致性"""
        details = []
        char_lib = self.project_root / "设定集" / "角色库"
        
        if not char_lib.exists():
            return ""
        
        # 遍历角色库子目录
        subdirs = ["主要角色", "反派角色", "次要角色"]
        for subdir in subdirs:
            subdir_path = char_lib / subdir
            if not subdir_path.exists():
                continue
            
            # 只读取前20个角色避免token过长
            files = sorted(subdir_path.glob("*.md"))[:20]
            for f in files:
                try:
                    content = f.read_text(encoding="utf-8")[:500]  # 只读开头500字
                    name = f.stem
                    
                    # 提取身份信息
                    identity = ""
                    identity_match = re.search(r"\*\*身份\*\*[：:]\s*(.+?)(?:\n|$)", content)
                    if identity_match:
                        identity = identity_match.group(1).strip()
                    
                    # 提取门派/势力信息（可能在身份里，也可能单独一行）
                    faction = ""
                    faction_match = re.search(r"\*\*(?:门派|势力|所属)\*\*[：:]\s*(.+?)(?:\n|$)", content)
                    if faction_match:
                        faction = faction_match.group(1).strip()
                    
                    # 组装摘要
                    info = f"- **{name}**"
                    if identity:
                        info += f"：{identity}"
                    if faction and faction not in identity:
                        info += f"（{faction}）"
                    
                    details.append(info)
                except Exception:
                    continue
        
        return "\n".join(details) if details else ""

    def _load_entity_libraries_summary(self) -> str:
        """加载设定库摘要（宝物/功法/势力/地点）用于 AI 写作参考。"""
        summary_parts = []
        settings_dir = self.project_root / "设定集"

        desc_patterns = [
            r"##\s*效果[/／]?用途?\s*\n+(.+?)(?:\n##|\Z)",
            r"##\s*效果[/／]?特点?\s*\n+(.+?)(?:\n##|\Z)",
            r"##\s*设定描述\s*\n+(.+?)(?:\n##|\Z)",
            r"##\s*特点\s*\n+(.+?)(?:\n##|\Z)",
            r"##\s*重要性\s*\n+(.+?)(?:\n##|\Z)",
            r"##\s*与主角关系\s*\n+(.+?)(?:\n##|\Z)",
            r"##\s*来源[/／]?出处\s*\n+(.+?)(?:\n##|\Z)",
        ]

        def to_one_line(text: str, max_chars: int = 28) -> str:
            raw = self._safe_text(text).strip()
            if not raw:
                return ""
            raw = re.sub(r"`+", "", raw)
            raw = re.sub(r"\*{1,3}", "", raw)
            raw = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", raw)
            raw = re.sub(r"\s+", " ", raw)
            return self._truncate_text(raw, max_chars, keep_tail=False)

        # 读取各库的文件列表（名称 + 关键描述）
        libraries = [
            ("宝物库", "已有宝物"),
            ("功法库", "已有功法"),
            ("势力库", "已有势力"),
            ("地点库", "已有地点")
        ]
        
        for lib_name, label in libraries:
            lib_dir = settings_dir / lib_name
            if lib_dir.exists():
                files = list(lib_dir.glob("*.md"))[:10]
                if files:
                    entries = []
                    for f in files:
                        name = f.stem
                        content = f.read_text(encoding="utf-8")[:900]
                        first_appear = ""
                        if "首次出现" in content or "首次出场" in content:
                            match = re.search(r"首次出[现场].*?第(\d+)[章卷]", content)
                            if match:
                                first_appear = f"(第{match.group(1)}章)"

                        desc = ""
                        for pattern in desc_patterns:
                            m = re.search(pattern, content, re.DOTALL)
                            if m:
                                desc = to_one_line(m.group(1), 30)
                                if desc:
                                    break
                        if not desc:
                            bullets = re.findall(r"^-?\s*[-*]\s*(.+)$", content, re.MULTILINE)
                            if bullets:
                                desc = to_one_line(bullets[0], 30)

                        entry = f"{name}{first_appear}"
                        if desc:
                            entry += f"：{desc}"
                        entries.append(entry)
                    summary_parts.append(f"【{label}】{'；'.join(entries)}")
        
        return "\n".join(summary_parts) if summary_parts else ""

    def _load_state(self) -> Optional[Dict]:
        """加载 state.json"""
        state_file = self.webnovel_dir / "state.json"
        if state_file.exists():
            with self._locked_file(state_file):
                try:
                    return json.loads(state_file.read_text(encoding="utf-8"))
                except Exception:
                    return None
        return None

    def _read_file(self, path: Path) -> str:
        """读取文件内容"""
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def get_chapter_outline(self, chapter: int) -> str:
        """获取章节大纲（公开接口）"""
        return self._find_chapter_outline(chapter)

    def _read_full_outline(self, chapter: int) -> str:
        """读取包含指定章节的完整大纲文件"""
        outline_dir = self.project_root / "大纲"
        # self._debug(f"[DEBUG] _read_full_outline: project_root = {self.project_root}")
        
        if not outline_dir.exists():
            self._debug(f"[DEBUG] _read_full_outline: 大纲目录不存在!")
            return ""
        
        # 搜索所有大纲文件，找到包含该章节的那个
        files = sorted(outline_dir.glob("*.md"))
        
        for f in files:
            content = self._read_file(f)
            if not content:
                continue
            # 检查这个文件是否包含当前章节的信息 (支持空格)
            # 使用简单的正则检查：第\s*chapter\s*章
            if re.search(rf"第\s*{chapter}\s*章", content) or \
               re.search(rf"\*\*\s*第\s*{chapter}\s*章", content) or \
               re.search(rf"#+\s*(\*\*|__)\s*第\s*{chapter}\s*章", content) or \
               re.search(rf"\b{chapter}\s*\.\s*《", content):
                self._debug(f"[DEBUG] _read_full_outline: 在 {f.name} 中找到第{chapter}章")
                return content
        
        self._debug(f"[DEBUG] _read_full_outline: 未找到包含第{chapter}章的大纲文件")
        return ""

    def _parse_outline(self, full_outline: str, chapter: int) -> str:
        """从完整大纲中解析出指定章节的内容"""
        if not full_outline:
            return ""
        
        lines = full_outline.split("\n")
        
        # 定义匹配章节标题的正则模式 - 必须支持空格！
        patterns = [
            # 0. 混合格式 (## **第 51 章...) - 用户反馈的 case
            rf"^#+\s*(\*\*|__)\s*第\s*{chapter}\s*章",
            # 1. Markdown 标题格式 (### 第 259 章)
            rf"^#+\s*第\s*{chapter}\s*章",
            # 2. 加粗格式 (**第 259 章**)
            rf"^(\*\*|__)\s*第\s*{chapter}\s*章",
            # 3. 列表加粗 (- **第 259 章**)
            rf"^[-*]\s*(\*\*|__)\s*第\s*{chapter}\s*章",
            # 4. 纯文本格式 (第 259 章：...)
            rf"^第\s*{chapter}\s*章",
            # 5. 数字标题 (1. 《...》)
            rf"^(\*\*|#+\s*)?{chapter}\s*\.\s*《",
        ]
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            match = False
            for p in patterns:
                if re.match(p, line_stripped):
                    match = True
                    break
            
            if match:
                # 找到章节标题，开始提取内容块
                outline_block = [line]
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    # 检测下一章节的开始 - 极度宽松模式
                    
                    # 1. 标题类 (# 第 X 章)
                    if re.match(r"^#+\s*第\s*\d+\s*章", next_line):
                        break
                    # 2. 加粗类 (**第 X 章)
                    if re.match(r"^(\*\*|__)\s*第\s*\d+\s*章", next_line):
                        break
                    # 3. 列表加粗 (- **第 X 章)
                    if re.match(r"^[-*]\s*(\*\*|__)\s*第\s*\d+\s*章", next_line):
                        break
                    # 4. 纯文本类 (第 X 章)
                    if re.match(r"^第\s*\d+\s*章", next_line):
                        break
                    # 5. 数字类 (123. 《)
                    if re.match(r"^(\*\*|#+\s*)?\d+\s*\.\s*《", next_line):
                        break
                    # 6. 宽容匹配：包含 "第X章" 且看起来像标题
                    # 避免匹配正文中的 "第X章" 引用，所以要求行首
                    if re.match(r"^#+\s*(\*\*|__)?\s*第\s*\d+\s*章", next_line):
                         break

                    outline_block.append(lines[j])
                
                return "\n".join(outline_block).strip()
        
        return ""

    def _find_chapter_outline(self, chapter: int) -> str:
        """查找章节大纲 - 支持多种格式并提取完整内容块"""
        outline_dir = self.project_root / "大纲"
        if not outline_dir.exists():
            return ""
        
        files_to_search = sorted(list(outline_dir.glob("*.md")))
        
        # 定义匹配章节标题的正则模式 - 按优先级排序，要包容多种格式
        patterns = [
            # 格式0: "## **第X章**" (混合格式) - 用户反馈的CASE
            rf"^#+\s*(\*\*|__)\s*第\s*{chapter}\s*章",
            # 格式1: "**第X章：标题**" 或 "**第X章:标题**"（无前缀），允许空格
            rf"^\*\*\s*第\s*{chapter}\s*章[：:].+\*\*",
            # 格式2: "*   **第X章：标题**"（带列表前缀），允许空格
            rf"^[-*]\s*\*\*\s*第\s*{chapter}\s*章[：:\s].*",
            # 格式3: "### 第X章" 或 "第X章..."（标题格式），允许空格
            rf"^#+\s*第\s*{chapter}\s*章",
            rf"^第\s*{chapter}\s*章[：:\s]",
            # 格式4: 带书名号的格式 "### 1.《标题》" 或 "1.《标题》"
            rf"^#+\s*{chapter}\s*\.\s*《",
            rf"^{chapter}\s*\.\s*《",
            # 格式5: 纯数字格式 "1. 标题" 或 "**1. 标题**"（章节号匹配）
            rf"^\*\*\s*{chapter}\s*\.\s+",
        ]
        
        for f in files_to_search:
            content = self._read_file(f)
            if not content:
                continue
            
            lines = content.split("\n")
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                match = False
                for p in patterns:
                    if re.match(p, line_stripped):
                        match = True
                        break
                
                if match:
                    # 找到章节标题，开始提取内容块
                    outline_block = [line]
                    # 向下读取直到遇到下一个标题（### 或 数字开头）或文件结束
                    for j in range(i + 1, len(lines)):
                        next_line = lines[j].strip()
                        #如果遇到下一个章节的标题特征，则停止
                        is_new_chapter = False
                        
                        # 检测下一章节的开始 - 极度宽松模式
                        
                        # 1. 标题类 (# 第 X 章)
                        if re.match(r"^#+\s*第\s*\d+\s*章", next_line):
                            is_new_chapter = True
                        
                        # 2. 加粗类 (**第 X 章)
                        elif re.match(r"^(\*\*|__)\s*第\s*\d+\s*章", next_line):
                            is_new_chapter = True
                        
                        # 3. 列表格式 (- **第X章**)
                        elif re.match(r"^[-*]\s*(\*\*|__)\s*第\s*\d+\s*章", next_line):
                             is_new_chapter = True
                             
                        # 4. 数字+书名号格式 (1. 《...》)
                        elif re.match(r"^(\*\*|#+\s*)?\d+\s*\.\s*《", next_line):
                             is_new_chapter = True
                        
                        # 5. 纯文本类 (第 X 章)
                        elif re.match(r"^第\s*\d+\s*章", next_line):
                            is_new_chapter = True

                        # 6. 宽容匹配：包含 "第X章" 且看起来像标题 (Mixed case ## **第X章)
                        elif re.match(r"^#+\s*(\*\*|__)?\s*第\s*\d+\s*章", next_line):
                             is_new_chapter = True

                        if is_new_chapter:
                            break

                        outline_block.append(lines[j])
                    
                    return "\n".join(outline_block).strip()
        
        return ""

    def _get_recent_summaries(self, chapter: int, count: int = 3) -> List[Dict]:
        """获取最近章节摘要"""
        summaries = []
        chapters_dir = self.project_root / "正文"
        for i in range(chapter - 1, max(0, chapter - count - 1), -1):
            for f in chapters_dir.glob(f"第{i}章*.md"):
                content = self._read_file(f)
                # 提取摘要部分
                if "## 本章摘要" in content:
                    summary = content.split("## 本章摘要")[1].strip()[:300]
                else:
                    summary = content[:200] + "..."
                summaries.append({"chapter": i, "summary": summary})
                break
        return summaries

    async def _generate_chapter_content_stream(
        self,
        chapter: int,
        context_pack: Dict,
        core_constraints: str,
        word_count: int
    ):
        """流式生成章节内容"""
        chapter_outline = context_pack.get("core", {}).get("chapter_outline", "")
        
        # ========== DEBUG: 打印大纲信息 ==========
        self._debug("\n" + "="*60)
        self._debug(f"[DEBUG] 正在生成第 {chapter} 章")
        self._debug("="*60)
        self._debug(f"[DEBUG] 本章大纲:\n{chapter_outline[:500] if chapter_outline else '(空)'}")
        self._debug("-"*60)
        
        # 尝试获取下一章大纲作为"刹车"参考
        full_outline = context_pack.get("core", {}).get("outline", "")
        next_chapter_outline = ""
        if full_outline:
            next_chapter_outline = self._parse_outline(full_outline, chapter + 1)
        
        self._debug(f"[DEBUG] 完整大纲长度: {len(full_outline)} 字符")
        self._debug(f"[DEBUG] 下一章 (第{chapter+1}章) 大纲:\n{next_chapter_outline[:500] if next_chapter_outline else '(空)'}")
        self._debug("="*60 + "\n")
        
        write_budget = self._get_context_budgets("write")
        protagonist = context_pack.get("core", {}).get("protagonist_snapshot", {})
        recent_summaries = context_pack.get("core", {}).get("recent_summaries", [])
        worldview = context_pack.get("global", {}).get("worldview_skeleton", "")
        power_system = context_pack.get("global", {}).get("power_system_skeleton", "")
        previous_ending = context_pack.get("core", {}).get("previous_chapter_ending", "")
        character_roster = context_pack.get("core", {}).get("character_roster", "")
        entity_libraries = context_pack.get("global", {}).get("entity_libraries", "")
        genre = context_pack.get("global", {}).get("genre", "") or self._get_project_genre()
        substyle = context_pack.get("global", {}).get("substyle", "") or self._get_project_substyle()
        opening_chapter_instruction = self._build_opening_chapter_instruction(genre, substyle, chapter, chapter_outline)

        # 构建前情提要
        recent_context = ""
        if recent_summaries:
            summary_texts = [f"第{s.get('chapter', '?')}章：{s.get('summary', '')}" for s in recent_summaries[-3:]]
            recent_context = self._truncate_text(
                "【近期章节摘要】\n" + "\n".join(summary_texts),
                write_budget.get("recent_context", 1200),
                keep_tail=True,
            )

        chapter_outline_for_prompt = self._truncate_text(
            chapter_outline,
            write_budget.get("chapter_outline", 2400),
            keep_tail=False,
        )
        next_chapter_outline_for_prompt = self._truncate_text(
            next_chapter_outline,
            write_budget.get("next_chapter_outline", 1600),
            keep_tail=False,
        )
        worldview_for_prompt = self._truncate_text(
            worldview,
            write_budget.get("worldview", 1000),
            keep_tail=False,
        )
        power_system_for_prompt = self._truncate_text(
            power_system,
            write_budget.get("power_system", 1000),
            keep_tail=False,
        )
        previous_ending_for_prompt = self._truncate_text(
            previous_ending,
            write_budget.get("previous_ending", 600),
            keep_tail=True,
        )
        continuity_summary_for_prompt = self._truncate_text(
            context_pack.get("core", {}).get("continuity_summary", ""),
            write_budget.get("continuity_summary", 1800),
            keep_tail=True,
        )
        realtime_status_for_prompt = self._truncate_text(
            context_pack.get("core", {}).get("realtime_status", "（无状态追踪）"),
            write_budget.get("realtime_status", 1800),
            keep_tail=True,
        )
        entity_libraries_for_prompt = self._truncate_text(
            entity_libraries,
            write_budget.get("entity_libraries", 1800),
            keep_tail=False,
        )

        independent_stage_prompt = self._build_independent_stage_prompt_block(
            genre,
            substyle,
            stage="章节写作",
        )
        base_writer_template = self._load_project_prompt(
            "writer_base",
            genre=genre,
            substyle=substyle,
        )
        base_writer_prompt = self._format_prompt_text(
            base_writer_template,
            core_constraints=self._truncate_text(
                core_constraints,
                write_budget.get("core_constraints", 2800),
                keep_tail=True,
            ) if core_constraints else "保持剧情清晰、节奏稳定，严格执行大纲。",
            worldview=worldview_for_prompt if worldview_for_prompt else "（无）",
            protagonist_name=protagonist.get('name', '主角'),
            protagonist_desc=protagonist.get('personality', '') or "（以设定和大纲为准）",
        )
        hard_constraints_prompt = self._build_chapter_hard_constraints_prompt(
            core_constraints=self._truncate_text(
                core_constraints,
                write_budget.get("core_constraints", 2800),
                keep_tail=True,
            ) if core_constraints else "保持剧情清晰、节奏稳定，严格执行大纲。",
            worldview=worldview_for_prompt if worldview_for_prompt else "（无）",
            protagonist_name=protagonist.get('name', '主角'),
            protagonist_desc=protagonist.get('personality', ''),
            word_count=word_count,
        )

        prompt_layers: List[str] = []
        if base_writer_prompt:
            prompt_layers.append(base_writer_prompt)
        if independent_stage_prompt:
            prompt_layers.append(independent_stage_prompt)

        # 注入题材风格锚定（genre_guard + positive_style + substyle_instruction）
        genre_guard = self._build_genre_guard_instruction(genre, stage="章节写作")
        positive_style_instruction = self._build_genre_positive_style_instruction(genre, stage="章节写作")
        substyle_instruction = self._build_substyle_instruction(genre, substyle, stage="章节写作")
        style_anchor_parts = [p for p in [genre_guard, positive_style_instruction, substyle_instruction] if p]
        if style_anchor_parts:
            prompt_layers.append("\n".join(style_anchor_parts))

        prompt_layers.append(hard_constraints_prompt)
        system_prompt = "\n\n".join(part for part in prompt_layers if part)

        # 添加金手指/系统设计（动态约束，避免设定污染）
        gold_finger = context_pack.get("core", {}).get("gold_finger", "")
        if gold_finger:
            # 提取金手指的核心术语和规则
            gf_summary = self._truncate_text(gold_finger, write_budget.get("gold_finger", 1800), keep_tail=False)
            system_prompt += f"""

【本书金手指/系统设计（必须严格遵守！）】
{gf_summary}

**重要**：上述是本书的专属系统设计，必须使用上面定义的术语和规则。
禁止使用其他小说的术语（如其他书的"词条"、"面板"等），只能使用本书设定中出现的概念！"""

        if power_system_for_prompt:
            system_prompt += f"""

【力量体系（必须严格一致）】
{power_system_for_prompt}

**重要**：涉及境界、突破条件、战力上限时，必须使用上方体系，不得自创新等级名。"""

        if opening_chapter_instruction:
            system_prompt += f"""

【开篇章节约束（必须遵守）】
{opening_chapter_instruction}
"""

        # ========== 最高优先级：死亡角色黑名单（放入 System Prompt 最显眼位置）==========
        dead_warning_system = ""
        if character_roster and "## 已下线" in character_roster:
            parts = character_roster.split("## 已下线")
            offline_roster = parts[1]
            dead_list = re.findall(r"- \*\*(.+?)\*\*", offline_roster)
            if dead_list:
                dead_str = "、".join(dead_list)
                dead_warning_system = f"""

⛔⛔⛔ 【最高优先级禁令：已死亡角色黑名单】⛔⛔⛔
==================================================
以下角色已经在之前的章节中**彻底死亡**！
**绝对禁止**让他们在正文中以活人身份出现、说话、行动、发号施令或做出任何反应！
（唯一例外：回忆杀、被他人提及名字、明确描写为尸体/亡魂）

🚨 黑名单：【{dead_str}】🚨

如果你让上述任何角色"复活"或"还活着"，本章将被判定为**严重失败**！
这是最高优先级的铁律，任何创意自由都不能违反此规则！
==================================================
"""
                system_prompt = dead_warning_system + system_prompt

        # 分离活跃与已下线角色
        active_roster = character_roster
        if character_roster and "## 已下线" in character_roster:
            parts = character_roster.split("## 已下线")
            active_roster = parts[0]
        active_roster_for_prompt = self._truncate_text(
            active_roster,
            write_budget.get("active_roster", 2400),
            keep_tail=True,
        ) if active_roster else "（无角色表）"
        character_details_for_prompt = self._truncate_text(
            self._load_character_details_for_review(),
            write_budget.get("character_details", 3200),
            keep_tail=True,
        ) or "（无角色档案）"
        chapter_keywords = self._truncate_text(chapter_outline_for_prompt, 120, keep_tail=False)
        next_chapter_keywords = self._truncate_text(next_chapter_outline_for_prompt, 120, keep_tail=False)

        # 构建 user prompt 里的风格锚定摘要
        genre_style_anchor_parts = []
        if genre_guard:
            genre_style_anchor_parts.append(genre_guard)
        if positive_style_instruction:
            genre_style_anchor_parts.append(positive_style_instruction)
        genre_style_anchor_text = "\n".join(genre_style_anchor_parts) if genre_style_anchor_parts else f"当前题材：{genre}，请严格遵守题材风格要求。"

        # 主路径：从 slot 系统加载写作用户提示词模板
        writing_user_template = self._load_project_prompt("writing_user_prompt")
        if writing_user_template:
            context = self._format_prompt_text(
                writing_user_template,
                chapter=str(chapter),
                next_chapter=str(chapter + 1),
                chapter_outline=chapter_outline_for_prompt or "（无大纲）",
                recent_context=recent_context or "",
                active_roster=active_roster_for_prompt,
                character_details=character_details_for_prompt,
                realtime_status=realtime_status_for_prompt if realtime_status_for_prompt else "（无状态追踪）",
                entity_libraries=entity_libraries_for_prompt if entity_libraries_for_prompt else "（设定库为空）",
                next_chapter_outline=next_chapter_outline_for_prompt if next_chapter_outline_for_prompt else "（无下一章大纲）",
                chapter_keywords=chapter_keywords if chapter_keywords else "无",
                next_chapter_keywords=next_chapter_keywords if next_chapter_keywords else "无",
                continuity_summary=continuity_summary_for_prompt if continuity_summary_for_prompt else "（无连续性摘要）",
                previous_ending=previous_ending_for_prompt if previous_ending_for_prompt else "（这是第一章，无需衔接）",
                genre_style_anchor=genre_style_anchor_text,
            )
        else:
            # Fallback：原始硬编码
            context = f"""## 待创作：第 {chapter} 章大纲（必须严格执行！）
{chapter_outline_for_prompt}

{recent_context}
## 活跃角色表（必须使用正确名字！）
以下是当前故事中的活跃角色，写作时**必须使用正确的名字**，不要编造新角色替代现有角色：
--------------------------------------------------
{active_roster_for_prompt}
--------------------------------------------------

## 角色身份档案（最高优先级 - 必须使用正确的门派/势力！）
以下是角色的**真实身份和所属门派**，写作时角色的自称、介绍必须与档案一致！
例如：某角色档案是"落云宗刑堂长老"，台词里就必须说"落云宗"，绝对不能说成"天火门"等其他门派！
--------------------------------------------------
{character_details_for_prompt}
--------------------------------------------------

## 实时状态数值（严格遵守！数字必须一致！）
以下是当前故事中的关键数值，写作时**必须参考这些数字**，不能随意编造：
--------------------------------------------------
{realtime_status_for_prompt if realtime_status_for_prompt else "（无状态追踪）"}
--------------------------------------------------

## 设定库标准名（必须优先复用）
以下是已有实体标准名称。正文出现功法/宝物/势力/地点时，优先使用以下名称，不要凭空改名或创造近义别称：
--------------------------------------------------
{entity_libraries_for_prompt if entity_libraries_for_prompt else "（设定库为空）"}
--------------------------------------------------

## 剧情边界红线（最高优先级 - 违反即失败！）
请仔细对比【本章大纲】和【下一章大纲】，理解剧情的**时间线分配**：

【下一章大纲预览】
--------------------------------------------------
{next_chapter_outline_for_prompt if next_chapter_outline_for_prompt else "（无下一章大纲）"}
--------------------------------------------------

**边界判定规则（严格遵守！）**：
1. **关键词归属判定**：如果下一章出现"兵临城下"、"出征"、"交战"、"决战"等词，说明**战斗开始是下一章的内容**！
   - 本章只能写到：敌军逼近、战前准备、气氛紧张、双方对峙
   - 本章**绝对禁止**：城门打开、出城迎战、刀剑相向、杀敌、有人死亡

2. **冲突解决归属判定**：如果下一章标题包含"击败"、"歼灭"、"胜利"，说明**战斗胜利是下一章内容**！
   - 本章只能写到：战斗胶着、危机四伏、悬念积累
   - 本章**绝对禁止**：敌人被杀光、敌首被斩、战斗结束

3. **具体到你现在的任务**：
   - 本章（第{chapter}章）大纲关键词：{chapter_keywords if chapter_keywords else "无"}...
   - 下一章（第{chapter+1}章）大纲关键词：{next_chapter_keywords if next_chapter_keywords else "无"}...
   - **你必须在本章结尾处停在一个"即将发生"的状态，把下一章的核心内容留给下一章！**

**错误示例（违反边界的写法）**：
- 本章写"敌军冲锋，被我方死士全歼" → 下一章没东西可写了！
- 本章写"城门打开，大军杀出" → 这是下一章"出征"的内容！
- 本章写"战斗结束，敌首授首" → 你把下一章的高潮用完了！

**正确示例（留有悬念的写法）**：
- 本章结尾："远处地平线上，五千大军的火把连成一片，如同燃烧的星河……" → 悬念！下一章写战斗
- 本章结尾："顾承厄冷笑一声，缓缓拔刀：'来得正好。'" → 悬念！下一章写出征
- 本章结尾："城墙上，守卫们眼睁睁看着黑压压的大军逼近，却发现城门正在缓缓打开……" → 悬念！

## 上一章遗留状态（必须严格遵守！违反即失败！）
以下是上一章的关键细节，写作时**必须考虑每一条**，不能假装没发生：
--------------------------------------------------
{continuity_summary_for_prompt if continuity_summary_for_prompt else "（无连续性摘要）"}
--------------------------------------------------
**强制要求**：如果上一章有角色处于受伤/昏迷/在场等状态，本章**必须用至少1-2句话交代他们的去向或处理方式**，然后再推进新剧情！
不能当这些人不存在！即使大纲没提到他们，你也必须合理交代（例如：主角离开时瞥了一眼、有人来搬走了伤员、角色被锁在房间里等）。
忽视上一章遗留的角色/场景会导致严重的逻辑漏洞！

## 上一章结尾（仅供衔接定位，严禁复述！）
以下是上一章最后几段原文。你的任务是从**这段文字之后的下一个瞬间**开始写，而不是重新描写这段文字里已经发生的事情。
它只用于确认事件顺序、角色位置和动作衔接，**不得继承其中的气氛措辞、句法习惯或压抑镜头语言**。
禁止用不同的措辞重新演绎下面这些内容（换个说法重写也算复述）！
{previous_ending_for_prompt if previous_ending_for_prompt else "（这是第一章，无需衔接）"}

请开始创作第 {chapter} 章正文。
**重要指示（必须遵守！）**：
1. **字数红线**：全文 **3200-3800字**，**严禁超过 4000 字**！剧情点多就精炼写，宁可精炼也不要注水超标！
2. **剧情因果连贯**：仔细阅读上一章结尾！如果上一章是"战前准备"，本章必须写"战斗过程"，不能直接跳到"战后总结"！
3. **角色状态一致**：上一章角色如果已经醒了，本章不能又写"一直昏迷不醒"！检查每个角色的状态（清醒/昏迷、位置等），严禁前后矛盾！
4. **严禁时间跳跃词汇**：绝对不能写"几日后"、"半月后"等！直接写当前正在发生的场景！
5. **严禁复述上一章结尾**：不要复述、改写、或用不同措辞重新演绎上一章末尾已经发生的事件！上一章结尾写到哪里，本章就从那个时刻的**下一秒**开始，直接推进新剧情。
6. **立刻进入**本章大纲的第一个剧情点，用动态场景开场。
7. 确保大纲里提到的台词、动作或关键道具在正文中出现。
8. 系统提示、技能名、特殊能力等专有名词可用【】包裹，禁止使用代码块。
9. **记录标签禁入正文**：严禁输出【伤亡：...】、【消耗：...】、【状态：...】等记账标签；这类信息应写入状态系统，不得直接展示给读者。
10. **在适当位置结尾**：再次检查【剧情边界红线】！本章结尾必须在下一章内容**之前**停止，留下悬念！"""

        async for chunk in self.ai_service.chat_stream(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0.8,
            max_tokens=4300  # 收紧上限，避免偶发输出 6k+ 长章
        ):
            if not chunk:
                continue
            yield chunk


    async def _generate_chapter_content(
        self,
        chapter: int,
        context_pack: Dict,
        core_constraints: str,
        word_count: int
    ) -> str:
        """生成章节内容 (兼容版)"""
        full_content = ""
        async for chunk in self._generate_chapter_content_stream(chapter, context_pack, core_constraints, word_count):
            if not chunk:
                continue
            if not chunk.startswith("[ERROR]"):
                full_content += chunk
        return full_content

    def _extract_chapter_title(self, content: str, chapter: int) -> str:
        """从内容中提取章节标题"""
        first_line = content.split("\n")[0] if content else ""
        if first_line.startswith("#"):
            title = first_line.lstrip("#").strip()
            title = re.sub(rf"第{chapter}章[：:\s]*", "", title)
            return title[:20] if title else ""
        return ""

    async def _generate_summary(self, content: str) -> str:
        """生成章节摘要"""
        if not self.ai_service:
            return ""
        return await self.ai_service.chat(
            [{"role": "user", "content": f"请用 100-200 字概括以下章节：\n{content[:3000]}"}],
            temperature=0.3,
            max_tokens=400
        )

    async def _extract_chapter_entities(self, chapter: int, content: str) -> Optional[Dict[str, Any]]:
        """分析章节内容，提取世界观实体（不写入磁盘）。

        Returns:
            提取结果 dict（含 chapter, extraction, stats），失败时返回 None。
        """
        if not self.ai_service:
            return None

        character_file = self.project_root / "设定集" / "角色库" / "活跃角色.md"
        current_roster = ""
        if character_file.exists():
            with self._locked_file(character_file):
                current_roster = self._read_file(character_file)

        tech_lib = self.project_root / "设定集" / "功法库"
        existing_techniques: List[str] = []
        if tech_lib.exists():
            existing_techniques = [f.stem for f in sorted(tech_lib.glob("*.md"))[:80]]
        existing_techniques_text = "、".join(existing_techniques) if existing_techniques else "（空）"

        # 第一步：分块提取新角色信息（JSON），降低长章节漏检风险
        extract_budget = self._get_context_budgets("extract_state")
        chunks = self._split_text_chunks(
            content,
            chunk_size=extract_budget.get("chunk_size", 5200),
            overlap=extract_budget.get("chunk_overlap", 600),
        )
        if not chunks:
            return

        roster_for_prompt = self._truncate_text(
            current_roster,
            extract_budget.get("roster", 1800),
            keep_tail=True,
        ) if current_roster else "（空）"
        techniques_for_prompt = self._truncate_text(
            existing_techniques_text,
            extract_budget.get("techniques", 1400),
            keep_tail=False,
        )
        style_bundle, normalized_genre, normalized_substyle = self._build_project_stage_style_bundle(
            stage="章节实体抽取",
            genre_style_chars=420,
            genre_examples_chars=0,
            substyle_examples_chars=0,
        )
        substyle_display = normalized_substyle or "默认子风格"
        style_section = f"【当前阶段题材协议】\n{style_bundle}\n\n" if style_bundle else ""

        def build_extract_prompt(chunk_content: str, chunk_index: int, chunk_total: int) -> str:
            return f"""{style_section}你是小说世界观分析助手。请分析第{chapter}章的内容，提取新出现的重要元素。

【题材】
{normalized_genre} / {substyle_display}

【抽取片段】
当前处理第 {chunk_index}/{chunk_total} 段（仅输出当前片段中明确出现的事实，禁止臆测）。

【当前已有角色】
{roster_for_prompt}

【当前已有功法（标准名，必须优先复用）】
{techniques_for_prompt}

【第{chapter}章内容片段】
{chunk_content}

请提取本章**新出现**的重要元素（排除已有角色和路人），输出 JSON：
```json
{{
  "new_characters": [
    {{
      "name": "角色名",
      "importance": "major/minor/villain",
      "identity": "身份（正妻/妾室/敌将/盟友/下属等）",
      "relation": "与主角关系",
      "appearance": "外貌描写",
      "personality": "性格特点",
      "realm": "当前境界（如炼气三层、筑基初期）",
      "location": "当前地点（如青云城、外门演武场）",
      "first_action": "本章主要行为"
    }}
  ],
  "new_treasures": [
    {{
      "name": "宝物名称",
      "tier": "品级（如：地级上品、天级等）",
      "effect": "效果/用途",
      "owner": "当前持有者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为旧物升级/破损修复，填旧名称，否则留空）"
    }}
  ],
  "new_techniques": [
    {{
      "name": "功法/武技名称",
      "tier": "等级（如：玄级、地级等）",
      "effect": "效果/特点",
      "practitioner": "修炼者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为进阶/补全/融合，填旧名称，否则留空）"
    }}
  ],
  "new_organizations": [
    {{
      "name": "势力名称",
      "type": "类型（宗门/家族/国家/帮派等）",
      "strength": "实力等级",
      "relation": "与主角关系（敌对/中立/友好）",
      "key_figures": "关键人物"
    }}
  ],
  "new_locations": [
    {{
      "name": "地点名称",
      "type": "类型（城市/秘境/山脉等）",
      "features": "特点",
      "importance": "重要性说明"
    }}
  ],
  "status_changes": [
    {{
      "name": "角色名",
      "status": "当前状态（如重伤、死亡、闭关中）",
      "realm": "最新境界（未变化填空字符串）",
      "location": "最新地点（未变化填空字符串）",
      "change": "状态变化简述（如突破筑基、重伤昏迷）"
    }}
  ],
  "entity_events": [
    {{"name": "实体名称", "type": "character/treasure/technique", "event": "本章发生的关键事件/重要行为/特殊用途"}}
  ],
  "exits": [
    {{"name": "角色名", "reason": "下线原因"}}
  ],
  "status_file_updates": {{
    "chapter_event": "本章最重要的事件概述（一句话）",
    "event_consequence": "该事件的数值/状态后果",
    "character_updates": [
      {{"name": "角色名", "current_status": "新状态", "body_condition": "身体状况", "note": "备注"}}
    ],
    "resource_updates": [
      {{"resource_name": "资源名", "new_value": "新值", "reason": "变化原因"}}
    ],
    "troop_casualties": {{
      "dead_count": "死亡人数（数字或估算如'约500人'）",
      "wounded_count": "受伤人数",
      "surviving_count": "存活人数（如果正文提到）",
      "unit_name": "部队名称（如'外围死士'、'夜不收'等）",
      "description": "伤亡描述"
    }},
    "new_items": [
      {{"name": "物品名", "status": "状态", "description": "说明"}}
    ]
  }}
}}
```

⚠️ **重点关注以下数值变化**：
1. **人口伤亡**：死士、私兵、百姓的死亡/受伤人数（必须提取！）
2. **气运/香火值**：增减数值和原因
3. **属性点**：主角消耗或获得的自由属性点
4. **军事力量变化**：部队折损、阵法损坏、诡兵符消耗等

如果正文中描述了"大量阵亡"、"折损过半"、"仅剩数百"等，请在 troop_casualties 中记录！

⚠️ **命名统一规则（必须遵守）**：
1. 若正文提到的功法与【当前已有功法】显然是同一招式（简称/别称/口语化写法），不要在 `new_techniques` 新建重复档案。
2. 优先使用功法库标准名；如确需新增，请确保不是已有功法的别名。
3. `previous_version` 尽量填写可追溯的前身名称，用于后续自动归并。

如果某类没有变化，输出空数组。只输出 JSON，不要其他内容。"""

        try:
            merged_data: Dict[str, Any] = {}
            ok_chunks = 0
            chunk_total = len(chunks)
            for idx, chunk_text in enumerate(chunks, start=1):
                chunk_prompt = build_extract_prompt(chunk_text, idx, chunk_total)
                chunk_data = await self._chat_json_with_retry(
                    chunk_prompt,
                    temperature=0.3,
                    max_tokens=extract_budget.get("max_tokens", 3600),
                    retries=2,
                )
                if not chunk_data:
                    print(f"[角色系统] 第{chapter}章第{idx}段抽取失败：JSON 解析失败（已重试）")
                    continue
                normalized_chunk = self._normalize_character_extraction(chunk_data)
                merged_data = self._merge_extraction_payload(merged_data, normalized_chunk)
                ok_chunks += 1

            if ok_chunks <= 0:
                print(f"[角色系统] 第{chapter}章抽取失败：全部分段都未产出可用 JSON")
                return None

            success_ratio = ok_chunks / max(1, chunk_total)
            partial_extraction = ok_chunks < chunk_total
            if chunk_total >= 2 and success_ratio < 0.5:
                print(
                    f"[角色系统] 第{chapter}章抽取质量过低：分段成功 {ok_chunks}/{chunk_total} "
                    f"({success_ratio:.0%})，为避免脏状态写入，本次跳过落库"
                )
                return None

            data = self._normalize_character_extraction(merged_data)
            new_chars = data.get("new_characters", [])
            new_treasures = data.get("new_treasures", [])
            new_techniques = data.get("new_techniques", [])
            new_organizations = data.get("new_organizations", [])
            new_locations = data.get("new_locations", [])
            status_changes = data.get("status_changes", [])
            exits = data.get("exits", [])
            status_file_updates = data.get("status_file_updates", {})  # 新增：状态文件更新指令

            if partial_extraction:
                # 分段抽取不完整时，禁止写"状态类"数据，避免把截断结果当事实落库。
                status_changes = []
                exits = []
                status_file_updates = {}
                print(
                    f"[角色系统] 第{chapter}章抽取存在截断/失败分段（{ok_chunks}/{chunk_total}），"
                    "已跳过状态更新，仅允许新增实体档案。"
                )

            # 兜底：若 AI 未给出状态更新，则对本章实际出场角色补"活跃"状态，避免长期未知
            if current_roster and not partial_extraction:
                existing_keys = {self._name_key(c.get("name", "")) for c in status_changes if isinstance(c, dict)}
                exit_keys = {self._name_key(e.get("name", "")) for e in exits if isinstance(e, dict)}
                for entry in self._extract_roster_entries(current_roster):
                    name = self._normalize_entity_name(entry.get("name", ""))
                    if not name or len(name) < 2:
                        continue
                    key = self._name_key(name)
                    if key in existing_keys or key in exit_keys:
                        continue
                    if name not in content:
                        continue
                    status_changes.append({
                        "name": name,
                        "status": "活跃",
                        "realm": "",
                        "location": "",
                        "change": "本章出场",
                    })
                    existing_keys.add(key)

            print(
                f"[角色系统] 第{chapter}章抽取结果:"
                f" 角色{len(new_chars)} 宝物{len(new_treasures)} 功法{len(new_techniques)}"
                f" 势力{len(new_organizations)} 地点{len(new_locations)} 状态变更{len(status_changes)} 下线{len(exits)}"
                f"（分段成功 {ok_chunks}/{chunk_total}）"
            )

            extraction = {
                "new_characters": new_chars,
                "new_treasures": new_treasures,
                "new_techniques": new_techniques,
                "new_organizations": new_organizations,
                "new_locations": new_locations,
                "status_changes": status_changes,
                "entity_events": data.get("entity_events", []),
                "exits": exits,
                "status_file_updates": status_file_updates,
            }

            return {
                "chapter": chapter,
                "extraction": extraction,
                "stats": {
                    "chunks_total": chunk_total,
                    "chunks_ok": ok_chunks,
                    "partial_extraction": partial_extraction,
                },
            }

        except Exception as e:
            print(f"[角色系统] 提取章节实体失败: {e}")
            return None

    async def _apply_extraction_results(self, chapter: int, content: str, extraction: Dict[str, Any]) -> Dict[str, Any]:
        """将提取结果写入磁盘（创建实体文件、更新状态、更新活跃角色表、更新实时状态）。

        Args:
            chapter: 章节号
            content: 章节正文
            extraction: 提取结果 dict（可能是用户确认后过滤的子集）

        Returns:
            操作摘要 dict
        """
        new_chars = extraction.get("new_characters", [])
        new_treasures = extraction.get("new_treasures", [])
        new_techniques = extraction.get("new_techniques", [])
        new_organizations = extraction.get("new_organizations", [])
        new_locations = extraction.get("new_locations", [])
        status_changes = extraction.get("status_changes", [])
        exits = extraction.get("exits", [])
        status_file_updates = extraction.get("status_file_updates", {})

        has_changes = any([new_chars, new_treasures, new_techniques, new_organizations, new_locations, status_changes, exits, status_file_updates])
        if not has_changes:
            print(f"[世界观系统] 第{chapter}章无需写入的元素")
            return {"created_files": 0, "updated_entities": 0, "roster_updated": False}

        character_file = self.project_root / "设定集" / "角色库" / "活跃角色.md"
        current_roster = ""
        if character_file.exists():
            with self._locked_file(character_file):
                current_roster = self._read_file(character_file)

        # 先补齐已有角色档案字段
        self._ensure_character_schema(chapter_hint=chapter)

        try:
            created_files = 0
            updated_entities = 0
            roster_updated = False
            settings_root = self.project_root / "设定集"
            entity_exact: Dict[str, Path] = {}
            entity_key_index: Dict[str, Path] = {}

            def register_entity_file(path: Path) -> None:
                stem = self._normalize_entity_name(path.stem)
                if not stem:
                    return
                entity_exact.setdefault(stem, path)
                entity_key_index.setdefault(self._name_key(stem), path)

            for f in self._iter_character_files():
                register_entity_file(f)
            for lib_name in ["宝物库", "功法库", "势力库", "地点库"]:
                lib_dir = settings_root / lib_name
                if not lib_dir.exists():
                    continue
                for f in lib_dir.glob("*.md"):
                    register_entity_file(f)
            
            # 第二步：为新角色创建独立档案
            if new_chars:
                char_lib = self.project_root / "设定集" / "角色库"
                (char_lib / "主要角色").mkdir(parents=True, exist_ok=True)
                (char_lib / "次要角色").mkdir(parents=True, exist_ok=True)
                (char_lib / "反派角色").mkdir(parents=True, exist_ok=True)
                
                for char in new_chars:
                    name = self._normalize_entity_name(char.get("name", ""))
                    if not name:
                        continue

                    # 名称归一：若已有档案（含括号别名），复用已有名字，避免重复建档
                    existing_char_file = self._find_character_file_by_name(name)
                    if existing_char_file:
                        char["name"] = existing_char_file.stem
                        continue
                    
                    # 根据 AI 判断的重要性分类
                    importance = self._safe_text(char.get("importance", "minor")).lower()
                    char_dir = char_lib / self._infer_character_category(importance=importance, identity=char.get("identity", ""))
                    
                    char_file_path = char_dir / f"{name}.md"
                    if char_file_path.exists():
                        continue
                    char["name"] = name
                    
                    # 使用 character-design skill 模板
                    file_content = f"""# {name}

## 基本信息
- **身份**：{self._safe_text(char.get("identity", "未知"))}
- **首次出场**：第{chapter}章
- **当前境界**：{self._safe_text(char.get("realm", "未知"))}
- **当前状态**：存活
- **当前地点**：{self._safe_text(char.get("location", "未知"))}
- **最后更新章节**：第{chapter}章

## 与主角关系
{self._safe_text(char.get("relation", "待补充"))}

## 外貌描写
{self._safe_text(char.get("appearance", "待补充（从正文中提取）"))}

## 性格特点
{self._safe_text(char.get("personality", "待补充"))}

## 关键事件时间线
- 第{chapter}章：{self._safe_text(char.get("first_action", "初次登场"))}

---
*档案创建于第{chapter}章写作后*
"""
                    char_file_path.write_text(file_content, encoding="utf-8")
                    created_files += 1
                    register_entity_file(char_file_path)
                    print(f"[世界观系统] 创建角色档案: {char_dir.name}/{name}.md")
            
            # 创建宝物档案
            if new_treasures:
                treasure_lib = self.project_root / "设定集" / "宝物库"
                treasure_lib.mkdir(parents=True, exist_ok=True)
                for item in new_treasures:
                    name = self._normalize_entity_name(item.get("name", ""))
                    if not name:
                        continue
                    existing_file = self._find_entity_file_in_dir(treasure_lib, name)
                    if existing_file:
                        continue
                    file_path = treasure_lib / f"{name}.md"
                    
                    # 检查是否有前身
                    prev_name = self._normalize_entity_name(item.get("previous_version", ""))
                    evolution_info = ""
                    if prev_name and prev_name != name:
                        prev_file = self._find_entity_file_in_dir(treasure_lib, prev_name)
                        if prev_file and prev_file.exists():
                            prev_name = prev_file.stem
                            evolution_info = f"\n## 演变记录\n- **前身**：[[{prev_name}]]（第{chapter}章演变为{name}）\n"
                            
                            # 更新旧档案，添加后续指向
                            try:
                                prev_content = prev_file.read_text(encoding="utf-8")
                                if "## 后续演变" not in prev_content:
                                    prev_content += f"\n## 后续演变\n- **进化为**：[[{name}]]（第{chapter}章）\n"
                                    prev_file.write_text(prev_content, encoding="utf-8")
                                    print(f"[世界观系统] 更新前身宝物档案: {prev_name}.md")
                            except Exception as e:
                                print(f"[世界观系统] 更新前身宝物失败: {e}")

                    content = f"""# {name}

## 基本信息
- **品级**：{self._safe_text(item.get("tier", "未知"))}
- **首次出现**：第{chapter}章
- **持有者**：{self._safe_text(item.get("owner", "未知"))}

## 效果/用途
{self._safe_text(item.get("effect", "待补充"))}

## 来源/出处
{self._safe_text(item.get("origin", "待补充"))}
{evolution_info}
---
*档案创建于第{chapter}章*
"""
                    file_path.write_text(content, encoding="utf-8")
                    created_files += 1
                    register_entity_file(file_path)
                    print(f"[世界观系统] 创建宝物档案: {name}.md")
            
            # 创建功法档案
            if new_techniques:
                tech_lib = self.project_root / "设定集" / "功法库"
                tech_lib.mkdir(parents=True, exist_ok=True)
                for item in new_techniques:
                    name = self._normalize_entity_name(item.get("name", ""))
                    if not name:
                        continue
                    existing_file = self._find_entity_file_in_dir(tech_lib, name)
                    if not existing_file:
                        existing_file = self._find_similar_entity_file_in_dir(tech_lib, name)
                    if existing_file:
                        if existing_file.stem != name:
                            print(f"[世界观系统] 功法别名归并: {name} -> {existing_file.stem}")
                        item["name"] = existing_file.stem
                        continue
                    file_path = tech_lib / f"{name}.md"
                    
                    # 检查是否有前身
                    prev_name = self._normalize_entity_name(item.get("previous_version", ""))
                    evolution_info = ""
                    if prev_name and prev_name != name:
                        prev_file = self._find_entity_file_in_dir(tech_lib, prev_name)
                        if prev_file and prev_file.exists():
                            prev_name = prev_file.stem
                            evolution_info = f"\n## 演变记录\n- **前身**：[[{prev_name}]]（第{chapter}章进阶为{name}）\n"
                            
                            # 更新旧档案
                            try:
                                prev_content = prev_file.read_text(encoding="utf-8")
                                if "## 后续演变" not in prev_content:
                                    prev_content += f"\n## 后续演变\n- **进阶为**：[[{name}]]（第{chapter}章）\n"
                                    prev_file.write_text(prev_content, encoding="utf-8")
                                    print(f"[世界观系统] 更新前身功法档案: {prev_name}.md")
                            except Exception as e:
                                print(f"[世界观系统] 更新前身功法失败: {e}")

                    content = f"""# {name}

## 基本信息
- **等级**：{self._safe_text(item.get("tier", "未知"))}
- **首次出现**：第{chapter}章
- **修炼者**：{self._safe_text(item.get("practitioner", "未知"))}

## 效果/特点
{self._safe_text(item.get("effect", "待补充"))}

## 来源/出处
{self._safe_text(item.get("origin", "待补充"))}
{evolution_info}
---
*档案创建于第{chapter}章*
"""
                    file_path.write_text(content, encoding="utf-8")
                    created_files += 1
                    register_entity_file(file_path)
                    print(f"[世界观系统] 创建功法档案: {name}.md")
            
            # 创建势力档案
            if new_organizations:
                org_lib = self.project_root / "设定集" / "势力库"
                org_lib.mkdir(parents=True, exist_ok=True)
                for item in new_organizations:
                    name = self._normalize_entity_name(item.get("name", ""))
                    if not name:
                        continue
                    existing_file = self._find_entity_file_in_dir(org_lib, name)
                    if existing_file:
                        continue
                    file_path = org_lib / f"{name}.md"
                    content = f"""# {name}

## 基本信息
- **类型**：{self._safe_text(item.get("type", "未知"))}
- **实力等级**：{self._safe_text(item.get("strength", "未知"))}
- **首次出现**：第{chapter}章

## 与主角关系
{self._safe_text(item.get("relation", "未知"))}

## 关键人物
{self._safe_text(item.get("key_figures", "待补充"))}

---
*档案创建于第{chapter}章*
"""
                    file_path.write_text(content, encoding="utf-8")
                    created_files += 1
                    register_entity_file(file_path)
                    print(f"[世界观系统] 创建势力档案: {name}.md")
            
            # 创建地点档案
            if new_locations:
                loc_lib = self.project_root / "设定集" / "地点库"
                loc_lib.mkdir(parents=True, exist_ok=True)
                for item in new_locations:
                    name = self._normalize_entity_name(item.get("name", ""))
                    if not name:
                        continue
                    # 清理名称中的特殊字符（防止嵌套路径）
                    safe_name = self._normalize_entity_name(name)
                    existing_file = self._find_entity_file_in_dir(loc_lib, safe_name)
                    if existing_file:
                        continue
                    file_path = loc_lib / f"{safe_name}.md"
                    content = f"""# {name}

## 基本信息
- **类型**：{self._safe_text(item.get("type", "未知"))}
- **首次出现**：第{chapter}章

## 特点
{self._safe_text(item.get("features", "待补充"))}

## 重要性
{self._safe_text(item.get("importance", "待补充"))}

---
*档案创建于第{chapter}章*
"""
                    file_path.write_text(content, encoding="utf-8")
                    created_files += 1
                    register_entity_file(file_path)
                    print(f"[世界观系统] 创建地点档案: {name}.md")
            
            # --- 第三步：更新已有档案（事件与状态）---
            entity_events = extraction.get("entity_events", [])
            
            # 辅助函数：查找实体文件
            def find_entity_file(e_name):
                if not e_name:
                    return None
                query_name = self._normalize_entity_name(e_name)
                query_key = self._name_key(query_name)
                exact = entity_exact.get(query_name)
                if exact:
                    return exact
                return entity_key_index.get(query_key)

            def parse_roster_name(line: str) -> str:
                m = re.search(r"\*\*(.+?)\*\*", line or "")
                return self._normalize_entity_name(m.group(1)) if m else ""

            def resolve_roster_name(name: str, roster_lines: List[str]) -> str:
                target = self._normalize_entity_name(name)
                if not target:
                    return ""
                target_key = self._name_key(target)
                for row in roster_lines:
                    row_name = parse_roster_name(row)
                    if row_name and self._name_key(row_name) == target_key:
                        return row_name
                found_file = self._find_character_file_by_name(target)
                return found_file.stem if found_file else target

            # 1. 处理关键事件 (entity_events)
            for event in entity_events:
                name = self._normalize_entity_name(event.get("name", ""))
                desc = self._safe_text(event.get("event", "")).strip()
                if not name or not desc:
                    continue
                
                file_path = find_entity_file(name)
                if file_path:
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        
                        # 判断追加的位置
                        append_header = "## 关键事件时间线"
                        if append_header not in content:
                            if "## 后续演变" in content:
                                append_header = "## 后续演变"
                            else:
                                # 如果都没有，加在最后
                                content += f"\n\n{append_header}\n"
                        
                        # 检查是否重复
                        new_line = f"- 第{chapter}章：{desc}"
                        if new_line not in content:
                            # 在对应标题后追加
                            lines = content.split("\n")
                            for i, line in enumerate(lines):
                                if append_header in line:
                                    # 往下找直到下一个标题或文件结束
                                    insert_pos = i + 1
                                    while insert_pos < len(lines) and not lines[insert_pos].strip().startswith("#"):
                                        insert_pos += 1
                                    lines.insert(insert_pos, new_line)
                                    break
                            content = "\n".join(lines)
                            file_path.write_text(content, encoding="utf-8")
                            print(f"[世界观系统] 更新档案事件: {name} -> {desc[:20]}...")
                            updated_entities += 1
                    except Exception as e:
                        print(f"[世界观系统] 更新档案失败 {name}: {e}")

            # 2. 处理状态变更 (status_changes) 同步到档案
            for change in status_changes:
                name = self._normalize_entity_name(change.get("name", ""))
                status_text = self._safe_text(change.get("status", "")).strip()
                realm_text = self._safe_text(change.get("realm", "")).strip()
                location_text = self._safe_text(change.get("location", "")).strip()
                desc = self._safe_text(change.get("change", "")).strip()

                if not name or not any([status_text, realm_text, location_text, desc]):
                    continue
                    
                file_path = find_entity_file(name)
                if file_path:
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        original = content

                        # 先保证字段存在
                        for label, default in [
                            ("当前境界", "未知"),
                            ("当前状态", "存活"),
                            ("当前地点", "未知"),
                            ("最后更新章节", f"第{chapter}章"),
                        ]:
                            content, _ = self._ensure_basic_info_field(content, label, default)

                        # 再写入本章结构化状态
                        if status_text:
                            content, _ = self._set_basic_info_field(content, "当前状态", status_text)
                        if realm_text:
                            content, _ = self._set_basic_info_field(content, "当前境界", realm_text)
                        if location_text:
                            content, _ = self._set_basic_info_field(content, "当前地点", location_text)
                        content, _ = self._set_basic_info_field(content, "最后更新章节", f"第{chapter}章")

                        # 记录时间线
                        timeline_parts = []
                        if desc:
                            timeline_parts.append(desc)
                        if status_text:
                            timeline_parts.append(f"状态：{status_text}")
                        if realm_text:
                            timeline_parts.append(f"境界：{realm_text}")
                        if location_text:
                            timeline_parts.append(f"地点：{location_text}")
                        timeline_parts = list(dict.fromkeys(timeline_parts))
                        timeline_desc = "；".join(timeline_parts) if timeline_parts else "状态更新"
                        content, _ = self._append_character_timeline(content, chapter, f"[状态变更] {timeline_desc}")

                        if content != original:
                            file_path.write_text(content, encoding="utf-8")
                            print(f"[世界观系统] 更新档案状态: {name} -> {timeline_desc[:40]}")
                            updated_entities += 1
                    except Exception as e:
                         print(f"[世界观系统] 更新状态失败 {name}: {e}")
            
            # 更新活跃角色表
            if current_roster:
                with self._locked_file(character_file):
                    latest_roster = self._read_file(character_file) or current_roster
                    roster_lines = latest_roster.split("\n")
                    existing_roster_keys = {self._name_key(e["name"]) for e in self._extract_roster_entries(latest_roster)}
                    
                    # 添加新角色到角色表
                    for char in new_chars:
                        name = self._normalize_entity_name(char.get("name", ""))
                        identity = self._safe_text(char.get("identity", ""))
                        if not name:
                            continue

                        canonical_name = resolve_roster_name(name, roster_lines)
                        key = self._name_key(canonical_name)
                        if key not in existing_roster_keys:
                            existing_roster_keys.add(key)
                            new_line = f"- **{canonical_name}**｜{identity}｜第{chapter}章登场"
                            # 找到合适位置插入
                            insert_idx = len(roster_lines)
                            for i, line in enumerate(roster_lines):
                                if "## 已下线" in line:
                                    insert_idx = i
                                    break
                            roster_lines.insert(insert_idx, new_line)
                    
                    # 更新状态变化（跳过已下线角色）
                    offline_section_start = -1
                    for i, line in enumerate(roster_lines):
                        if "## 已下线" in line:
                            offline_section_start = i
                            break
                    
                    for change in status_changes:
                        name = resolve_roster_name(change.get("name", ""), roster_lines)
                        status_text = self._safe_text(change.get("status", "")).strip()
                        change_desc = self._safe_text(change.get("change", "")).strip()
                        realm_text = self._safe_text(change.get("realm", "")).strip()
                        location_text = self._safe_text(change.get("location", "")).strip()
                        extra = []
                        if realm_text:
                            extra.append(f"境界:{realm_text}")
                        if location_text:
                            extra.append(f"地点:{location_text}")
                        if not change_desc:
                            change_desc = status_text
                        if extra:
                            addon = "；".join(extra)
                            change_desc = f"{change_desc}（{addon}）" if change_desc else addon
                        if not change_desc:
                            continue
                        target_key = self._name_key(name)
                        for i, line in enumerate(roster_lines):
                            line_name = parse_roster_name(line)
                            if not line_name or self._name_key(line_name) != target_key:
                                continue
                            # 检查是否在"已下线"区域之后
                            if offline_section_start >= 0 and i >= offline_section_start:
                                print(f"[角色系统] ⚠️ 警告：角色 {name} 已在「已下线」区域，跳过状态更新（可能是 AI 幻觉复活了死人！）")
                                continue
                            roster_lines[i] = line.rstrip() + f"→第{chapter}章{change_desc}"
                            break
                    
                    # 处理角色下线（死亡/离场）- 移动到"已下线"区域
                    for exit_info in exits:
                        exit_name = resolve_roster_name(exit_info.get("name", ""), roster_lines)
                        exit_reason = self._safe_text(exit_info.get("reason", "下线"))
                        if not exit_name:
                            continue
                        
                        # 找到该角色在活跃区域的行
                        exit_line_idx = -1
                        target_key = self._name_key(exit_name)
                        for i, line in enumerate(roster_lines):
                            line_name = parse_roster_name(line)
                            if line_name and self._name_key(line_name) == target_key and not line.startswith("## 已下线"):
                                exit_line_idx = i
                                break
                        
                        if exit_line_idx >= 0:
                            # 从活跃区域删除
                            roster_lines.pop(exit_line_idx)
                            
                            # 构建下线记录
                            offline_entry = f"- **{exit_name}**｜已死｜第{chapter}章{exit_reason}"
                            
                            # 找到"已下线"区域并插入
                            offline_section_idx = -1
                            for i, line in enumerate(roster_lines):
                                if "## 已下线" in line:
                                    offline_section_idx = i
                                    break
                            
                            if offline_section_idx >= 0:
                                # 在"已下线"标题后插入
                                roster_lines.insert(offline_section_idx + 1, offline_entry)
                            else:
                                # 如果没有"已下线"区域，在末尾创建
                                roster_lines.append("")
                                roster_lines.append("## 已下线（仅保留记录）")
                                roster_lines.append(offline_entry)
                            
                            print(f"[角色系统] 角色下线: {exit_name} -> 已下线（{exit_reason}）")
                    
                    # 更新章节号
                    for i, line in enumerate(roster_lines):
                        if "# 活跃角色表" in line:
                            roster_lines[i] = f"# 活跃角色表（更新于第{chapter}章）"
                            break
                    
                    updated_roster = "\n".join(roster_lines)
                    character_file.write_text(updated_roster, encoding="utf-8")
                    print(f"[角色系统] 已更新活跃角色表（第{chapter}章后）")
                    roster_updated = True

            # 规则兜底：活跃角色表出现但未建档时，自动补建档案
            backfill_count = self._ensure_character_profiles_from_roster(chapter_hint=chapter)
            if backfill_count > 0:
                print(f"[角色系统] 规则补建完成：补建角色档案 {backfill_count} 个")
            print(f"[角色系统] 第{chapter}章档案写入完成：新增文件 {created_files} 个")
            
            # --- 代码驱动更新实时状态文件（使用 status_file_updates） ---
            status_file = self.project_root / "设定集" / "实时状态.md"
            if status_file.exists() and status_file_updates:
                try:
                    with self._locked_file(status_file):
                        current_status = status_file.read_text(encoding="utf-8")
                        lines = current_status.split("\n")
                        updated = False

                        # 1. 更新时间戳
                        for i, line in enumerate(lines):
                            if "更新时间" in line:
                                lines[i] = re.sub(r"第\d+章后?", f"第{chapter}章后", line)
                                updated = True
                                break

                        # 2. 更新角色状态表（核心家将/骨干表格）
                        character_updates = status_file_updates.get("character_updates", [])
                        for char_update in character_updates:
                            char_name = char_update.get("name", "")
                            if not char_name:
                                continue
                            for i, line in enumerate(lines):
                                if f"**{char_name}**" in line and line.startswith("|"):
                                    parts = [p.strip() for p in line.split("|")]
                                    if len(parts) >= 6:
                                        new_status = char_update.get("current_status", "")
                                        new_body = char_update.get("body_condition", "")
                                        new_note = char_update.get("note", "")
                                        if new_status:
                                            parts[3] = f"**{new_status}**"
                                        if new_body:
                                            parts[4] = f"**{new_body}**"
                                        if new_note:
                                            parts[5] = f"**{new_note}**"
                                        lines[i] = " | ".join(parts)
                                        updated = True
                                    break

                        # 3. 添加新事件记录
                        chapter_event = status_file_updates.get("chapter_event", "")
                        event_consequence = status_file_updates.get("event_consequence", "")
                        if chapter_event:
                            new_event_line = f"| **第{chapter}章** | **{chapter_event}** | {event_consequence} |"
                            for i, line in enumerate(lines):
                                if "重大事件记录" in line:
                                    insert_pos = i + 3
                                    if insert_pos < len(lines):
                                        lines.insert(insert_pos, new_event_line)
                                        updated = True
                                    break

                        # 4. 添加新物品到特殊物品表
                        new_items = status_file_updates.get("new_items", [])
                        if new_items:
                            for item in new_items:
                                item_name = item.get("name", "")
                                item_status = item.get("status", "")
                                item_desc = item.get("description", "")
                                if item_name:
                                    new_item_line = f"| **{item_name}** | **{item_status}** | {item_desc} | **第{chapter}章** |"
                                    for i, line in enumerate(lines):
                                        if "特殊物品" in line or "法器" in line:
                                            insert_pos = i + 1
                                            while insert_pos < len(lines) and lines[insert_pos].startswith("|"):
                                                insert_pos += 1
                                            lines.insert(insert_pos, new_item_line)
                                            updated = True
                                            break

                        # 5. 更新资源值
                        resource_updates = status_file_updates.get("resource_updates", [])
                        for res in resource_updates:
                            res_name = res.get("resource_name", "")
                            new_value = res.get("new_value", "")
                            reason = res.get("reason", "")
                            if res_name and new_value:
                                for i, line in enumerate(lines):
                                    if res_name in line and line.startswith("|"):
                                        parts = [p.strip() for p in line.split("|")]
                                        if len(parts) >= 4:
                                            parts[2] = f"**{new_value}**"
                                            parts[3] = f"**第{chapter}章（{reason}）**"
                                            lines[i] = " | ".join(parts)
                                            updated = True
                                        break

                        # 6. 处理部队伤亡数据（更新家族人口表）
                        troop_casualties = status_file_updates.get("troop_casualties", {})
                        if troop_casualties and troop_casualties.get("unit_name"):
                            unit_name = troop_casualties.get("unit_name", "")
                            dead_count = troop_casualties.get("dead_count", "")
                            surviving_count = troop_casualties.get("surviving_count", "")
                            description = troop_casualties.get("description", "")
                            casualty_updated = False

                            for i, line in enumerate(lines):
                                if unit_name in line and line.startswith("|"):
                                    parts = [p.strip() for p in line.split("|")]
                                    if len(parts) >= 4:
                                        if surviving_count:
                                            parts[2] = f"**{surviving_count}**"
                                        elif dead_count:
                                            parts[2] = f"**折损严重（-{dead_count}）**"
                                        parts[3] = f"**第{chapter}章（{description or '战斗伤亡'}）**"
                                        lines[i] = " | ".join(parts)
                                        updated = True
                                        casualty_updated = True
                                        print(f"[状态系统] 更新部队伤亡: {unit_name} -> {surviving_count or dead_count}")
                                    break

                            if not casualty_updated and (dead_count or surviving_count):
                                casualty_event = f"| **第{chapter}章** | **{unit_name}伤亡: {description}** | 阵亡{dead_count or '未知'}，存活{surviving_count or '未知'} |"
                                for i, line in enumerate(lines):
                                    if "重大事件记录" in line:
                                        insert_pos = i + 3
                                        if insert_pos < len(lines):
                                            lines.insert(insert_pos, casualty_event)
                                            updated = True
                                            print(f"[状态系统] 记录伤亡事件: {unit_name}")
                                        break

                        # 7. 智能截断：只保留最近20章事件
                        MAX_EVENT_CHAPTERS = 20
                        event_count = 0
                        archive_lines = []
                        for line in lines:
                            if line.startswith("| **第") and "章**" in line:
                                event_count += 1
                                if event_count > MAX_EVENT_CHAPTERS:
                                    archive_lines.append(line)

                        # 归档老旧事件
                        if archive_lines:
                            archive_file = self.project_root / "设定集" / "历史事件归档.md"
                            archive_content = ""
                            if archive_file.exists():
                                archive_content = archive_file.read_text(encoding="utf-8")
                            else:
                                archive_content = "# 历史事件归档\n\n> 此文件保存超过20章的老旧事件记录，AI写作时无需参考。\n\n| 章节 | 事件 | 数值变化 |\n|------|------|----------|\n"
                            for line in archive_lines:
                                if line not in archive_content:
                                    archive_content += line + "\n"
                            archive_file.write_text(archive_content, encoding="utf-8")
                            print(f"[状态系统] 已归档 {len(archive_lines)} 条老旧事件")
                            lines = [line for line in lines if line not in archive_lines]

                        if updated:
                            status_file.write_text("\n".join(lines), encoding="utf-8")
                            print(f"[状态系统] 已更新实时状态文件（第{chapter}章后）")
                    
                except Exception as e:
                    print(f"[状态系统] 更新失败: {e}")
            
            # ── 同步 state.json：protagonist_state + relationships + progress ──
            try:
                self._sync_state_from_extraction(chapter, new_chars, status_changes, exits)
            except Exception as e:
                print(f"[状态系统] 同步 state.json 失败: {e}")

        except Exception as e:
            print(f"[角色系统] 应用提取结果失败: {e}")
            return {"created_files": created_files, "updated_entities": updated_entities, "roster_updated": False}

        return {"created_files": created_files, "updated_entities": updated_entities, "roster_updated": roster_updated}

    def _resolve_protagonist_name(self) -> str:
        """从多个来源尝试解析主角名：state.json → 主角卡 → 大纲。"""
        # 1) state.json
        state = self._load_state()
        if state:
            name = self._safe_text(state.get("protagonist_state", {}).get("name", "")).strip()
            if name:
                return name

        # 2) 主角卡
        card_file = self.project_root / "设定集" / "主角卡.md"
        if card_file.exists():
            card_text = card_file.read_text(encoding="utf-8")
            name = self._extract_protagonist_name_from_card(card_text)
            if name:
                return name

        # 3) 大纲（匹配 **主角**：XXX 或 - **主角**：XXX）
        outline_dir = self.project_root / "大纲"
        if outline_dir.exists():
            for f in sorted(outline_dir.glob("*.md")):
                text = f.read_text(encoding="utf-8")
                m = re.search(r"\*?\*?主角\*?\*?[：:]\s*([^\s,，｜|（(]+)", text)
                if m:
                    name = self._normalize_entity_name(m.group(1))
                    if name and "待填写" not in name:
                        return name
        return ""

    def _sync_state_from_extraction(self, chapter: int, new_chars: list, status_changes: list, exits: list) -> None:
        """将提取结果同步到 state.json 的 protagonist_state、relationships、progress。"""
        protagonist_name = self._resolve_protagonist_name()

        def _updater(state: Dict[str, Any]) -> None:
            from datetime import datetime

            # ── 1. protagonist_state ──
            pstate = state.setdefault("protagonist_state", {})
            # 如果主角名还没写入，补上
            if not pstate.get("name") and protagonist_name:
                pstate["name"] = protagonist_name

            cur_protagonist = pstate.get("name", "")

            # 从 status_changes 更新主角状态
            for sc in status_changes:
                sc_name = self._normalize_entity_name(sc.get("name", ""))
                if sc_name and sc_name == cur_protagonist:
                    if sc.get("realm"):
                        pstate.setdefault("power", {})["realm"] = sc["realm"]
                    if sc.get("location"):
                        pstate.setdefault("location", {})["current"] = sc["location"]
                        pstate["location"]["last_chapter"] = chapter

            # 从 new_characters 也补充主角状态（有时主角出现在 status_changes 而非 new_chars）
            for char in new_chars:
                cname = self._normalize_entity_name(char.get("name", ""))
                if cname and cname == cur_protagonist:
                    if char.get("realm") and not pstate.get("power", {}).get("realm"):
                        pstate.setdefault("power", {})["realm"] = char["realm"]
                    if char.get("location") and not pstate.get("location", {}).get("current"):
                        pstate.setdefault("location", {})["current"] = char["location"]
                        pstate["location"]["last_chapter"] = chapter

            # ── 2. relationships ──
            rels = state.setdefault("relationships", {})

            for char in new_chars:
                cname = self._normalize_entity_name(char.get("name", ""))
                relation = self._safe_text(char.get("relation", "")).strip()
                if not cname or cname == cur_protagonist:
                    continue
                if not relation or relation == "待补充":
                    continue
                # 新角色直接写入；已有角色只更新变化的字段
                existing = rels.get(cname, {})
                rels[cname] = {
                    "relation": relation,
                    "status": existing.get("status", "存活"),
                    "realm": char.get("realm", "") or existing.get("realm", ""),
                    "first_chapter": existing.get("first_chapter", chapter),
                    "last_chapter": chapter,
                }

            for sc in status_changes:
                sc_name = self._normalize_entity_name(sc.get("name", ""))
                if not sc_name or sc_name == cur_protagonist:
                    continue
                if sc_name in rels:
                    if sc.get("realm"):
                        rels[sc_name]["realm"] = sc["realm"]
                    if sc.get("status"):
                        rels[sc_name]["status"] = sc["status"]
                    rels[sc_name]["last_chapter"] = chapter

            for ex in exits:
                ex_name = self._normalize_entity_name(ex.get("name", ""))
                if ex_name and ex_name in rels:
                    rels[ex_name]["status"] = f"下线: {self._safe_text(ex.get('reason', ''))}"
                    rels[ex_name]["last_chapter"] = chapter

            # ── 3. progress ──
            prog = state.setdefault("progress", {})
            if chapter > prog.get("current_chapter", 0):
                prog["current_chapter"] = chapter
            prog["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._update_state(_updater)

        # ── 确保主角档案存在 ──
        if protagonist_name:
            self._ensure_protagonist_profile(protagonist_name, chapter, status_changes)

        print(f"[状态系统] state.json 已同步（第{chapter}章提取结果）")

    def _ensure_protagonist_profile(self, name: str, chapter: int, status_changes: list) -> None:
        """如果主角档案不存在，自动创建。"""
        existing = self._find_character_file_by_name(name)
        if existing:
            return

        char_lib = self.project_root / "设定集" / "角色库"
        main_dir = char_lib / "主要角色"
        main_dir.mkdir(parents=True, exist_ok=True)

        # 从大纲中尝试获取更多主角信息
        realm = ""
        identity = "主角"
        for sc in status_changes:
            if self._normalize_entity_name(sc.get("name", "")) == name:
                realm = sc.get("realm", "") or realm

        # 尝试从大纲提取境界和身份
        outline_dir = self.project_root / "大纲"
        if outline_dir.exists():
            for f in sorted(outline_dir.glob("*.md")):
                text = f.read_text(encoding="utf-8")
                # 匹配初始境界
                m = re.search(r"初始境界[：:]\s*\*?\*?([^*\n]+)", text)
                if m and not realm:
                    realm = m.group(1).strip()
                # 匹配身份
                m = re.search(r"身份[：:]\s*([^\n]+)", text)
                if m:
                    identity = m.group(1).strip()
                if realm:
                    break

        profile_path = main_dir / f"{name}.md"
        profile_path.write_text(f"""# {name}

## 基本信息
- **身份**：{identity}
- **首次出场**：第1章
- **当前境界**：{realm or '未知'}
- **当前状态**：存活
- **当前地点**：未知
- **最后更新章节**：第{chapter}章

## 与主角关系
主角本人

## 外貌描写
待补充（从正文中提取）

## 性格特点
待补充

## 关键事件时间线
- 第1章：初次登场

---
*档案创建于第{chapter}章设定同步后*
""", encoding="utf-8")
        print(f"[角色系统] 自动创建主角档案: 主要角色/{name}.md")

    async def _update_character_state(self, chapter: int, content: str) -> None:
        """分析章节内容，自动更新活跃角色表 + 创建新角色档案（向后兼容包装）"""
        result = await self._extract_chapter_entities(chapter, content)
        if result is None:
            return
        await self._apply_extraction_results(chapter, content, result["extraction"])

    async def sync_post_save_artifacts(self, chapter: int, content: str) -> Dict[str, Any]:
        """在用户确认保存后执行持久化副作用（RAG 索引 + 连续性摘要）。"""
        text = self._safe_text(content)
        if not text.strip():
            return {"rag_indexed": False, "continuity_written": False}

        rag_indexed = False
        continuity_written = False

        rag = None
        try:
            from data_modules.rag_adapter import RAGAdapter
            from data_modules.config import DataModulesConfig
            rag_config = DataModulesConfig.from_project_root(self.project_root)
            rag = RAGAdapter(rag_config)

            scene_chunks = self._split_content_for_rag(text, chunk_size=1800, overlap=220)
            chunks = [
                {
                    "chapter": chapter,
                    "scene_index": item.get("scene_index", idx + 1),
                    "content": item.get("content", ""),
                }
                for idx, item in enumerate(scene_chunks)
                if self._safe_text(item.get("content", "")).strip()
            ]
            await rag.store_chunks(chunks)
            rag_indexed = True
        except Exception as e:
            print(f"[POST-SAVE RAG] Failed: {e}")
        finally:
            try:
                if rag and getattr(rag, "api_client", None):
                    close_fn = getattr(rag.api_client, "close", None)
                    if close_fn:
                        await close_fn()
            except Exception as close_err:
                print(f"[POST-SAVE RAG] Failed to close client session: {close_err}")

        try:
            continuity_summary = await self._generate_continuity_summary(chapter, text)
            if continuity_summary:
                continuity_dir = self.project_root / "正文" / ".continuity"
                continuity_dir.mkdir(parents=True, exist_ok=True)
                continuity_file = continuity_dir / f"第{chapter}章_状态.md"
                continuity_file.write_text(continuity_summary, encoding="utf-8")
                continuity_written = True
        except Exception as e:
            print(f"[POST-SAVE CONTINUITY] Failed: {e}")

        return {"rag_indexed": rag_indexed, "continuity_written": continuity_written}

    async def _generate_continuity_summary(self, chapter: int, content: str) -> str:
        """生成章节连续性摘要，供下一章参考"""
        if not self.ai_service:
            return ""
        continuity_budget = self._get_context_budgets("continuity_summary")
        content_for_prompt = self._truncate_text(
            content,
            continuity_budget.get("content", 9000),
            keep_tail=True,
        )
        prompt = f"""你是一位负责维护小说连续性的编辑。请仔细阅读以下第{chapter}章内容，提取所有【下一章必须遵守】的关键信息。

【第{chapter}章内容】
{content_for_prompt}

请自由总结以下内容（如果有的话）：
1. **场景状态**：当前地点、时间、环境状况
2. **目击者**：有没有其他人看到了什么？他们的反应是什么？这些人会怎么做？
3. **角色状态**：主角和重要角色现在的位置、伤情、情绪
4. **遗留物品**：尸体、武器、血迹、证据等需要处理的东西
5. **未完成事件**：正在发生但没结束的事、承诺要做的事
6. **信息差**：谁知道什么、谁不知道什么
7. **悬念/钩子**：本章结尾的悬念是什么
8. **任何其他重要细节**：你认为下一章必须考虑的任何信息

【重要】：请特别注意那些容易被忽略但会导致逻辑漏洞的细节！
比如：有围观群众却假装没人看到、角色明明受伤了却突然生龙活虎、时间地点突然跳跃等。

【写作要求】
1. 只保留事实、状态、位置、数量、因果、承诺、未完成事项。
2. 禁止复述原文修辞，禁止保留氛围词、情绪渲染、镜头语言、比喻和文学化表达。
3. 禁止使用“阴冷”“死寂”“压抑”“诡异”“毛骨悚然”等风格词，除非它本身是剧情规则或角色对白中的必要事实。
4. 输出要像制作组交接清单，不像小说摘要。

请用简洁清晰的条目列出，不要遗漏任何关键信息。"""

        try:
            result = await self.ai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500
            )
            return result.strip() if result else ""
        except Exception as e:
            print(f"[连续性摘要] 生成失败: {e}")
            return ""

    async def _create_character_files_from_outline(self, volume: int, outline_content: str) -> None:
        """从卷大纲中提取新元素（角色/宝物/功法/势力/地点），创建基础档案"""
        if not self.ai_service:
            return
        
        # 读取现有角色表，避免重复创建
        character_roster = ""
        character_file = self.project_root / "设定集" / "角色库" / "活跃角色.md"
        if character_file.exists():
            character_roster = self._read_file(character_file)
        budgets = self._get_context_budgets("outline_entity_extract")
        roster_for_prompt = self._truncate_text(
            character_roster,
            budgets.get("roster", 1800),
            keep_tail=True,
        ) if character_roster else "（无）"
        outline_for_prompt = self._compress_outline_for_prompt(
            outline_content,
            budgets.get("outline", 8000),
        ) if outline_content else "（无）"
        style_bundle, normalized_genre, normalized_substyle = self._build_project_stage_style_bundle(
            stage="卷纲实体抽取",
            genre_style_chars=500,
            genre_examples_chars=0,
            substyle_examples_chars=0,
        )
        substyle_display = normalized_substyle or "默认子风格"
        style_section = f"【当前阶段题材协议】\n{style_bundle}\n\n" if style_bundle else ""
        
        prompt = f"""{style_section}你是小说世界观档案管理助手。请从第{volume}卷大纲中提取**新登场的重要元素**。

【题材】
{normalized_genre} / {substyle_display}

【现有角色（不要重复创建）】
{roster_for_prompt}

【第{volume}卷大纲】
{outline_for_prompt}

请提取本卷**新登场**的重要元素（排除主角和已有角色），输出 JSON 格式：
```json
{{
  "characters": [
    {{"name": "角色名", "identity": "身份", "first_chapter": 123, "relation": "与主角关系", "description": "描述"}}
  ],
  "treasures": [
    {{"name": "宝物名", "tier": "品级", "effect": "效果", "owner": "持有者"}}
  ],
  "techniques": [
    {{"name": "功法名", "tier": "等级", "effect": "效果", "practitioner": "修炼者"}}
  ],
  "organizations": [
    {{"name": "势力名", "type": "类型", "strength": "实力", "relation": "与主角关系"}}
  ],
  "locations": [
    {{"name": "地点名", "type": "类型", "features": "特点"}}
  ]
}}
```

        如果某类没有新元素，输出空数组。只输出 JSON，不要其他内容。"""

        try:
            data = await self._chat_json_with_retry(
                prompt,
                temperature=0.3,
                max_tokens=3200,
                retries=2,
            )
            if not data:
                print(f"[世界观系统] 第{volume}卷解析失败：JSON 解析失败（已重试）")
                return

            def list_of_dict(v: Any) -> List[Dict[str, Any]]:
                if not isinstance(v, list):
                    return []
                return [x for x in v if isinstance(x, dict)]

            characters = list_of_dict(data.get("characters"))
            treasures = list_of_dict(data.get("treasures"))
            techniques = list_of_dict(data.get("techniques"))
            organizations = list_of_dict(data.get("organizations"))
            locations = list_of_dict(data.get("locations"))

            print(
                f"[世界观系统] 第{volume}卷抽取结果:"
                f" 角色{len(characters)} 宝物{len(treasures)} 功法{len(techniques)}"
                f" 势力{len(organizations)} 地点{len(locations)}"
            )

            settings_dir = self.project_root / "设定集"
            created_count = 0
            
            # 创建角色档案
            if characters:
                char_lib = settings_dir / "角色库"
                (char_lib / "主要角色").mkdir(parents=True, exist_ok=True)
                (char_lib / "次要角色").mkdir(parents=True, exist_ok=True)
                (char_lib / "反派角色").mkdir(parents=True, exist_ok=True)
                
                for char in characters:
                    name = self._normalize_entity_name(char.get("name", ""))
                    if not name:
                        continue
                    existing_char_file = self._find_character_file_by_name(name)
                    if existing_char_file:
                        char["name"] = existing_char_file.stem
                        continue
                    identity = self._safe_text(char.get("identity", ""))
                    char_dir = char_lib / self._infer_character_category(identity=identity)
                    
                    char_file = char_dir / f"{name}.md"
                    if char_file.exists():
                        continue
                    char["name"] = name
                    first_chapter = self._safe_text(char.get("first_chapter", "")).strip()
                    if not first_chapter.isdigit():
                        first_chapter = str(volume)
                    content = f"""# {name}

## 基本信息
- **身份**：{identity or "未知"}
- **首次出场**：第{first_chapter}章
- **当前境界**：{self._safe_text(char.get("realm", "未知"))}
- **当前状态**：存活
- **当前地点**：{self._safe_text(char.get("location", "未知"))}
- **最后更新章节**：第{first_chapter}章

## 与主角关系
{self._safe_text(char.get("relation", "待补充"))}

## 外貌/性格
{self._safe_text(char.get("description", "待补充"))}

---
*档案创建于第{volume}卷大纲生成时*
"""
                    char_file.write_text(content, encoding="utf-8")
                    created_count += 1
                    print(f"[世界观系统] 创建角色: {name}.md")
            
            # 创建宝物档案
            if treasures:
                lib = settings_dir / "宝物库"
                lib.mkdir(parents=True, exist_ok=True)
                for item in treasures:
                    name = self._normalize_entity_name(item.get("name", ""))
                    if not name:
                        continue
                    if self._find_entity_file_in_dir(lib, name):
                        continue
                    file_path = lib / f"{name}.md"
                    content = f"""# {name}

## 基本信息
- **品级**：{self._safe_text(item.get("tier", "未知"))}
- **首次出现**：第{volume}卷
- **持有者**：{self._safe_text(item.get("owner", "未知"))}

## 效果/用途
{self._safe_text(item.get("effect", "待补充"))}

---
*档案创建于第{volume}卷大纲生成时*
"""
                    file_path.write_text(content, encoding="utf-8")
                    created_count += 1
                    print(f"[世界观系统] 创建宝物: {name}.md")
            
            # 创建功法档案
            if techniques:
                lib = settings_dir / "功法库"
                lib.mkdir(parents=True, exist_ok=True)
                for item in techniques:
                    name = self._normalize_entity_name(item.get("name", ""))
                    if not name:
                        continue
                    if self._find_entity_file_in_dir(lib, name):
                        continue
                    file_path = lib / f"{name}.md"
                    content = f"""# {name}

## 基本信息
- **等级**：{self._safe_text(item.get("tier", "未知"))}
- **首次出现**：第{volume}卷
- **修炼者**：{self._safe_text(item.get("practitioner", "未知"))}

## 效果/特点
{self._safe_text(item.get("effect", "待补充"))}

---
*档案创建于第{volume}卷大纲生成时*
"""
                    file_path.write_text(content, encoding="utf-8")
                    created_count += 1
                    print(f"[世界观系统] 创建功法: {name}.md")
            
            # 创建势力档案
            if organizations:
                lib = settings_dir / "势力库"
                lib.mkdir(parents=True, exist_ok=True)
                for item in organizations:
                    name = self._normalize_entity_name(item.get("name", ""))
                    if not name:
                        continue
                    if self._find_entity_file_in_dir(lib, name):
                        continue
                    file_path = lib / f"{name}.md"
                    content = f"""# {name}

## 基本信息
- **类型**：{self._safe_text(item.get("type", "未知"))}
- **实力等级**：{self._safe_text(item.get("strength", "未知"))}
- **首次出现**：第{volume}卷

## 与主角关系
{self._safe_text(item.get("relation", "未知"))}

---
*档案创建于第{volume}卷大纲生成时*
"""
                    file_path.write_text(content, encoding="utf-8")
                    created_count += 1
                    print(f"[世界观系统] 创建势力: {name}.md")
            
            # 创建地点档案
            if locations:
                lib = settings_dir / "地点库"
                lib.mkdir(parents=True, exist_ok=True)
                for item in locations:
                    name = self._normalize_entity_name(item.get("name", ""))
                    if not name:
                        continue
                    if self._find_entity_file_in_dir(lib, name):
                        continue
                    file_path = lib / f"{name}.md"
                    content = f"""# {name}

## 基本信息
- **类型**：{self._safe_text(item.get("type", "未知"))}
- **首次出现**：第{volume}卷

## 特点
{self._safe_text(item.get("features", "待补充"))}

---
*档案创建于第{volume}卷大纲生成时*
"""
                    file_path.write_text(content, encoding="utf-8")
                    created_count += 1
                    print(f"[世界观系统] 创建地点: {name}.md")
            
            # 更新活跃角色表
            if characters:
                await self._update_roster_from_new_chars(volume, characters)

            # 规则兜底补建
            backfill_count = self._ensure_character_profiles_from_roster(chapter_hint=volume)
            if backfill_count > 0:
                print(f"[世界观系统] 第{volume}卷规则补建角色档案 {backfill_count} 个")
            
            if created_count > 0:
                print(f"[世界观系统] 第{volume}卷共创建 {created_count} 个档案")
            else:
                print(f"[世界观系统] 第{volume}卷无新增元素")
            
        except Exception as e:
            print(f"[世界观系统] 创建档案失败: {e}")

    async def _update_roster_from_new_chars(self, volume: int, characters: list) -> None:
        """将新角色添加到活跃角色表"""
        character_file = self.project_root / "设定集" / "角色库" / "活跃角色.md"
        if not character_file.exists():
            return
        
        roster = self._read_file(character_file)
        existing_keys = {self._name_key(e["name"]) for e in self._extract_roster_entries(roster)}
        
        # 在适当位置添加新角色
        new_entries = []
        for char in characters:
            name = self._normalize_entity_name(char.get("name", ""))
            identity = self._safe_text(char.get("identity", ""))
            chapter = self._safe_text(char.get("first_chapter", ""))
            if not name:
                continue

            existing = self._find_character_file_by_name(name)
            canonical_name = existing.stem if existing else name
            key = self._name_key(canonical_name)
            if key in existing_keys:
                continue
            existing_keys.add(key)

            chapter_text = chapter if chapter.isdigit() else str(volume)
            new_entries.append(f"- **{canonical_name}**｜{identity}｜第{chapter_text}章登场")
        
        if new_entries:
            # 在已下线之前插入
            if "## 已下线" in roster:
                insert_text = "\n## 本卷新角色（待分类）\n" + "\n".join(new_entries) + "\n\n"
                roster = roster.replace("## 已下线", insert_text + "## 已下线")
            else:
                roster += "\n## 本卷新角色（待分类）\n" + "\n".join(new_entries) + "\n"
            
            character_file.write_text(roster, encoding="utf-8")
