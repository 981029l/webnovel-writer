---
name: webnovel-write
description: Writes webnovel chapters (3000-5000 words) using v5.1 dual-agent architecture. Context Agent gathers context, writer produces pure text (no XML tags), review agents report issues, polish fixes problems, Data Agent extracts entities with AI.
allowed-tools: Read Write Edit Grep Bash Task
---

# Chapter Writing Skill

## Workflow Checklist

⚠️ **强制要求**: 开始写作前，**必须复制以下清单**到回复中并逐项勾选。跳过任何步骤视为工作流不完整。

```
章节创作进度 (v5.1)：
- [ ] Step 1: Context Agent 搜集上下文
- [ ] Step 2: 生成章节内容 (纯正文，3000-5000字)
- [ ] Step 3: 审查 (7个Agent并行，输出汇总表格)
- [ ] Step 3.5: 自动修复循环 (仅当 critical/high > 0 时触发)
- [ ] Step 4: 最终润色 (AI痕迹检测 + 自然化 + 排版)
- [ ] Step 5: Data Agent 处理数据链
- [ ] Step 6: Git 备份
```

**工作流规则**:
1. 每完成一个 Step，立即更新 TodoWrite 状态
2. Step 之间的验证必须通过才能进入下一步
3. 如遇阻断，记录 deviation 但不可跳过

---

## Step 1: Context Agent 搜集上下文

**调用 Context Agent**:

使用 Task 工具调用 `context-agent` subagent：

```
调用 context-agent，参数：
- chapter: {chapter_num}
- project_root: {PROJECT_ROOT}
- storage_path: .webnovel/
- state_file: .webnovel/state.json
```

**Agent 自动完成**:
1. 读取本章大纲，分析需要什么信息
2. 读取 state.json 获取主角状态快照
3. 调用 index.db (v5.1 schema) 查询相关实体和别名
4. 调用 data_modules.rag_adapter 语义检索
5. Grep 设定集搜索相关设定
6. 评估伏笔紧急度
7. 选择风格样本
8. 组装上下文包 JSON (v5.1)

**输出**：上下文包 JSON，包含：
- `core`: 大纲、主角快照、最近摘要
- `scene`: 地点上下文、出场角色、紧急伏笔
- `global`: 世界观骨架、力量体系、风格样本
- `rag`: 语义检索召回的相关场景
- `alerts`: 关键风险提示（如消歧警告/待确认项）

**失败处理**：
- 如果大纲不存在 → 提示用户先创建大纲
- 如果 state.json 不存在 → 提示用户初始化项目

---

## Step 2: 生成章节内容

**字数**: 3000-5000 字

**核心原则**:
- **大纲即法律**: 100% 执行大纲
- **设定即物理**: 实力 ≤ 上下文包中的设定
- **纯正文**: 不需要写任何 XML 标签

**加载核心约束**:
```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/core-constraints.md"
```

**按需加载场景参考**:

| 场景类型 | 判断条件 | 执行命令 |
|---------|---------|---------|
| 战斗戏 | 大纲含打斗/对决/追逐 | `cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/combat-scenes.md"` |
| 情感戏 | 大纲含告白/冲突/羁绊 | `cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/emotion-psychology.md"` |
| 对话密集 | 预估对话 >50% | `cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/dialogue-writing.md"` |
| 复杂场景 | 新地点/大场面描写 | `cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/scene-description.md"` |
| 欲念描写 | 大纲含暧昧/亲密/情欲场景 | `cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/desire-description.md"` |

**强制加载题材风格 prompt**（根据 state.json 中的 genre 字段自动选择）:
```bash
# ⚠️ 必须加载！题材风格 prompt 是防止氛围跑偏的核心锚定
# 从 state.json 读取 genre 字段，加载对应题材的 writer.md
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/prompts/genres/{genre}/writer.md"

# 如果有子风格(substyle)，同时加载子风格 prompt
# cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/prompts/genres/{genre}/substyles/{substyle}.md"
```

**可用题材**: xuanhuan(玄幻)、dog-blood-romance(狗血言情)、period-drama(古言)、realistic(都市现实)、zhihu-short(知乎短篇)、rules-mystery(规则怪谈)、dark(黑暗题材)

