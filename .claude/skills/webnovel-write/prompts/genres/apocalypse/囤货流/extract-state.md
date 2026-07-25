<!-- generated slot=extract_state gen_hash=c5b25f05f1 -->
{style_section}你是小说世界观分析助手。请分析第{chapter}章的内容，提取新出现的重要元素。

【题材】
{genre} / {substyle}

【抽取片段】
当前处理第 {chunk_index}/{chunk_total} 段（仅输出当前片段中明确出现的事实，禁止臆测）。

【当前已有角色】
{roster}

【当前已有异能/技能（标准名，必须优先复用）】
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
      "identity": "身份（幸存者/军方军官/佣兵/掠夺者头目/基地管理层等）",
      "relation": "与主角关系",
      "appearance": "外貌描写",
      "personality": "性格特点",
      "realm": "当前异能等级或进化阶位（如觉醒一阶、二级强化者、三阶变异）",
      "location": "当前地点（如废弃超市、庇护所B区、高速收费站）",
      "first_action": "本章主要行为"
    }
  ],
  "new_treasures": [
    {
      "name": "宝物名称",
      "tier": "等级（如：民用级、军用级、战略物资级）",
      "effect": "效果/用途",
      "owner": "当前持有者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为旧物升级/破损修复，填旧名称，否则留空）"
    }
  ],
  "new_techniques": [
    {
      "name": "异能/技能名称",
      "tier": "等级（如：一阶、二阶、强化系/精神系）",
      "effect": "效果/特点",
      "practitioner": "修炼者/掌握者",
      "origin": "来源/出处",
      "previous_version": "前身名称（若为进阶/补全/融合，填旧名称，否则留空）"
    }
  ],
  "new_organizations": [
    {
      "name": "势力名称",
      "type": "类型（庇护所/军方残部/佣兵团/掠夺者/幸存者聚落等）",
      "strength": "实力等级",
      "relation": "与主角关系（敌对/中立/友好）",
      "key_figures": "关键人物"
    }
  ],
  "new_locations": [
    {
      "name": "地点名称",
      "type": "类型（安全区/废墟/物资点/感染区等）",
      "features": "特点",
      "importance": "重要性说明"
    }
  ],
  "status_changes": [
    {
      "name": "角色名",
      "status": "当前状态（如重伤、死亡、失踪）",
      "realm": "最新异能等级/进化阶位（未变化填空字符串）",
      "location": "最新地点（未变化填空字符串）",
      "change": "状态变化简述（如异能觉醒、被感染、断粮、重伤失血）"
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
      {"resource_name": "资源名（如食物（按天数）、饮用水、弹药、燃油、药品）", "new_value": "新值", "reason": "变化原因"}
    ],
    "troop_casualties": {
      "dead_count": "死亡人数（数字或估算如'约500人'）",
      "wounded_count": "受伤人数",
      "surviving_count": "存活人数（如果正文提到）",
      "unit_name": "队伍名称（如'巡逻小队'、'物资搜索队'等）",
      "description": "伤亡描述"
    },
    "new_items": [
      {"name": "物品名", "status": "状态", "description": "说明"}
    ]
  }
}
```

⚠️ **重点关注以下数值变化**：
1. **囤货台账**：新入库物资的品类与数量（必须逐项提取！）
2. **消耗流水**：食物、水、弹药、药品的每笔支出
3. **幸存者伤亡**：死亡/受伤/感染人数
4. **空间/仓库**：储物空间容量、仓库安全状态

如果正文中描述了"大量阵亡"、"折损过半"、"仅剩数百"等，请在 troop_casualties 中记录！

⚠️ **档案语域（硬约束）**：
提取产出的所有描述文本（性格、外貌、关系、事件摘要）将写入设定档案并回流到后续写作提示词——措辞必须使用本题材世界观语言；禁止用跨语域词汇概括人物（如古风人物写成"复盘型人格""数据敏感"）。

⚠️ **命名统一规则（必须遵守）**：
1. 若正文提到的异能/技能与【当前已有异能/技能】显然是同一招式（简称/别称/口语化写法），不要在 `new_techniques` 新建重复档案。
2. 优先使用功法库标准名；如确需新增，请确保不是已有条目的别名。
3. `previous_version` 尽量填写可追溯的前身名称，用于后续自动归并。

如果某类没有变化，输出空数组。只输出 JSON，不要其他内容。
