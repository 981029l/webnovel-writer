"""题材写手 Agent（方案 B）— 侦查阶段循环控制器。

架构：两段式
  1. 侦查阶段（本模块）：题材专属写手用 function calling 自主查资料，
     多轮循环（上限 MAX_ROUNDS），产出【补充资料】文本块；
  2. 写作阶段（skill_executor 现有流式路径）：把补充资料注入写作 prompt，
     走原有 chat_stream 流式产出正文——前端体验不变。

降级策略（永不阻塞写作）：
  - 供应商不支持 tools（ToolsUnsupportedError）→ 返回空资料，照常写作；
  - 侦查阶段任意异常/超时 → 返回已收集的部分资料，照常写作；
  - agent 模式开关关闭 → 完全跳过本模块。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from services.ai_service import AIService, ToolsUnsupportedError
from services.writer_tools import WriterTools, TOOL_SCHEMAS
from services.genre_catalog import canonical_genre_id

MAX_ROUNDS = 3          # 最多侦查轮数
MAX_TOOL_CALLS = 8      # 全程最多工具调用次数
RESEARCH_TIMEOUT = 180  # 侦查阶段总超时（秒）

# 工具名 → 前端展示文案
TOOL_LABELS = {
    "query_settings": "查阅设定集",
    "query_character": "查阅角色档案",
    "query_foreshadow": "追查前文伏笔",
    "read_chapter": "回看前文章节",
    "query_timeline": "梳理剧情时间线",
}


def _build_research_system_prompt(genre: str, chapter: int) -> str:
    normalized = canonical_genre_id(genre)
    return f"""你是《{normalized}》题材的专属写手，正在为第{chapter}章做写前调研。

你的任务**不是写作**，而是判断：为了把本章写准、写对、不与前文矛盾，你还缺哪些信息。

规则：
1. 只查真正需要的：本章大纲涉及的旧伏笔、久未出场的配角、拿不准的设定细则、需要衔接的前文细节。
2. 已经在上下文里给你的信息（大纲、主角状态、上一章结尾）不要重复查。
3. 每轮最多调用 3 个工具；信息足够时，直接回复"调研完成"并简述你确认了什么，不要再调用工具。
4. 最多 {MAX_ROUNDS} 轮，请高效。"""


class GenreWriterAgent:
    """题材写手 Agent 的侦查阶段执行器。"""

    def __init__(self, ai_service: AIService, project_root: Path, rag_adapter: Any = None):
        self.ai = ai_service
        self.tools = WriterTools(project_root, rag_adapter=rag_adapter)

    async def research_stream(
        self,
        genre: str,
        chapter: int,
        chapter_outline: str,
        known_context_brief: str = "",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """执行侦查循环。

        产出事件流（dict）：
          {"type": "agent_step", "action": str, "detail": str}   — 过程事件（给前端展示）
          {"type": "agent_done", "materials": str, "rounds": int, "calls": int}
                                                                  — 结束事件，materials 为补充资料块
        """
        materials: List[str] = []
        calls_used = 0
        rounds_used = 0

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _build_research_system_prompt(genre, chapter)},
            {
                "role": "user",
                "content": (
                    f"【第{chapter}章大纲】\n{chapter_outline or '（无）'}\n\n"
                    f"【已提供给写手的上下文简述】\n{known_context_brief or '（基础上下文：主角状态、上一章结尾、近3章摘要）'}\n\n"
                    "请判断还需要查什么。不需要就直接回复调研完成。"
                ),
            },
        ]

        try:
            async with asyncio.timeout(RESEARCH_TIMEOUT):
                for round_no in range(1, MAX_ROUNDS + 1):
                    rounds_used = round_no
                    response = await self.ai.chat_with_tools(
                        messages, TOOL_SCHEMAS, temperature=0.2, max_tokens=1200
                    )
                    tool_calls = response.get("tool_calls") or []

                    if not tool_calls:
                        # 模型认为信息足够
                        summary = (response.get("content") or "").strip()
                        if summary:
                            yield {"type": "agent_step", "action": "调研完成", "detail": summary[:120]}
                        break

                    # 记录 assistant 的 tool_calls 消息（OpenAI 协议要求回传）
                    messages.append({
                        "role": "assistant",
                        "content": response.get("content") or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                                },
                            }
                            for tc in tool_calls
                        ],
                    })

                    for tc in tool_calls[:3]:  # 每轮上限 3 个
                        if calls_used >= MAX_TOOL_CALLS:
                            break
                        calls_used += 1
                        label = TOOL_LABELS.get(tc["name"], tc["name"])
                        arg_brief = "、".join(str(v) for v in tc["arguments"].values())[:60]
                        yield {"type": "agent_step", "action": label, "detail": arg_brief}

                        result = await self.tools.execute(tc["name"], tc["arguments"])
                        materials.append(f"### {label}（{arg_brief}）\n{result}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        })

                    if calls_used >= MAX_TOOL_CALLS:
                        yield {"type": "agent_step", "action": "调研完成", "detail": "已达工具调用上限"}
                        break

        except ToolsUnsupportedError:
            yield {
                "type": "agent_step",
                "action": "降级",
                "detail": "当前模型不支持工具调用，使用标准模式写作",
            }
        except (asyncio.TimeoutError, TimeoutError):
            yield {"type": "agent_step", "action": "降级", "detail": "调研超时，携带已获资料继续写作"}
        except Exception as e:  # noqa: BLE001 — 侦查失败绝不阻塞写作
            yield {"type": "agent_step", "action": "降级", "detail": f"调研异常（{str(e)[:80]}），标准模式继续"}

        materials_block = ""
        if materials:
            materials_block = (
                "【写前调研资料（写手自主查阅，写作时必须与之保持一致）】\n"
                + "\n\n".join(materials)
            )

        yield {
            "type": "agent_done",
            "materials": materials_block,
            "rounds": rounds_used,
            "calls": calls_used,
        }