⚠️ **如果未加载题材风格 prompt，写作步骤视为无效。** 题材 prompt 包含该题材的氛围基调、对话风格、禁词表等关键约束，缺失会导致风格跑偏。

**输出格式**:
- Markdown 文件: `正文/第{NNNN}章.md`
- 章节末尾追加摘要（见模板）
- 纯正文，Data Agent 会自动提取实体

---

## Step 3: 审查

⚠️ **强制要求**: 必须在**同一条消息**中并行调用全部 7 个 Agent。缺少任何一个视为步骤未完成，**禁止进入 Step 4**。

**执行命令（不可修改）**:

在一条消息中发送 7 个 Task 工具调用，每个调用需传入以下公共参数：
- project_root: {PROJECT_ROOT}
- storage_path: .webnovel/
- state_file: .webnovel/state.json
- chapter_file: "正文/第{NNNN}章.md"

| # | subagent_type | 必须 | 说明 |
|---|---------------|------|------|
| 1 | `high-point-checker` | ✅ | 爽点密度检查 |
| 2 | `consistency-checker` | ✅ | 设定一致性检查 |
| 3 | `pacing-checker` | ✅ | Strand 节奏检查 |
| 4 | `ooc-checker` | ✅ | 人物 OOC 检查（强化版） |
| 5 | `continuity-checker` | ✅ | 连贯性检查 |
| 6 | `anti-ai-detector` | ✅ | AI痕迹检测 |
| 7 | `dialogue-reality-enforcer` | ✅ | 对话真实性强制检查 |

**验证**: 收到全部 7 份报告后，**必须输出以下汇总表格**：

```
┌─────────────────────────────────────────────────┐
│ 审查汇总 - 第 {chapter_num} 章                    │
├─────────────────────┬───────────┬───────────────┤
│ Agent               │ 结果      │ 关键问题数     │
├─────────────────────┼───────────┼───────────────┤
│ high-point-checker  │ PASS/FAIL │ {N}           │
│ consistency-checker │ PASS/FAIL │ {N}           │
│ pacing-checker      │ PASS/FAIL │ {N}           │
│ ooc-checker         │ PASS/FAIL │ {N}           │
│ continuity-checker  │ PASS/FAIL │ {N}           │
│ anti-ai-detector    │ PASS/FAIL │ {N}           │
│ dialogue-reality-enforcer │ PASS/FAIL │ {N}     │
├─────────────────────┴───────────┴───────────────┤
│ critical issues: {N}  |  high issues: {N}       │
│ 是否可进入润色: {是/否}                           │
└─────────────────────────────────────────────────┘
```

**审查后处理规则**:

根据汇总表格中的 critical/high issues 数量，决定下一步：

| 情况 | 下一步 |
|------|--------|
| critical = 0 且 high = 0 | → 直接进入 Step 4 最终润色 |
| critical > 0 或 high > 0 | → 进入 Step 3.5 自动修复循环 |

> medium/low 问题不触发修复循环，留到 Step 4 润色时顺带处理。

---

## Step 3.5: 自动修复循环（仅当 critical/high > 0 时触发）

⚠️ **核心原则**: 主要问题（high）和严重问题（critical）必须修好才能继续。修不好就重写。

### 修复策略（按顺序升级）

```
Phase A: 针对性修订（最多 2 轮）
  └→ 针对具体问题段落修改，不重写整章
  └→ 每轮修订后，重新调用 FAIL 的 Agent 验证
  └→ critical/high 清零 → 跳到 Step 4

Phase B: 深度润色重写（最多 2 轮）
  └→ 加载 polish-guide.md，对问题区域深度改写
  └→ 每轮润色后，重新调用 FAIL 的 Agent 验证
  └→ critical/high 清零 → 跳到 Step 4（跳过 4.1，直接从 4.2 开始）

Phase C: 整章重新生成（最多 1 次）
  └→ 保留 Step 1 的上下文包，回到 Step 2 重新写
  └→ 重新走完整 Step 3 审查（7个Agent全跑）
  └→ 如果仍有 critical/high → 记录 deviation，强制进入 Step 4
```

