# Copyright (c) 2025 左岚. All rights reserved.
"""提示词模板基底与运行时兜底。

本模块是「方案A 全模板化」的单一源头：
- ``*_BASE``：六段模板基底，含 ``{var}`` 运行时占位符与 ``%%TOKEN%%`` 题材词汇插槽。
  scripts/generate_prompt_slots.py 用桶级词表填充 ``%%TOKEN%%`` 后生成 37 个子风格包文件。
- ``DEFAULT_VOCAB``：中性词表。用它填充基底得到 ``*_FALLBACK`` 运行时兜底常量——
  当项目槽位模板意外为空时使用，保证生成链路永不静默降级、且不向非修仙题材泄漏修仙词。
- ``*_CONTRACT``：代码在渲染后追加的不可编辑契约块，保护下游解析
  （分卷正则切卷、章节号解析、实体提取 JSON 落库）不被模板编辑破坏。

运行时渲染一律使用纯 replace（skill_executor._render_slot_template），
禁止 str.format——模板含大量裸 JSON 花括号。
"""

from __future__ import annotations

import re
from typing import Dict

# ---------------------------------------------------------------------------
# 词汇插槽填充
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"%%([A-Z_]+)%%")


def fill_vocab(text: str, vocab: Dict[str, str], *, strict: bool = True) -> str:
    """把基底中的 %%TOKEN%% 替换为词表值。strict 时残留未知 token 直接报错。"""
    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1)
        if key in vocab:
            return vocab[key]
        if strict:
            raise KeyError(f"词表缺少 token: %%{key}%%")
        return match.group(0)

    return _TOKEN_RE.sub(_sub, text)


def list_tokens(text: str) -> list[str]:
    """列出基底中出现的全部 %%TOKEN%%（生成器自校验用）。"""
    return sorted(set(_TOKEN_RE.findall(text)))


# ---------------------------------------------------------------------------
# 中性默认词表（兜底与非典型题材共用；各桶按需覆盖）
# ---------------------------------------------------------------------------

DEFAULT_VOCAB: Dict[str, str] = {
    # 通用
    "NAMING_HINT": "",
    # 总纲初稿
    "SCALE_HINT": "约600-1000章体量，分为12卷",
    "MASTER_FORMAT_EXAMPLE": (
        "   ## 第X卷 《卷名》（约XX章）\n"
        "   - **核心冲突**：...\n"
        "   - **关键爽点**：...\n"
        "   - **卷末高潮**：..."
    ),
    # 总纲重写
    "VOLUME_COUNT_HINT": "建议10-12卷",
    "REWRITE_FORMAT_EXAMPLE": (
        "## 第1卷 《卷名示例》（约50-60章）\n"
        "- **预计章数**：50-60章\n"
        "- **核心冲突**：主角身处最初困境，获得核心驱动力，开始逆势翻盘\n"
        "- **关键爽点**：第一次以下克上，让轻视者付出代价\n"
        "- **卷末高潮**：击败本卷最大对手，赢得进入更大舞台的资格"
    ),
    # 分卷大纲
    "VOLUME_NUMERIC_EXAMPLE": (
        "✅ 正确示例：\n"
        "   - 【伤亡】一线战力折损约两成，仅存核心成员若干（写出具体数字）\n"
        "   - 【消耗】关键消耗品用去多少、剩余多少，写出具体数值\n"
        "   - 【收益】本章获得的资源/情报/地位变化，写出具体数值或等级\n"
        "   - 【状态】某角色重伤（伤情部位，需恢复时间）\n"
        "❌ 错误示例：\n"
        "   - \"死伤惨重\"（太模糊！必须写具体数字）\n"
        "   - \"消耗了大量资源\"（必须说明消耗了什么、多少）"
    ),
    # 大纲润色
    "POLISH_NUMERIC_EXAMPLE": (
        "- 【伤亡】xxx（写明具体人数或比例）\n"
        "- 【消耗】xxx（写明资源名与数量）\n"
        "- 【状态】xxx（如：重伤、突破、地位变化）"
    ),
    # 实体提取
    "IDENTITY_EG": "主角亲随/盟友/对手/长辈/下属等",
    "REALM_LABEL": "境界/等级",
    "REALM_DESC": "当前境界或等级（用本书力量体系的说法）",
    "LOCATION_DESC": "当前地点（用本书世界观中的地名）",
    "TIER_DESC": "品级/等级（用本书世界观的分级说法）",
    "TECH_LABEL": "功法/技能",
    "TECH_TIER_DESC": "等级（用本书世界观的分级说法）",
    "ORG_TYPE_DESC": "类型（组织/家族/国家/团体等）",
    "LOC_TYPE_DESC": "类型（城市/据点/秘地/区域等）",
    "CHANGE_EG": "如突破晋级、重伤昏迷、身份暴露",
    "RESOURCE_EG": "本书的核心资源，如货币、物资、点数",
    "UNIT_DESC": "队伍/部队名称（用正文中的称呼）",
    "EXTRACT_NUMERIC_FOCUS": (
        "1. **人员伤亡**：战斗、灾祸造成的死亡/受伤人数（正文有数字必须提取！）\n"
        "2. **核心资源**：主角方关键资源的增减数值和原因\n"
        "3. **成长数值**：主角获得或消耗的成长点数/次数/额度\n"
        "4. **战力资产变化**：队伍折损、装备损坏、消耗品用量等"
    ),
    # 连续性摘要
    "CONTINUITY_EXTRA": "-（无本题材附加条目）",
    # 题材专属大纲方法论（分卷基底内；各桶覆盖）
    "OUTLINE_METHOD_EXTRA": "",
    # 黄金三章：各桶开篇钩子示例
    "OPENING_HOOK_EG": "",
    # 辅助文件题材变体
    "COMBAT_LABEL": "战斗/冲突场面",
    "COMBAT_TYPES": (
        "【场面类型侧重】\n"
        "- 一对一：重心理博弈与来回试探；一对多：重走位战术与逐个击破；"
        "群体混战：重视角切换与阵形崩解；特殊环境：重环境利用与限制。"
    ),
    "DIALOGUE_FLAVOR": "",
    "EMOTION_FLAVOR": "",
    "SCENE_FLAVOR": "",
}


