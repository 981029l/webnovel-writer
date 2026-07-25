<!-- generated slot=extract_state gen_hash=c9e7b46cb1 -->
{style_section}你是小说世界观分析助手。请分析第{chapter}章的内容，提取新出现的重要元素。

【题材】
{genre} / {substyle}

【抽取片段】
当前处理第 {chunk_index}/{chunk_total} 段（仅输出当前片段中明确出现的事实，禁止臆测）。

【当前已有角色】
{roster}

【当前已有本事/技艺（标准名，必须优先复用）】
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
      "identity": "身份（嫡母/庶妹/婆母/陪房嬷嬷/对家妃嫔等）",
      "relation": "与主角关系",
      "appearance": "外貌描写",
      "personality": "性格特点",
      "realm": "当前位份或地位（如嫡次女、贵妾、正五品诰命、昭仪）",
      "location": "当前地点（如荣安堂、西跨院、御花园）",
      "first_action": "本章主要行为"
    }
  ],
  "new_treasures": [
    {
      "name": "宝物名称",
      "tier": "规格（如：御赐、内造之物、嫁妆头面）",
      "effect": "效果/用途",
      "owner": "当前持有者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为旧物升级/破损修复，填旧名称，否则留空）"
    }
  ],
  "new_techniques": [
    {
      "name": "本事/技艺名称",
      "tier": "水准（如：管家理事、女红厨艺、宫廷礼仪）",
      "effect": "效果/特点",
      "practitioner": "修炼者/掌握者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为进阶/补全/融合，填旧名称，否则留空）"
    }
  ],
  "new_organizations": [
    {
      "name": "势力名称",
      "type": "类型（府邸/宫廷派系/母族/姻亲等）",
      "strength": "实力等级",
      "relation": "与主角关系（敌对/中立/友好）",
      "key_figures": "关键人物"
    }
  ],
  "new_locations": [
    {
      "name": "地点名称",
      "type": "类型（院落/正堂/宫殿/庄子/铺面等）",
      "features": "特点",
      "importance": "重要性说明"
    }
  ],
  "status_changes": [
    {
      "name": "角色名",
      "status": "当前状态（如重伤、死亡、失踪）",
      "realm": "最新位份/地位（未变化填空字符串）",
      "location": "最新地点（未变化填空字符串）",
      "change": "状态变化简述（如晋位、禁足、失宠、有孕、被夺管家权）"
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
      {"resource_name": "资源名（如月例银子、嫁妆、庄子铺面、人脉）", "new_value": "新值", "reason": "变化原因"}
    ],
    "troop_casualties": {
      "dead_count": "死亡人数（数字或估算如'约500人'）",
      "wounded_count": "受伤人数",
      "surviving_count": "存活人数（如果正文提到）",
      "unit_name": "群体称呼（如'陪房下人'、'各房女眷'等）",
      "description": "伤亡描述"
    },
    "new_items": [
      {"name": "物品名", "status": "状态", "description": "说明"}
    ]
  }
}
```

⚠️ **重点关注以下数值变化**：
1. **位份权柄**：晋位/降位、管家权/宫权归属（必须记录！）
2. **银钱产业**：月例、嫁妆、庄铺收益的具体数目
3. **人手布局**：安插/拔除的眼线与心腹
4. **把柄人情**：新抓的把柄、新欠的人情

如果正文中描述了"大量阵亡"、"折损过半"、"仅剩数百"等，请在 troop_casualties 中记录！

⚠️ **档案语域（硬约束）**：
提取产出的所有描述文本（性格、外貌、关系、事件摘要）将写入设定档案并回流到后续写作提示词——措辞必须使用本题材世界观语言；禁止用跨语域词汇概括人物（如古风人物写成"复盘型人格""数据敏感"）。

⚠️ **命名统一规则（必须遵守）**：
1. 若正文提到的本事/技艺与【当前已有本事/技艺】显然是同一招式（简称/别称/口语化写法），不要在 `new_techniques` 新建重复档案。
2. 优先使用功法库标准名；如确需新增，请确保不是已有条目的别名。
3. `previous_version` 尽量填写可追溯的前身名称，用于后续自动归并。

如果某类没有变化，输出空数组。只输出 JSON，不要其他内容。