### Phase A: 针对性修订

**每轮执行**:
1. 列出所有 critical/high 问题及其具体位置（引用原文）
2. 逐个修改问题段落，保持上下文不变
3. 修改后，**仅重新调用上一轮 FAIL 的 Agent**（不用全部7个）
4. 输出修订汇总：

```
┌─────────────────────────────────────────────────┐
│ 修订轮次 A-{round} - 第 {chapter_num} 章        │
├─────────────────────────────────────────────────┤
│ 修改内容: {简述修改了哪些段落/问题}               │
│ 重新审查 Agent: {列出重跑的Agent名}              │
│ 剩余 critical: {N}  |  剩余 high: {N}           │
│ 结果: {已解决/升级到Phase B}                     │
└─────────────────────────────────────────────────┘
```

5. 如果 critical = 0 且 high = 0 → 进入 Step 4
6. 如果已修订 2 轮仍有问题 → 升级到 Phase B

### Phase B: 深度润色重写

**每轮执行**:
1. 加载润色指南：
```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/polish-guide.md"
```
2. 对仍有问题的段落/场景做**深度改写**（可调整叙事结构、重写对话、重组节奏）
3. 润色红线仍然有效（不改情节走向、不改实力设定、不删伏笔）
4. 改写后，重新调用 FAIL 的 Agent 验证
5. 输出润色汇总：

```
┌─────────────────────────────────────────────────┐
│ 润色轮次 B-{round} - 第 {chapter_num} 章        │
├─────────────────────────────────────────────────┤
│ 改写范围: {简述改写了哪些场景/段落}               │
│ 重新审查 Agent: {列出重跑的Agent名}              │
│ 剩余 critical: {N}  |  剩余 high: {N}           │
│ 结果: {已解决/升级到Phase C}                     │
└─────────────────────────────────────────────────┘
```

6. 如果 critical = 0 且 high = 0 → 进入 Step 4（跳过 4.1，从 4.2 AI痕迹检测开始）
7. 如果已润色 2 轮仍有问题 → 升级到 Phase C

### Phase C: 整章重新生成

1. 输出重写决定：
```
⚠️ 经过 2 轮修订 + 2 轮润色仍有 critical/high 问题未解决
→ 决定：保留上下文包，回到 Step 2 重新生成整章
→ 未解决问题: {列出}
```
2. **保留 Step 1 的上下文包**，不需要重新搜集
3. 回到 **Step 2** 重新写章节，在写作提示中明确标注需要避免的问题
4. 重新执行完整 **Step 3** 审查（全部7个Agent）
5. 如果重写后仍有 critical/high → **记录 deviation，强制进入 Step 4**，不再循环

```
┌─────────────────────────────────────────────────┐
│ 重新生成结果 - 第 {chapter_num} 章               │
├─────────────────────────────────────────────────┤
│ 剩余 critical: {N}  |  剩余 high: {N}           │
│ 结果: {已解决/记录deviation强制继续}              │
└─────────────────────────────────────────────────┘
```

### 修复循环上限

| 阶段 | 最大轮次 | 累计审查次数 |
|------|---------|-------------|
| Phase A 修订 | 2 轮 | 2 |
| Phase B 润色 | 2 轮 | 2 |
| Phase C 重写 | 1 次 | 1 |
| **合计** | **最多 5 次额外审查** | |

超过上限后强制记录 deviation 继续，**绝不死循环**。

---

## Step 4: 最终润色 (AI痕迹 + 自然化 + 排版)

⚠️ **强制要求**: 必须按以下顺序执行全部子步骤（4.0-4.5），不可跳过。

### 4.0 加载润色指南（必须先执行）

**执行命令（不可跳过）**:
```bash
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/polish-guide.md"
cat "${CLAUDE_PLUGIN_ROOT}/skills/webnovel-write/references/writing/typesetting.md"
```

如果未执行以上命令，视为润色步骤无效。

### 4.1 修复审查问题（如经过 Phase B 可跳过此步）