# ---------------------------------------------------------------------------
# 槽位模板基底
# ---------------------------------------------------------------------------

OUTLINE_MASTER_BASE = """请为《{title}》规划全书总纲（%%SCALE_HINT%%）。

【命名与标题语域（硬约束）】
章节标题、卷名、以及一切会写进正文世界的名词（人物/势力/功法/装置/系统词条）必须使用符合本题材世界观的语言；禁止现代职场/统计/网络词汇入名（如"数据、KPI、复盘、成本、上线"）。大纲中的策划性说明（爽点设计、数值/状态等工作栏目）不受此限。%%NAMING_HINT%%

【小说信息】
- 书名：《{title}》
- 题材：{genre}
- 子风格：{substyle}

{independent_stage_prompt}

【题材锁定】
{genre_guard}

【题材笔调校准】
{positive_style_instruction}

【子风格锁定】
{substyle_instruction}

【设定参考】
{world}
{power}
{char}

【金手指/核心驱动设定】
{gold_finger}

【用户补充设定】
{additional_info}

【题材核心节奏】
{trope_focus}
{style_guide}

【子风格示例（按当前子风格抽取）】
{substyle_examples}

【题材示例（按当前题材动态加载）】
{genre_examples}
要求：学习风格而非复写句子。

【要求】
1. 每卷必须包含：标题、预计章数（如50-80章）、核心冲突、关键爽点、卷末高潮
2. 节奏层层递进，符合{genre} / {substyle} 的爽文结构
3. 每卷标注卷级关键节点：切入点、上升段、卷高潮、回落收束
4. 跨卷伏笔用台账式标注：【伏笔F-01】埋设第X卷 / 类型（身份/物品/台词/场景/行为）/ 预计回收第Y卷；总纲末尾汇总一份伏笔台账
5. 使用 Markdown 格式，每卷格式示例：
%%MASTER_FORMAT_EXAMPLE%%
%%OUTLINE_METHOD_EXTRA%%"""


