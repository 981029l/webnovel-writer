<!-- generated slot=extract_state gen_hash=c895d20872 -->
{style_section}你是小说世界观分析助手。请分析第{chapter}章的内容，提取新出现的重要元素。

【题材】
{genre} / {substyle}

【抽取片段】
当前处理第 {chunk_index}/{chunk_total} 段（仅输出当前片段中明确出现的事实，禁止臆测）。

【当前已有角色】
{roster}

【当前已有技能/底牌（标准名，必须优先复用）】
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
      "identity": "身份（配偶/前任/婆家人/同事/发小等）",
      "relation": "与主角关系",
      "appearance": "外貌描写",
      "personality": "性格特点",
      "realm": "当前身份（如大厂程序员、县城教师、全职主妇）",
      "location": "当前地点（如出租屋、老家县城、公司工位）",
      "first_action": "本章主要行为"
    }
  ],
  "new_treasures": [
    {
      "name": "宝物名称",
      "tier": "价值（如：存款数额、房产、关键证据）",
      "effect": "效果/用途",
      "owner": "当前持有者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为旧物升级/破损修复，填旧名称，否则留空）"
    }
  ],
  "new_techniques": [
    {
      "name": "技能/底牌名称",
      "tier": "分量（如：一锤定音的证据、专业技能）",
      "effect": "效果/特点",
      "practitioner": "修炼者/掌握者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为进阶/补全/融合，填旧名称，否则留空）"
    }
  ],
  "new_organizations": [
    {
      "name": "势力名称",
      "type": "类型（家庭/公司/亲戚圈/朋友圈等）",
      "strength": "实力等级",
      "relation": "与主角关系（敌对/中立/友好）",
      "key_figures": "关键人物"
    }
  ],
  "new_locations": [
    {
      "name": "地点名称",
      "type": "类型（城市/小区/单位/老家等）",
      "features": "特点",
      "importance": "重要性说明"
    }
  ],
  "status_changes": [
    {
      "name": "角色名",
      "status": "当前状态（如重伤、死亡、失踪）",
      "realm": "最新身份（未变化填空字符串）",
      "location": "最新地点（未变化填空字符串）",
      "change": "状态变化简述（如摊牌、离婚、录音曝光、当众反转）"
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
      {"resource_name": "资源名（如存款、房产、证据、舆论支持）", "new_value": "新值", "reason": "变化原因"}
    ],
    "troop_casualties": {
      "dead_count": "死亡人数（数字或估算如'约500人'）",
      "wounded_count": "受伤人数",
      "surviving_count": "存活人数（如果正文提到）",
      "unit_name": "群体称呼（如'婆家亲戚'、'部门同事'等）",
      "description": "伤亡描述"
    },
    "new_items": [
      {"name": "物品名", "status": "状态", "description": "说明"}
    ]
  }
}
```

⚠️ **重点关注以下数值变化**：
1. **钱账**：彩礼、存款、转账的具体数额（必须提取！）
2. **证据清单**：录音、聊天记录、票据等新增证据
3. **关系节点**：破裂/修复/站队的关键变化
4. **知情范围**：谁知道了什么、舆论走向

如果正文中描述了"大量阵亡"、"折损过半"、"仅剩数百"等，请在 troop_casualties 中记录！

⚠️ **档案语域（硬约束）**：
提取产出的所有描述文本（性格、外貌、关系、事件摘要）将写入设定档案并回流到后续写作提示词——措辞必须使用本题材世界观语言；禁止用跨语域词汇概括人物（如古风人物写成"复盘型人格""数据敏感"）。

⚠️ **命名统一规则（必须遵守）**：
1. 若正文提到的技能/底牌与【当前已有技能/底牌】显然是同一招式（简称/别称/口语化写法），不要在 `new_techniques` 新建重复档案。
2. 优先使用功法库标准名；如确需新增，请确保不是已有条目的别名。
3. `previous_version` 尽量填写可追溯的前身名称，用于后续自动归并。

如果某类没有变化，输出空数组。只输出 JSON，不要其他内容。