> 如果经过 Step 3.5 Phase B 深度润色已解决所有 critical/high 问题，直接从 4.2 开始。

根据 Step 3 汇总表格中的 issues 列表针对性修改：

| 严重度 | 处理方式 |
|-------|---------|
| critical | **必须修复**，否则记录 deviation |
| high | 优先修复 |
| medium | 建议修复 |
| low | 可选修复 |

| 问题类型 | 修复方式 |
|---------|---------|
| OOC | 调整角色言行，符合人设 |
| POWER_CONFLICT | 修改能力描述，符合当前境界 |
| TIMELINE_ISSUE | 调整时间线描述 |
| PACING_IMBALANCE | 调整 Strand 比例 |
| LOW_COOL_POINTS | 增加爽点密度 |

### 4.2 AI痕迹检测（必须执行）

使用 Grep 工具检测以下关键词:

| 类型 | 关键词模式 | 警戒线 | 目标值 |
|-----|-----------|-------|--------|
| 总结词 | `综合\|总之\|由此可见\|总而言之` | > 1次/1000字 | 0次 |
| 列举结构 | `首先\|其次\|最后\|第一\|第二\|第三` | > 0.5次/1000字 | 0次 |
| 学术词 | `而言\|某种程度上\|本质上` | > 3次/1000字 | < 1次 |
| 因果连词 | `因为\|所以\|由于\|因此` | > 5次/1000字 | < 3次 |

如超标，必须修改后重新检测。

### 4.3 自然化处理

| 指标 | 不达标 | 达标 |
|-----|-------|------|
| 停顿词 | < 0.5次/500字 | 1-2次/500字 |
| 不确定表达 | 0次 | ≥ 2次/章 |
| 短句占比 | < 20% | 30-50% |
| 口语词 | 0次/1000字 | ≥ 2次/1000字 |

**自然化检测（必须执行）**：
- 停顿词：`嗯\|这个\|那什么\|怎么说呢`
- 不确定表达：`大概\|应该\|似乎\|好像`
- 口语词：`咋回事\|得了\|行吧\|算了`
- 短句占比：抽样 30 句（按 `。！？` 分句），≤25 字视为短句，目标 30-50%

**排版检查（必须执行）**（见 typesetting.md）：
- 对话换人换行；长段落（5行以上）拆分；场景切换留空行/分隔；章末钩子

### 4.4 润色红线

- ❌ 改变情节走向 → 违反"大纲即法律"
- ❌ 修改主角实力 → 违反"设定即物理"
- ❌ 改变人物关系 → 违反设定
- ❌ 删除伏笔 → 破坏长线剧情

### 4.5 输出检查清单（必须输出）

润色完成后，**必须输出以下检查清单**：

```
┌─────────────────────────────────────────────────┐
│ 润色检查清单 - 第 {chapter_num} 章               │
├─────────────────────────────────────────────────┤
│ [x] polish-guide.md 已加载                      │
│ [x] typesetting.md 已加载                       │
│ [x] critical issues 已修复: {是/否/无}          │
│ [x] high issues 已修复: {是/否/无}              │
├─────────────────────────────────────────────────┤
│ AI痕迹检测:                                     │
│   - 总结词: {N}次 {达标/超标}                    │
│   - 列举结构: {N}次 {达标/超标}                  │
│   - 学术词: {N}次 {达标/超标}                    │
│   - 因果连词: {N}次 {达标/超标}                  │
├─────────────────────────────────────────────────┤
│ 自然化检测:                                     │
│   - 停顿词: {N}次 {达标/偏少/偏多}               │
│   - 不确定表达: {N}次 {达标/偏少}                │
│   - 口语词: {N}次 {达标/偏少}                    │
│   - 短句占比: {X}% {达标/偏低/偏高}              │
├─────────────────────────────────────────────────┤
│ [x] 未违反润色红线                              │
│ 是否可进入 Data Agent: {是/否}                  │
└─────────────────────────────────────────────────┘
```