OUTLINE_REWRITE_BASE = """请为《{title}》重新规划全书总纲。

【命名与标题语域（硬约束）】
章节标题、卷名、以及一切会写进正文世界的名词（人物/势力/功法/装置/系统词条）必须使用符合本题材世界观的语言；禁止现代职场/统计/网络词汇入名（如"数据、KPI、复盘、成本、上线"）。大纲中的策划性说明（爽点设计、数值/状态等工作栏目）不受此限。%%NAMING_HINT%%

【题材】
{genre} / {substyle}

{independent_stage_prompt}

【题材锁定】
{genre_guard}

【题材笔调校准】
{positive_style_instruction}

【子风格锁定】
{substyle_instruction}

【用户指导意见】
{guidance}

【设定参考】
{world}
{power}
{char}
{gold_finger}
{entity_libraries}

【参考：题材核心节奏】
{trope_focus}
{style_guide}
【参考：子风格示例（按当前子风格抽取）】
{substyle_examples}
【参考：题材表达示例（按当前题材动态加载）】
{genre_examples}
要求：学习风格而非复写句子。

【当前文稿】
{current_outline}

【核心任务】
请**完整重写**上述总纲文件。如果当前文稿为空或仅有骨架，请尽情发挥。
结构要求：
1. 卷名格式：## 第X卷 《卷名》（约XX-XX章）
2. 为每一卷（%%VOLUME_COUNT_HINT%%）设计：
   - **预计章数**：如"约50-60章"
   - **核心冲突**：本卷主要矛盾
   - **关键爽点**：让读者爽的高光时刻
   - **卷末高潮**：本卷结局
   - **关键伏笔**：为后续埋下的线索
3. 每卷标注卷级关键节点：切入点、上升段、卷高潮、回落收束。
4. 跨卷伏笔用台账式标注：【伏笔F-01】埋设第X卷 / 类型 / 预计回收第Y卷；总纲末尾汇总伏笔台账。
5. 整体节奏要前松后紧，每一卷都要有明确的升级或地图切换。
6. 若【当前文稿】中存在违反本题材附加要求或禁令的桥段，重写时必须替换为符合题材的情境，禁止原样保留。
%%OUTLINE_METHOD_EXTRA%%

格式示例：
%%REWRITE_FORMAT_EXAMPLE%%

请输出完整的 Markdown 内容："""


OUTLINE_VOLUME_BASE = """你是一位专业的网文大纲策划师。请严格根据【总纲】和【设定】，为第 {volume} 卷生成详细大纲。

【命名与标题语域（硬约束）】
章节标题、以及一切会写进正文世界的名词（人物/势力/功法/装置/系统词条）必须使用符合本题材世界观的语言；禁止现代职场/统计/网络词汇入名（如"数据、KPI、复盘、成本、上线"）。大纲中的策划性说明（爽点设计、数值/状态等工作栏目）不受此限。%%NAMING_HINT%%

【小说信息】
- 书名：《{title}》
- 题材：{genre}
- 子风格：{substyle}

{independent_stage_prompt}

【题材锁定】
{genre_guard}

【题材笔调校准】
{positive_style_instruction}

【子风格锁定】
{substyle_instruction}

{prev_vol_context}

{character_context}

【第 {volume} 卷总纲摘要】
{volume_outline}

【世界观设定】
{world}

【力量体系】
{power}

【主角设定】
{char}

【金手指/系统设定】
{gold_finger}

【实体库标准名】
{entity_libraries}

【规划参考】
{chapter_planning}
{conflict_design}
{trope_focus}
{style_guide}
【子风格示例（按当前子风格抽取）】
{substyle_examples}
【题材示例（按当前题材动态加载）】
{genre_examples}
要求：学习表达风格，不照抄句子。

【输出要求】
1. 第一行必须是卷标题，格式：# 第 {volume} 卷：【卷名】（第 {vol_start_chapter}-{vol_end_chapter} 章）
{opening_rule}
3. 必须严格遵循上方总纲摘要中的剧情走向和爽点
4. 生成第 {start_chapter} 章到第 {end_chapter} 章，共 {chapters_count} 章的详细大纲
5. 章节编号必须从 {start_chapter} 开始，且后续每章编号必须精准等于前一章编号 + 1（例如第30章后紧接着必须是第31章），绝对严禁任何跨章跳号（如从第30章直接写到第35章）！
6. 每章格式：**第X章：章节标题**，包含主要情节、爽点设计
7. 确保人物名、地点名、势力名与设定一致
8. 使用 Markdown 格式
9. **在大纲末尾添加"本卷角色规划"部分**（如果有活跃角色表）
10. ⚠️ **【连贯性铁律】章节编号必须连续无断层**：严禁遗漏任何章号，第 {start_chapter} 章至第 {end_chapter} 章必须逐章写齐！


【章级方法论（每章大纲必须落实）】
1. 每章同时写明四类任务：剧情任务（推进什么）、角色任务（谁被塑造/关系怎么变）、信息任务（向读者放出或隐瞒什么）、情绪任务（读者该有什么感受）。
2. 每章至少安排：1 个爽点（写明类型与兑现方式）、1 个压抑点（为后续爽点蓄力）、1 个章末钩子。爽点执行遵循「铺垫-兑现-微反转」，善用读者与角色之间的信息差。
3. 伏笔用台账式标注：【伏笔F-01】埋设第X章 / 类型（身份/物品/台词/场景/行为）/ 预计回收第Y章；本卷埋设与回收的伏笔都要列出。
4. 输出前做结构风险自检：是否存在连续 3 章无爽点的注水段？前 3-5 章是否展示了核心卖点？高潮章是否过密或过疏？
%%OUTLINE_METHOD_EXTRA%%

⚠️ **【极重要】数值变化必须明确标注**：
涉及战斗、伤亡、资源消耗的章节，必须在大纲中**明确写出具体数字或估算范围**！
%%VOLUME_NUMERIC_EXAMPLE%%"""


