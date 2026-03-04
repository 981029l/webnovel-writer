# Copyright (c) 2026 左岚. All rights reserved.
"""AI 服务模块 - 对接 OpenAI 兼容 API"""

import os
import re
import json
import httpx
from typing import Optional, List, Dict, Any
from pathlib import Path

from services.projects_manager import GLOBAL_CONFIG_DIR

# 默认 AI API 配置
DEFAULT_AI_BASE_URL = "http://jiushi.online/"
DEFAULT_AI_API_KEY = "your-api-key-3"
DEFAULT_AI_MODEL = "gpt-5.2"


class AIService:
    """AI 服务封装"""

    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or os.getenv("AI_BASE_URL", DEFAULT_AI_BASE_URL)
        self.api_key = api_key or os.getenv("AI_API_KEY", DEFAULT_AI_API_KEY)
        self.model = model or os.getenv("AI_MODEL", DEFAULT_AI_MODEL)
        self.timeout = 1800  # 3分钟超时

    def _debug_enabled(self) -> bool:
        flag = os.getenv("WEBNOVEL_DEBUG", "").strip().lower()
        return flag in {"1", "true", "yes", "on", "debug"}

    def _debug(self, message: str) -> None:
        if self._debug_enabled():
            print(message)

    async def chat(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 4000, response_format: str = None) -> str:
        """发送聊天请求 - 使用 aiohttp 提升稳定性"""
        import aiohttp
        
        # 智能处理 URL
        base_url = self.base_url.rstrip("/")
        if base_url.endswith("/v1"):
            url = f"{base_url}/chat/completions"
        else:
            url = f"{base_url}/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        # 添加 response_format 参数（强制 JSON 输出）
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        self._debug(f"Applying AI Request: {url} (Model: {self.model})")
        
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 每次重试都创建新的 connector 和 session，确保连接干净
                connector = aiohttp.TCPConnector(force_close=True, enable_cleanup_closed=True)
                timeout = aiohttp.ClientTimeout(total=self.timeout, connect=30, sock_read=self.timeout)
                # trust_env=False 忽略系统代理，避免 localhost 连接问题
                async with aiohttp.ClientSession(connector=connector, timeout=timeout, trust_env=False) as session:
                    async with session.post(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data["choices"][0]["message"]["content"]
                        else:
                            error_text = await response.text()
                            print(f"AI Error {response.status}: {error_text[:200]}")
                            raise Exception(f"AI API returned {response.status}: {error_text[:100]}")
            except Exception as e:
                last_error = e
                print(f"AI Request Failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(3 + attempt * 2)  # 递增等待：3s, 5s
                    continue
                raise last_error


    async def chat_stream(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 4000):
        """流式发送聊天请求"""
        import aiohttp
        
        base_url = self.base_url.rstrip("/")
        url = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/event-stream"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        self._debug(f"Applying AI Stream Request: {url} (Model: {self.model})")
        # 调试：打印请求消息的长度和摘要
        try:
            msg_preview = json.dumps(messages, ensure_ascii=False)[:500]
            self._debug(f"Request Messages Preview: {msg_preview}...")
            self._debug(f"Total Messages count: {len(messages)}")
        except:
            pass
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                connector = aiohttp.TCPConnector(force_close=True, enable_cleanup_closed=True)
                timeout = aiohttp.ClientTimeout(total=self.timeout, connect=30, sock_read=300)
                # trust_env=False 忽略系统代理
                async with aiohttp.ClientSession(connector=connector, timeout=timeout, trust_env=False) as session:
                    async with session.post(url, json=payload, headers=headers) as response:
                        self._debug(f"AI Stream Response Status: {response.status}")
                        self._debug(f"AI Stream Content-Type: {response.headers.get('Content-Type', 'unknown')}")
                        
                        if response.status != 200:
                            error_text = await response.text()
                            print(f"AI Stream Error: {error_text[:200]}")
                            yield f"[ERROR] AI API returned {response.status}: {error_text[:100]}"
                            return

                        content_type = response.headers.get('Content-Type', '')
                        
                        # 如果返回的是 JSON 而不是 SSE，直接解析
                        if 'application/json' in content_type:
                            self._debug("AI returned JSON instead of SSE, parsing as single response")
                            raw_text = await response.text()
                            try:
                                data = json.loads(raw_text)
                                if "choices" in data and len(data["choices"]) > 0:
                                    content = data["choices"][0].get("message", {}).get("content", "")
                                    if content:
                                        yield content
                                        self._debug(f"AI JSON response length: {len(content)}")
                                        return
                            except json.JSONDecodeError as e:
                                print(f"Failed to parse JSON response: {e}")
                                yield f"[ERROR] Failed to parse AI response"
                                return
                        
                        # SSE 流式处理 - 使用 buffer 累积并按行分割
                        chunk_count = 0
                        buffer = ""
                        self._debug("Starting SSE stream reading...")
                        
                        async for chunk in response.content.iter_any():
                            raw_chunk = chunk.decode('utf-8', errors='ignore')
                            # 调试：打印原始数据块的前50个字符
                            self._debug(f"Raw chunk received ({len(raw_chunk)}): {raw_chunk[:100]}...")
                            buffer += raw_chunk
                            
                            # 按行分割处理
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                line = line.strip()
                                
                                if not line:
                                    continue
                                if line == "data: [DONE]":
                                    self._debug(f"AI Stream completed, total chunks: {chunk_count}")
                                    return
                                
                                if line.startswith("data: "):
                                    try:
                                        data = json.loads(line[6:])
                                        if "choices" in data and len(data["choices"]) > 0:
                                            delta = data["choices"][0].get("delta", {})
                                            if "content" in delta:
                                                chunk_count += 1
                                                if chunk_count == 1:
                                                    self._debug("First SSE chunk received!")
                                                yield delta["content"]
                                    except json.JSONDecodeError:
                                        continue
                        
                        self._debug(f"AI Stream ended, total chunks: {chunk_count}")
                        return
            except Exception as e:
                print(f"AI Stream Request Failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(3 + attempt * 2)
                    continue
                yield f"[ERROR] {str(e)}"




    async def list_models(self) -> List[str]:
        """获取可用模型列表"""
        base_url = self.base_url.rstrip("/")
        if base_url.endswith("/v1"):
            url = f"{base_url}/models"
        else:
            url = f"{base_url}/v1/models"
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            # trust_env=False 防止受到系统代理影响 (解决 localhost 502 问题)
            async with httpx.AsyncClient(timeout=10, follow_redirects=True, http2=False, trust_env=False) as client:
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    print(f"Error fetching models: {response.status_code} - {response.text}")
                    return [self.model]
                
                data = response.json()
                if "data" in data and isinstance(data["data"], list):
                    return [m["id"] for m in data["data"]]
                return [self.model]
        except Exception as e:
            print(f"Error fetching models from {url}: {e}")
            return [self.model, "gpt-3.5-turbo", "gpt-4"]

    async def generate_outline(self, genre: str, premise: str, volumes: int = 1) -> str:
        """生成大纲"""
        system_prompt = """你是一位专业的网文大纲策划师。请根据用户提供的题材和设定，生成详细的小说大纲。

大纲格式要求：
1. 使用 Markdown 格式
2. 包含故事概要、主要角色、卷纲规划
3. 每卷包含 20-30 章的详细规划
4. 每章包含：标题、目标、爽点设计、Strand类型(Quest/Fire/Constellation)"""

        user_prompt = f"""题材：{genre}
核心设定：{premise}
规划卷数：{volumes} 卷

请生成完整的小说大纲。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return await self.chat(messages, temperature=0.8, max_tokens=8000)

    async def write_chapter(
        self,
        chapter_num: int,
        chapter_outline: str,
        previous_summary: str = "",
        characters: List[str] = None,
        settings: str = "",
        word_count: int = 4000
    ) -> str:
        """AI 写作章节"""
        system_prompt = f"""你是一位专业的网文作者。请根据大纲和上下文，创作精彩的章节内容。

写作要求：
1. 字数：{word_count} 字左右
2. 风格：节奏紧凑、对话生动、描写细腻
3. 结构：开头引人入胜、中间层层推进、结尾留有悬念
4. 遵循大纲设定，不要擅自发挥
5. 保持与前文的一致性"""

        context = f"""## 第 {chapter_num} 章大纲
{chapter_outline}

## 前情摘要
{previous_summary or '（这是第一章，无前情）'}

## 出场角色
{', '.join(characters) if characters else '（根据大纲安排）'}

## 世界观设定
{settings or '（使用默认设定）'}

请开始创作第 {chapter_num} 章正文："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context}
        ]

        return await self.chat(messages, temperature=0.7, max_tokens=8000)

    async def review_chapter(self, content: str, previous_context: str = "", chapter_outline: str = "") -> Dict[str, Any]:
        """审查章节质量（含上下文重复性检查与大纲一致性检查）"""
        system_prompt = """你是一位“找茬”专家的网文主编，专门负责揪出正文与大纲不符的错误。你的审核标准极度严苛，绝不容忍任何设定偏差。

        【审核核心任务】
        请对比【本章大纲】与【正文内容】，重点检查以下几点：
        1. **专有名词一致性**：大纲里的宗门、地名、人名、物品名，正文必须完全一致。
           - 例子：大纲写“落云宗”，正文写“流云宗” -> ❌ 严重错误！
           - 例子：大纲写“万剑窟”，正文写“矿山” -> ❌ 严重错误！
        2. **核心剧情一致性**：大纲规定的核心冲突起因、经过、结果，正文是否篡改？

        【评分规则】
        1. **Consistency (一致性)**：初始 100 分。发现 1 个名词错误扣 20 分；发现 1 个剧情篡改扣 30 分。必须严格！
        2. **High Point (爽点)**：评估剧情是否能调动情绪（期待感、震惊、满足感）。无爽点=0-40，平淡=41-60，有亮点=61-80，极爽=81-100。
        3. **Pacing (节奏)**：评估剧情推进速度。太拖沓或太赶=0-50，正常=60-80，起伏有致=81-100。
        4. **OOC (人设)**：人物行为是否符合性格。严重崩坏=0-50，符合=60-100。
        5. **Continuity (连贯性)**：场景切换是否自然。

        【返回格式（JSON）】
        {
          "comparison_log": {
             "outline_entities": ["大纲名词1", "大纲名词2"],
             "content_entities": ["正文名词1", "正文名词2"],
             "mismatch_found": true/false
          },
          "scores": {
              "high_point": 85, 
              "consistency": 95, 
              "pacing": 70, 
              "ooc": 90, 
              "continuity": 88
          },
          "issues": [
             "❌ 宗门名称错误：大纲为[落云宗]，正文写成了[流云宗]",
             "⚠️ 节奏建议：开篇说明文略多"
          ],
          "suggestions": ["建议1", "建议2"],
          "summary": "简短评价"
        }"""

        user_content = f"请审查以下章节：\n\n{content}"
        
        context_info = []
        if chapter_outline:
            context_info.append(f"【本章大纲（用于检查剧情一致性）】\n{chapter_outline}")
        if previous_context:
            context_info.append(f"【上一章结尾（用于检查衔接与重复）】\n{previous_context}\n\n【特别注意】请仔细检查新章节开头是否机械复述了上一章结尾。")
            
        if context_info:
            user_content = "\n\n".join(context_info) + "\n\n" + user_content

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        result = await self.chat(messages, temperature=0.3, max_tokens=2000)

        # 尝试解析 JSON
        try:
            # 提取 JSON 部分
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            return json.loads(result.strip())
        except Exception:
            return {
                "scores": {"high_point": 0, "consistency": 0, "pacing": 0, "ooc": 0, "continuity": 0},
                "issues": ["无法解析审查结果"],
                "suggestions": [],
                "summary": result
            }

    async def generate_ending_plan(self, outline: str, current_progress: str, remaining_chapters: int) -> dict:
        """生成收尾规划"""
        prompt = f"""你是一位拥有20年经验的金牌网文主编，擅长为小说设计精彩的收尾大结局。
        
        【任务】
        请根据提供的小说总纲和当前进度，为这本小说规划最后的 {remaining_chapters} 章收尾大纲。
        
        【要求】
        1. **伏笔回收**：必须列出通过这几章需要回收的关键伏笔。
        2. **节奏紧凑**：每一章都必须有明确的推进目标，最后高潮迭起。
        3. **结局圆满**：符合网文读者的期待，给出一个合理且精彩的结局。
        4. **分章规划**：生成 {remaining_chapters} 个章节的详细大纲。
        
        【现有信息】
        总纲：
        {outline}
        
        当前进度/状态：
        {current_progress}
        
        【输出格式（JSON）】
        {{
            "ending_straregy": "收尾策略简述（200字内）",
            "chapters": [
                {{
                    "chapter_num": "自动推算的章节号",
                    "title": "章节标题",
                    "summary": "章节剧情概要（100字+）",
                    "purpose": "本章核心作用（如：揭示真相、最终决战、情感升华）"
                }},
                ...
            ]
        }}
        """
        
        try:
            response = await self.chat(
                messages=[
                    {"role": "system", "content": "你是一位专业的网文主编策划。请用 JSON 格式回复。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000,
                response_format="json_object"
            )
            data = json.loads(response)
            return {"success": True, "plan": data}
        except Exception as e:
            return {"success": False, "error": f"AI 规划失败: {str(e)}"}

    async def generate_titles(self, genre: str, outline: str) -> List[str]:
        """根据大纲生成书名"""
        system_prompt = f"""你是一位深谙网文市场规律的金牌主编，擅长打造爆款书名。
请根据大纲，为这部{genre}小说起 8 个极具吸引力、充满噱头和点击欲望的书名。

【起名核心法则】
1. **突出核心卖点**：必须一秒展示金手指、极致反差或核心爽点。
2. **拒绝平庸**：不要“xx传”、“xx记”这种古早文名，要“开局...”、“我...”、夸张对比。
3. **情绪调动**：利用震惊、好奇、贪婪（金手指）、优越感（无敌）等情绪。
4. **流派定制**：
   - 修仙/玄幻：要霸气宏大或极致苟道/稳健（如《我有一剑...》《开局签到...》）。
   - 都市/系统：要直白爽快，突出身份反差或系统功能（如《让你...没让你...》《校花...》）。
   - 悬疑/惊悚：要细思恐极或规则怪谈感。

【输出要求】
1. 只输出书名，每行一个。
2. 不要有任何解释或序号。
3. 必须生成 8 个。
4. **字数限制**：严格控制在 15 个字以内，短小精悍。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"【小说大纲】\n{outline[:3000]}"}
        ]

        content = await self.chat(messages, temperature=0.8, max_tokens=200)
        
        # 清洗数据
        titles = []
        for line in content.split("\n"):
            line = line.strip()
            # 去除序号 (1. xxx)
            line = re.sub(r"^\d+[\.、\s]*", "", line)
            # 去除书名号
            line = line.replace("《", "").replace("》", "")
            if line:
                titles.append(line)
        
        return titles[:8]

    async def polish_chapter(self, content: str, suggestions: List[str] = None) -> str:
        """AI 润色章节"""
        system_prompt = """你是一位专业的网文主编。请根据改进建议，对用户提供的章节内容进行润色和重写。

要求：
1. **严格遵循改进建议**：针对性地解决提出的问题（如节奏、爽点、人设等）。
2. **提升文笔**：优化描写，增强代入感，使用 show-don't-tell 手法。
3. **保持原意**：不要随意更改核心剧情走向，除非建议中明确要求。
4. **输出完整正文**：直接输出润色后的内容，不要包含“好的”、“这是润色后的版本”等废话。"""

        user_prompt = f"""请润色以下章节内容：

【改进建议】
{chr(10).join([f"- {s}" for s in suggestions]) if suggestions else "- 请全面提升文笔，增强画面感和代入感。"}

【原文】
{content}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return await self.chat(messages, temperature=0.7, max_tokens=8000)

    async def generate_chapter_summary(self, content: str) -> str:
        """生成章节摘要"""
        messages = [
            {"role": "system", "content": "请用 100-200 字概括以下章节的主要情节，用于后续章节的上下文参考。"},
            {"role": "user", "content": content}
        ]
        return await self.chat(messages, temperature=0.3, max_tokens=500)



CONFIG_FILE = GLOBAL_CONFIG_DIR / "ai_config.json"

def _load_config_from_file() -> Dict[str, str]:
    """从文件加载 AI 配置"""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: Failed to load AI config: {e}")
    return {}

def _save_config_to_file(config: Dict[str, str]):
    """保存 AI 配置到文件"""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"Error saving AI config: {e}")

# 全局实例
_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        # 1. 尝试从文件加载
        file_config = _load_config_from_file()
        
        # 2. 环境变量覆盖（可选）
        base_url = file_config.get("base_url") or os.getenv("AI_BASE_URL", DEFAULT_AI_BASE_URL)
        api_key = file_config.get("api_key") or os.getenv("AI_API_KEY", DEFAULT_AI_API_KEY)
        model = file_config.get("model") or os.getenv("AI_MODEL", DEFAULT_AI_MODEL)
        
        _ai_service = AIService(base_url, api_key, model)
    return _ai_service


def configure_ai_service(base_url: str = None, api_key: str = None, model: str = None):
    global _ai_service
    
    # 保存到文件
    config_data = {
        "base_url": base_url or DEFAULT_AI_BASE_URL,
        "api_key": api_key or "",
        "model": model or DEFAULT_AI_MODEL
    }
    _save_config_to_file(config_data)
    
    # 更新内存实例
    _ai_service = AIService(base_url, api_key, model)