**Only proceed to Step 5 when:**
1. 已加载 polish-guide.md + typesetting.md
2. 已修复所有 critical/high issues（或记录 deviation）
3. AI 痕迹检测全部达标
4. 自然化/排版检查已完成（不足则记录 deviation）
5. 已输出检查清单

**输出**: 润色后的章节文件（覆盖原文件）

---

## Step 5: Data Agent 处理数据链

**调用 Data Agent**:

使用 Task 工具调用 `data-agent` subagent：

```
调用 data-agent，参数：
- chapter: {chapter_num}
- chapter_file: "正文/第{NNNN}章.md"
- review_score: {overall_score from Step 3}
- project_root: {PROJECT_ROOT}
- storage_path: .webnovel/
- state_file: .webnovel/state.json
```

**Agent 自动完成**:

1. **AI 实体提取**（Agent 内置，无需外部 LLM）
   - 从正文中语义提取实体
   - 匹配已有实体库，识别新实体
   - 识别状态变化（境界/位置/关系）

2. **实体消歧**
   - 高置信度 (>0.8): 自动采用
   - 中置信度 (0.5-0.8): 采用但记录 warning
   - 低置信度 (<0.5): 标记待人工确认

3. **写入存储**
   - 更新 state.json (精简状态)
   - 更新 index.db (v5.1 schema: entities/aliases/state_changes)
   - 注册新别名到 aliases 表

4. **AI 场景切片**
   - 按地点/时间/视角切分场景
   - 生成场景摘要

5. **向量嵌入**
   - 调用 data_modules.rag_adapter 存入向量库

6. **风格样本评估**
   - 如果 review_score > 80，提取高质量片段作为样本候选

**输出**:
```json
{
  "entities_appeared": 5,
  "entities_new": 1,
  "state_changes": 2,
  "scenes_chunked": 4,
  "uncertain": [...],
  "warnings": [...]
}
```

---

## Step 6: Git 备份

```bash
git add . && git commit -m "Ch{chapter_num}: {title}"
```

---

## 章节摘要模板

章节末尾追加：

```markdown
---
## 本章摘要
**剧情**: {主要事件}
**人物**: {角色互动}
**状态变化**: {实力/位置/关系}
**伏笔**: [埋设] / [回收]
**承接点**: {下章衔接}
**压扬比例**: 压{X}扬{Y} ({genre}类型标准)
```

---

## 错误处理

### Context Agent 失败
```
⚠️ 上下文包生成失败
→ 检查大纲是否存在
→ 检查 state.json 是否初始化
→ 手动加载必要上下文后继续
```

### 审查发现严重问题
```
⚠️ 审查发现 critical/high 级别问题
→ 自动进入 Step 3.5 修复循环
→ Phase A 修订(2轮) → Phase B 润色(2轮) → Phase C 重写(1次)
→ 超过上限仍未解决 → 记录 deviation，强制继续
```

### Data Agent 失败
```
⚠️ AI 提取失败
→ 记录 warning
→ 可选：手动添加关键实体
→ Git 备份仍然执行
```

---

## 成功标准

章节完成后，**必须输出最终验证报告**：

```
┌─────────────────────────────────────────────────┐
│ 章节完成验证 - 第 {chapter_num} 章               │
├─────────────────────────────────────────────────┤
│ 1. [x] 字数: {N}字 (3000-5000)                  │
│ 2. [x] 大纲执行: 100%                           │
│ 3. [x] 审查Agent: 5/5 已调用                    │
│ 4. [x] 审查汇总表格: 已输出                      │
│ 5. [x] polish-guide.md: 已加载                  │
│ 6. [x] AI痕迹检测: 已执行                       │
│ 7. [x] 润色检查清单: 已输出                      │
│ 8. [x] Data Agent: 成功提取 {N} 个实体          │
│ 9. [x] Git: 已提交 ({commit_hash})              │
├─────────────────────────────────────────────────┤
│ 最终状态: {成功/有deviation}                     │
└─────────────────────────────────────────────────┘
```

**验证失败处理**:
- 如有任何项目未完成，记录 deviation 原因
- deviation 不阻断工作流，但必须记录
- 连续 3 章出现相同 deviation → 标记为系统问题