OUTLINE_POLISH_BASE = """你是一位专业的网文大纲医生。请根据用户的修改要求，对已有的大纲进行润色和优化。

【核心任务】
根据用户的【修改要求】，重写或优化大纲内容。

【注意事项】
1. **结构保持**：尽量保持原有的章节号和整体架构，除非用户要求重组。
2. **针对性修改**：如果是要求"增加数值"，请在每章末尾补充具体的伤亡/消耗统计。
3. **格式规范**：输出标准的 Markdown 大纲。
4. **完整性**：输出完整的大纲内容，不要只输出修改片段。

【数值标记规范（关键）】
如果用户要求添加数值，请参考以下格式：
%%POLISH_NUMERIC_EXAMPLE%%

【润色后自检（五维，输出前完成）】
完整性（章节/爽点/钩子要素齐全）、逻辑性（因果与时间线自洽）、吸引力（卖点与期待感是否变弱）、节奏（高潮疏密与注水段）、可行性（正文可执行、无凭空新增设定）。发现问题先修正再输出。

{independent_stage_prompt}

【题材锁定（最高优先级）】
当前题材：{genre}
{genre_guard}
{positive_style_instruction}
{substyle_instruction}
若修改要求未明确要求跨题材试验，文风必须严格锁定在当前题材范式内。

【题材风格参考】
{style_guide}

【子风格示例（按当前子风格抽取）】
{substyle_examples}

【题材示例（按当前题材动态加载）】
{genre_examples}
要求：只学习语气与节奏，不照抄原句。"""


EXTRACT_ENTITIES_BASE = """{style_section}你是小说世界观分析助手。请分析第{chapter}章的内容，提取新出现的重要元素。

【题材】
{genre} / {substyle}

【抽取片段】
当前处理第 {chunk_index}/{chunk_total} 段（仅输出当前片段中明确出现的事实，禁止臆测）。

【当前已有角色】
{roster}

【当前已有%%TECH_LABEL%%（标准名，必须优先复用）】
{existing_techniques}

【第{chapter}章内容片段】
{content}

请提取本章**新出现**的重要元素（排除已有角色和路人），输出 JSON：
```json
{
  "new_characters": [
    {
      "name": "角色名",
      "importance": "major/minor/villain",
      "identity": "身份（%%IDENTITY_EG%%）",
      "relation": "与主角关系",
      "appearance": "外貌描写",
      "personality": "性格特点",
      "realm": "%%REALM_DESC%%",
      "location": "%%LOCATION_DESC%%",
      "first_action": "本章主要行为"
    }
  ],
  "new_treasures": [
    {
      "name": "宝物名称",
      "tier": "%%TIER_DESC%%",
      "effect": "效果/用途",
      "owner": "当前持有者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为旧物升级/破损修复，填旧名称，否则留空）"
    }
  ],
  "new_techniques": [
    {
      "name": "%%TECH_LABEL%%名称",
      "tier": "%%TECH_TIER_DESC%%",
      "effect": "效果/特点",
      "practitioner": "修炼者/掌握者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为进阶/补全/融合，填旧名称，否则留空）"
    }
  ],
  "new_organizations": [
    {
      "name": "势力名称",
      "type": "%%ORG_TYPE_DESC%%",
      "strength": "实力等级",
      "relation": "与主角关系（敌对/中立/友好）",
      "key_figures": "关键人物"
    }
  ],
  "new_locations": [
    {
      "name": "地点名称",
      "type": "%%LOC_TYPE_DESC%%",
      "features": "特点",
      "importance": "重要性说明"
    }
  ],
  "status_changes": [
    {
      "name": "角色名",
      "status": "当前状态（如重伤、死亡、失踪）",
      "realm": "最新%%REALM_LABEL%%（未变化填空字符串）",
      "location": "最新地点（未变化填空字符串）",
      "change": "状态变化简述（%%CHANGE_EG%%）"
    }
  ],
  "entity_events": [
    {"name": "实体名称", "type": "character/treasure/technique", "event": "本章发生的关键事件/重要行为/特殊用途"}
  ],
  "exits": [
    {"name": "角色名", "reason": "下线原因"}
  ],
  "status_file_updates": {
    "chapter_event": "本章最重要的事件概述（一句话）",
    "event_consequence": "该事件的数值/状态后果",
    "character_updates": [
      {"name": "角色名", "current_status": "新状态", "body_condition": "身体状况", "note": "备注"}
    ],
    "resource_updates": [
      {"resource_name": "资源名（%%RESOURCE_EG%%）", "new_value": "新值", "reason": "变化原因"}
    ],
    "troop_casualties": {
      "dead_count": "死亡人数（数字或估算如'约500人'）",
      "wounded_count": "受伤人数",
      "surviving_count": "存活人数（如果正文提到）",
      "unit_name": "%%UNIT_DESC%%",
      "description": "伤亡描述"
    },
    "new_items": [
      {"name": "物品名", "status": "状态", "description": "说明"}
    ]
  }
}
```

⚠️ **重点关注以下数值变化**：
%%EXTRACT_NUMERIC_FOCUS%%

如果正文中描述了"大量阵亡"、"折损过半"、"仅剩数百"等，请在 troop_casualties 中记录！

⚠️ **档案语域（硬约束）**：
提取产出的所有描述文本（性格、外貌、关系、事件摘要）将写入设定档案并回流到后续写作提示词——措辞必须使用本题材世界观语言；禁止用跨语域词汇概括人物（如古风人物写成"复盘型人格""数据敏感"）。

⚠️ **命名统一规则（必须遵守）**：
1. 若正文提到的%%TECH_LABEL%%与【当前已有%%TECH_LABEL%%】显然是同一招式（简称/别称/口语化写法），不要在 `new_techniques` 新建重复档案。
2. 优先使用功法库标准名；如确需新增，请确保不是已有条目的别名。
3. `previous_version` 尽量填写可追溯的前身名称，用于后续自动归并。

如果某类没有变化，输出空数组。只输出 JSON，不要其他内容。"""


