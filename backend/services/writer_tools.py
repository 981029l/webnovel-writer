"""写手 Agent 工具集 (方案 B)。

把已有的数据链（设定集 / 正文 / state.json / RAG 向量库）包装成 OpenAI 兼容
function-calling 工具，供题材写手 Agent 在写作前/写作中按需调用。

设计原则：
- 每个工具都是只读、快速、无副作用；
- 工具执行永不抛出到 agent 循环外，出错时返回可读的错误串（模型能理解并继续）；
- 不依赖具体 AI 供应商，纯本地数据访问。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 工具 JSON Schema（发给模型的 tools 定义）
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_settings",
            "description": "查询本书的世界观、力量体系、金手指等设定细则。当你不确定某个设定、术语、规则或体系时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "要查询的设定关键词，如'灵气等级''金手指规则''某个地名'",
                    }
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_character",
            "description": "查询某个角色的人物卡、当前境界/状态、性格与最近动向。写到配角登场、需要确认其设定或口吻时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "角色名字"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_foreshadow",
            "description": "查询与关键词相关的伏笔：它在前文何处埋下、原文是什么、是否已回收。写到可能呼应前文伏笔时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "伏笔相关关键词，如某个物件、人物、谜团"}
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_chapter",
            "description": "读取指定章节的正文内容（可只取开头或结尾若干字），用于确认前文细节、衔接上一章。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter": {"type": "integer", "description": "章节号"},
                    "position": {
                        "type": "string",
                        "enum": ["head", "tail", "full"],
                        "description": "取开头(head)、结尾(tail)还是全文(full)，默认 tail",
                    },
                },
                "required": ["chapter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_timeline",
            "description": "拉取某一段章节区间的剧情摘要，用于把握时间线、避免与前文矛盾。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "integer", "description": "起始章节号"},
                    "end": {"type": "integer", "description": "结束章节号"},
                },
                "required": ["start", "end"],
            },
        },
    },
]


class WriterTools:
    """写手工具集执行器。绑定到某个项目根目录。"""

    def __init__(self, project_root: Path, rag_adapter: Any = None, max_result_chars: int = 1500):
        self.project_root = Path(project_root)
        self.settings_dir = self.project_root / "设定集"
        self.text_dir = self.project_root / "正文"
        self.rag_adapter = rag_adapter
        self.max_result_chars = max_result_chars

    # ---- 分发入口 -------------------------------------------------------

    async def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """执行一个工具调用，返回给模型的文本结果。永不抛出。"""
        try:
            handler = {
                "query_settings": self._query_settings,
                "query_character": self._query_character,
                "query_foreshadow": self._query_foreshadow,
                "read_chapter": self._read_chapter,
                "query_timeline": self._query_timeline,
            }.get(name)
            if handler is None:
                return f"[工具错误] 未知工具: {name}"
            result = await handler(arguments or {})
            return self._truncate(result) if result else "（未查到相关内容）"
        except Exception as e:  # noqa: BLE001 - 工具错误必须软着陆
            return f"[工具错误] {name} 执行失败: {e}"

    # ---- 具体工具 -------------------------------------------------------

    async def _query_settings(self, args: Dict[str, Any]) -> str:
        keyword = str(args.get("keyword", "")).strip()
        if not keyword:
            return "（未提供关键词）"

        hits: List[str] = []
        # 1) 直接在设定集 md 里找包含关键词的段落
        for md in self._iter_setting_files():
            text = self._read(md)
            if not text:
                continue
            for para in re.split(r"\n\s*\n", text):
                if keyword in para:
                    hits.append(f"【{md.stem}】{para.strip()}")
                    if len(hits) >= 4:
                        break
            if len(hits) >= 4:
                break

        # 2) RAG 兜底（若可用且直查无果）
        if not hits and self.rag_adapter is not None:
            rag_text = await self._rag_search(keyword)
            if rag_text:
                hits.append(rag_text)

        return "\n\n".join(hits) if hits else ""

    async def _query_character(self, args: Dict[str, Any]) -> str:
        name = str(args.get("name", "")).strip()
        if not name:
            return "（未提供角色名）"

        parts: List[str] = []
        # 角色库各分类目录
        char_lib = self.settings_dir / "角色库"
        if char_lib.exists():
            for md in char_lib.rglob("*.md"):
                if name in md.stem:
                    parts.append(f"【人物卡·{md.stem}】\n{self._read(md).strip()}")
                    break
        # 主角卡兜底
        if not parts:
            card = self.settings_dir / "主角卡.md"
            if card.exists() and name in self._read(card):
                parts.append(f"【主角卡】\n{self._read(card).strip()}")
        # 实时状态里与该角色相关的行
        status = self.settings_dir / "实时状态.md"
        if status.exists():
            status_hits = [
                ln.strip() for ln in self._read(status).splitlines() if name in ln
            ]
            if status_hits:
                parts.append("【实时状态】\n" + "\n".join(status_hits[:8]))

        return "\n\n".join(parts) if parts else ""

    async def _query_foreshadow(self, args: Dict[str, Any]) -> str:
        keyword = str(args.get("keyword", "")).strip()
        if not keyword:
            return "（未提供关键词）"

        parts: List[str] = []
        # 1) state.json 里的伏笔表（结构不固定，做宽松扫描）
        state = self._load_state()
        if state:
            fores = self._extract_foreshadows(state)
            for item in fores:
                blob = json.dumps(item, ensure_ascii=False)
                if keyword in blob:
                    parts.append("【伏笔记录】" + blob)
                    if len(parts) >= 4:
                        break

        # 2) RAG 在正文里找埋设原文
        if self.rag_adapter is not None:
            rag_text = await self._rag_search(keyword)
            if rag_text:
                parts.append("【前文相关片段】\n" + rag_text)

        return "\n\n".join(parts) if parts else ""

    async def _read_chapter(self, args: Dict[str, Any]) -> str:
        chapter = args.get("chapter")
        position = str(args.get("position", "tail")).strip() or "tail"
        if chapter is None:
            return "（未提供章节号）"
        try:
            chapter = int(chapter)
        except (TypeError, ValueError):
            return "（章节号无效）"

        files = list(self.text_dir.glob(f"第{chapter}章*.md")) if self.text_dir.exists() else []
        if not files:
            return f"（未找到第{chapter}章）"
        text = self._read(files[0]).strip()
        if not text:
            return f"（第{chapter}章为空）"

        span = 800
        if position == "head":
            return text[:span]
        if position == "full":
            return text
        return text[-span:]  # tail 默认

    async def _query_timeline(self, args: Dict[str, Any]) -> str:
        try:
            start = int(args.get("start"))
            end = int(args.get("end"))
        except (TypeError, ValueError):
            return "（章节区间无效）"
        if start > end:
            start, end = end, start
        end = min(end, start + 30)  # 上限保护

        cont_dir = self.text_dir / ".continuity"
        lines: List[str] = []
        for ch in range(start, end + 1):
            f = cont_dir / f"第{ch}章_状态.md"
            if f.exists():
                summary = self._read(f).strip()
                if summary:
                    lines.append(f"第{ch}章：{summary[:200]}")
        return "\n".join(lines) if lines else ""

    # ---- 内部工具 -------------------------------------------------------

    def _iter_setting_files(self):
        if not self.settings_dir.exists():
            return
        for md in sorted(self.settings_dir.glob("*.md")):
            yield md

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _load_state(self) -> Optional[Dict]:
        f = self.project_root / ".webnovel" / "state.json"
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _extract_foreshadows(self, state: Dict) -> List[Any]:
        """从 state.json 里尽量宽松地取出伏笔条目。"""
        for key in ("foreshadows", "foreshadowing", "伏笔", "pending_foreshadows"):
            val = state.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                return list(val.values())
        # 嵌套在 plot / story 下
        for container_key in ("plot", "story", "world_settings"):
            container = state.get(container_key)
            if isinstance(container, dict):
                for key in ("foreshadows", "伏笔"):
                    val = container.get(key)
                    if isinstance(val, list):
                        return val
        return []

    async def _rag_search(self, query: str) -> str:
        if self.rag_adapter is None:
            return ""
        try:
            results = await self.rag_adapter.hybrid_search(query, rerank_top_n=3)
        except Exception:
            try:
                results = self.rag_adapter.bm25_search(query, 3)
            except Exception:
                return ""
        snippets = []
        for r in (results or [])[:3]:
            content = getattr(r, "content", None) or getattr(r, "text", None) or ""
            if content:
                snippets.append(content.strip()[:400])
        return "\n---\n".join(snippets)

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_result_chars:
            return text
        return text[: self.max_result_chars] + "…（已截断）"