CONTINUITY_SUMMARY_BASE = """你是一位负责维护小说连续性的编辑。请仔细阅读以下第{chapter}章内容，提取所有【下一章必须遵守】的关键信息。

【题材】
{genre} / {substyle}

【第{chapter}章内容】
{content}

请自由总结以下内容（如果有的话）：
1. **场景状态**：当前地点、时间、环境状况
2. **目击者**：有没有其他人看到了什么？他们的反应是什么？这些人会怎么做？
3. **角色状态**：主角和重要角色现在的位置、伤情、情绪
4. **遗留物品**：尸体、武器、血迹、证据等需要处理的东西
5. **未完成事件**：正在发生但没结束的事、承诺要做的事
6. **信息差**：谁知道什么、谁不知道什么
7. **悬念/钩子**：本章结尾的悬念是什么
8. **任何其他重要细节**：你认为下一章必须考虑的任何信息

【本题材必须额外盯住】
%%CONTINUITY_EXTRA%%

【重要】：请特别注意那些容易被忽略但会导致逻辑漏洞的细节！
比如：有围观群众却假装没人看到、角色明明受伤了却突然生龙活虎、时间地点突然跳跃等。

【写作要求】
1. 只保留事实、状态、位置、数量、因果、承诺、未完成事项。
2. 禁止复述原文修辞，禁止保留氛围词、情绪渲染、镜头语言、比喻和文学化表达。
3. 禁止使用"阴冷""死寂""压抑""诡异""毛骨悚然"等风格词，除非它本身是剧情规则或角色对白中的必要事实。
4. 输出要像制作组交接清单，不像小说摘要。

请用简洁清晰的条目列出，不要遗漏任何关键信息。"""


OPENING_THREE_BASE = """【黄金三章开篇协议】当前正在写第 {chapter} 章（前三章开篇期）。
题材：{genre} / {substyle}

黄金三章的本质是与读者签订「情绪契约」：让读者在最短时间内知道这本书爽在哪、主角凭什么、值得追下去的理由。以下要求只用于强化本章大纲已有内容，禁止为了满足开篇节奏私自新增事件、收益、反制、机缘或结局。

【三章功能分配】
- 第 1 章：立住主角（处境+性格+第一动作），亮出金手指或核心优势的第一面；前 300 字内必须出现钩子与情绪锚点，并给出「代偿承诺」——让读者预感到眼下的憋屈会翻倍偿还。%%OPENING_HOOK_EG%%
- 第 2 章：冲突升级，压迫加码；主角的应对开始显出章法，金手指/核心优势露出第二层；至少埋 1 个伏笔。
- 第 3 章：第一个小高潮，兑现第 1 章的代偿承诺（首次打脸/反击/收益落袋），同时开启新悬念，把读者推进第 4 章。

【压迫-反击节奏】
开篇期的情绪积累遵循「压迫-反击」：压迫要具体（谁、以什么方式、夺走什么），反击的第一步要在本章或下一章内兑现，不许压过三章不还。

【开篇底线】
1. 禁止开篇大段世界观说明书；设定信息全部揉进冲突与对话。
2. 每章结尾必须是钩子（危机/反转/悬念/期待），不许平收。
3. 主角必须主动做事，不许连续被动挨打超过一章。"""


COMBAT_SCENES_BASE = """# %%COMBAT_LABEL%%写作指南

【篇幅配比（单场冲突）】
起手与气氛 15-20% → 试探与交锋 20-25% → 升级与反复 30-40% → 高潮决胜 15-20% → 收尾与余波 10-15%。

【节奏控制】
1. 句式控节奏：交锋处用短句、动词开头；间歇处用长句收情绪。
2. 画面切换：近景（招式/伤处/手上动作）、远景（全场态势）、特写（表情/关键物）交替，不许一镜到底。
3. 环境必须参战：地形、器物、旁观者至少一项影响过程或结果。

%%COMBAT_TYPES%%

【底线】
- 胜负手必须呼应已铺垫的能力、道具或信息差，禁止临场变出新能力。
- 冲突结束必须结算：伤亡、消耗、收益、关系变化，用具体数字或明确状态。"""


DIALOGUE_WRITING_BASE = """# 对话写作指南

【三元组原则】
关键对话逐句考虑三元组：台词（说什么）+ 动作/微表情（说话时做什么）+ 潜台词（真正想表达什么）。潜台词可承载情感、动机、关系、情节、主题五类信息。

【一句三效】
每句对话至少占其一：塑造人物（语气辨识度/口头禅/立场）、推进关系或剧情、埋设伏笔。三者皆无的对话删掉。

【真实感】
1. 人物语气必须可辨识：不同角色说话方式明显不同，符合身份与教养。%%DIALOGUE_FLAVOR%%
2. 对话允许打断、答非所问、沉默——真人不按问答机器说话。
3. 信息差入戏：角色只说与其认知匹配的话，在「读者知而角色不知」处形成张力。"""


EMOTION_PSYCHOLOGY_BASE = """# 情绪场景写作指南

【三段配比】
高情绪场景按「铺垫 → 爆发 → 余韵」三段展开，铺垫给足动机，爆发短促有力，余韵留白收尾，比例约 3:5:2。

【七类场景要点】
吵架（针尖对麦芒逐步升级）、隐忍爆发（压到极限一次决堤）、告白（错位与迟疑比直白动人）、决裂（一句话斩断，动作收尾）、诀别（克制大于嚎啕）、道歉无力（补救追不上伤害）、和好有裂痕（和解但留刺）。%%EMOTION_FLAVOR%%

【底线】
1. 情绪靠动作与细节外化（手抖、停顿、避开视线），禁止报菜名式直写"他很愤怒"。
2. 保留「未说出口的话」：最重的那句留白，让读者替角色说完。
3. 防煽情过度：眼泪与嘶吼是最后手段，克制的痛感更持久。"""


SCENE_DESCRIPTION_BASE = """# 场景与画面写作指南

【场景卡四要素】
进入场景前明确：目的（这场戏为什么存在）、冲突（谁与谁在什么上较劲、强度几何）、转折（局面在哪一拍改变）、结果（情节/人物/主题各落下什么）。四要素缺一的场景压缩或合并。

【分镜五要素】
把场景拆成 3-8 个镜头，每个镜头明确：视角所在、画面内容、人物动作、关键对话、情绪基调；镜头间用动作或视线自然衔接。

【五感层次】
视觉打底，听觉与触觉制造临场，嗅觉与味觉点睛少用；每景选 2-3 种感官，不许五感堆砌。%%SCENE_FLAVOR%%

【底线】
环境描写必须服务戏剧：要么衬情绪、要么埋伏笔、要么参与冲突，纯风景描写删掉。"""


# 槽位 id → 基底（生成器与自校验共用）
SLOT_BASES: Dict[str, str] = {
    "outline_master": OUTLINE_MASTER_BASE,
    "outline_rewrite": OUTLINE_REWRITE_BASE,
    "outline_volume": OUTLINE_VOLUME_BASE,
    "outline_polish": OUTLINE_POLISH_BASE,
    "extract_state": EXTRACT_ENTITIES_BASE,
    "continuity_summary": CONTINUITY_SUMMARY_BASE,
    "opening_three": OPENING_THREE_BASE,
}

# 辅助文件族：非槽位、不进项目快照，运行时经 _load_style_package_file
# 按章节大纲关键词条件加载（见 skill_executor._load_scene_technique_bundle）。
# desire-description.md 不纳管。
AUX_FILENAMES: Dict[str, str] = {
    "combat_scenes": "combat-scenes.md",
    "dialogue_writing": "dialogue-writing.md",
    "emotion_psychology": "emotion-psychology.md",
    "scene_description": "scene-description.md",
}

AUX_BASES: Dict[str, str] = {
    "combat_scenes": COMBAT_SCENES_BASE,
    "dialogue_writing": DIALOGUE_WRITING_BASE,
    "emotion_psychology": EMOTION_PSYCHOLOGY_BASE,
    "scene_description": SCENE_DESCRIPTION_BASE,
}


# ---------------------------------------------------------------------------
# 运行时兜底常量（中性词表填充；项目槽位模板为空时使用）
# ---------------------------------------------------------------------------

OUTLINE_MASTER_FALLBACK = fill_vocab(OUTLINE_MASTER_BASE, DEFAULT_VOCAB)
OUTLINE_REWRITE_FALLBACK = fill_vocab(OUTLINE_REWRITE_BASE, DEFAULT_VOCAB)
OUTLINE_VOLUME_FALLBACK = fill_vocab(OUTLINE_VOLUME_BASE, DEFAULT_VOCAB)
OUTLINE_POLISH_FALLBACK = fill_vocab(OUTLINE_POLISH_BASE, DEFAULT_VOCAB)
EXTRACT_ENTITIES_FALLBACK = fill_vocab(EXTRACT_ENTITIES_BASE, DEFAULT_VOCAB)
CONTINUITY_SUMMARY_FALLBACK = fill_vocab(CONTINUITY_SUMMARY_BASE, DEFAULT_VOCAB)
OPENING_THREE_FALLBACK = fill_vocab(OPENING_THREE_BASE, DEFAULT_VOCAB)

SLOT_FALLBACKS: Dict[str, str] = {
    "outline_master": OUTLINE_MASTER_FALLBACK,
    "outline_rewrite": OUTLINE_REWRITE_FALLBACK,
    "outline_volume": OUTLINE_VOLUME_FALLBACK,
    "outline_polish": OUTLINE_POLISH_FALLBACK,
    "extract_state": EXTRACT_ENTITIES_FALLBACK,
    "continuity_summary": CONTINUITY_SUMMARY_FALLBACK,
    "opening_three": OPENING_THREE_FALLBACK,
}

# 辅助文件兜底（包文件缺失/为空时使用）
AUX_FALLBACKS: Dict[str, str] = {
    key: fill_vocab(base, DEFAULT_VOCAB) for key, base in AUX_BASES.items()
}


# ---------------------------------------------------------------------------
# 契约块（代码渲染后追加，不进模板、不可编辑）
# ---------------------------------------------------------------------------

OUTLINE_MASTER_CONTRACT = """

【输出格式契约（系统级硬约束）】
1. 每一卷的标题行必须使用格式：## 第X卷 《卷名》（约XX章），其中 X 为从 1 开始连续递增的阿拉伯数字。
2. 除卷标题外，任何行不得以「## 第X卷」开头。
3. 直接输出 Markdown 正文，不要输出任何解释性前言或结语。"""

OUTLINE_REWRITE_CONTRACT = OUTLINE_MASTER_CONTRACT

# 含 {volume}/{start_chapter}/{end_chapter}/{chapters_count} 占位符，随主模板一同渲染；
# 卷标题使用全卷范围 {vol_start_chapter}/{vol_end_chapter}（分批时与批次范围不同）。
OUTLINE_VOLUME_CONTRACT = """

【输出格式契约（系统级硬约束）】
1. 第一行必须是卷标题：# 第 {volume} 卷：【卷名】（第 {vol_start_chapter}-{vol_end_chapter} 章）
2. 必须覆盖第 {start_chapter} 章到第 {end_chapter} 章共 {chapters_count} 章，章号连续递增，不得跳号、不得重复。
3. 每章标题行必须使用格式：**第X章：章节标题**（X 为阿拉伯数字全书连续编号）。
4. 直接输出 Markdown 正文，只输出卷标题与章节条目，禁止输出「本批概览」「批次说明」等任何过程性段落，禁止解释性前言或结语。"""

# 分批生成的续写批次专用契约：不重复卷标题，直接续章节条目。
OUTLINE_VOLUME_CONTRACT_CONT = """

【输出格式契约（系统级硬约束，本批为同一卷的续写批次）】
1. 禁止输出卷标题行（# 第X卷…），直接从「**第 {start_chapter} 章：章节标题**」条目开始输出。
2. 必须覆盖第 {start_chapter} 章到第 {end_chapter} 章共 {chapters_count} 章，章号连续递增，不得跳号、不得重复、不得改写已生成的章节。
3. 每章标题行必须使用格式：**第X章：章节标题**（X 为阿拉伯数字全书连续编号）。
4. 直接输出 Markdown 正文，只输出章节条目，禁止输出「本批概览」「批次说明」等任何过程性段落，禁止解释性前言或结语。"""

OUTLINE_POLISH_CONTRACT = """

【输出格式契约（系统级硬约束）】
1. 输出完整的大纲全文，禁止只输出修改片段或差异说明。
2. 保持原有的卷标题与章节标题格式（## 第X卷… / **第X章：章节标题**），不要改变编号体系。
3. 直接输出 Markdown 正文，不要输出任何解释性前言或结语。"""

EXTRACT_CONTRACT = """

【输出契约（系统级硬约束，优先级最高）】
1. 只输出一个合法 JSON 对象，禁止 Markdown 代码块包裹，禁止任何前后缀文字。
2. 顶层键必须且只能是：new_characters、new_treasures、new_techniques、new_organizations、new_locations、status_changes、entity_events、exits、status_file_updates。
3. status_file_updates 的子键固定为：chapter_event、event_consequence、character_updates、resource_updates、troop_casualties、new_items。
4. 各元素的英文字段名以上方 JSON 结构为准，不得增删或改名；键名一律用英文，值用中文。
5. 某类没有内容时输出空数组 []；status_file_updates 无内容时输出空对象 {}。"""

# 实体提取落库依赖的顶层键（生成器自校验与保存校验共用）
EXTRACT_REQUIRED_KEYS = (
    "new_characters",
    "new_treasures",
    "new_techniques",
    "new_organizations",
    "new_locations",
    "status_changes",
    "entity_events",
    "exits",
    "status_file_updates",
)


# ---------------------------------------------------------------------------
# 槽位注册数据（project_prompt_store 与生成器共用的单一源头）
# ---------------------------------------------------------------------------

SLOT_FILENAMES: Dict[str, str] = {
    "outline_master": "outline-master.md",
    "outline_rewrite": "outline-rewrite.md",
    "outline_volume": "outline-volume.md",
    "outline_polish": "outline-polish.md",
    "extract_state": "extract-state.md",
    "continuity_summary": "continuity-summary.md",
    "opening_three": "opening-three.md",
}

SLOT_VARIABLES: Dict[str, list] = {
    "outline_master": [
        "title", "genre", "substyle",
        "independent_stage_prompt", "genre_guard",
        "positive_style_instruction", "substyle_instruction",
        "world", "power", "char", "gold_finger", "additional_info",
        "trope_focus", "style_guide", "substyle_examples", "genre_examples",
    ],
    "outline_rewrite": [
        "title", "genre", "substyle",
        "independent_stage_prompt", "genre_guard",
        "positive_style_instruction", "substyle_instruction",
        "guidance", "world", "power", "char", "gold_finger",
        "entity_libraries", "trope_focus", "style_guide",
        "substyle_examples", "genre_examples", "current_outline",
    ],
    "outline_volume": [
        "volume", "chapters_count", "start_chapter", "end_chapter",
        "vol_start_chapter", "vol_end_chapter",
        "title", "genre", "substyle",
        "independent_stage_prompt", "genre_guard",
        "positive_style_instruction", "substyle_instruction",
        "prev_vol_context", "character_context", "opening_rule",
        "volume_outline", "world", "power", "char", "gold_finger",
        "entity_libraries", "chapter_planning", "conflict_design",
        "trope_focus", "style_guide", "substyle_examples", "genre_examples",
    ],
    "outline_polish": [
        "genre", "independent_stage_prompt", "genre_guard",
        "positive_style_instruction", "substyle_instruction",
        "style_guide", "substyle_examples", "genre_examples",
    ],
    "extract_state": [
        "style_section", "chapter", "genre", "substyle",
        "chunk_index", "chunk_total", "roster", "existing_techniques", "content",
    ],
    "continuity_summary": [
        "chapter", "content", "genre", "substyle",
    ],
    "opening_three": [
        "chapter", "genre", "substyle",
    ],
}
