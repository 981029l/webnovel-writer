# Webnovel Writer

[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-purple.svg)](https://claude.ai/claude-code)

基于 Claude Code 的长篇网文辅助创作系统，解决 AI 写作中的「遗忘」和「幻觉」问题，支持 **200 万字量级** 连载创作。

---

## 目录

- [核心理念](#核心理念)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [命令详解](#命令详解)
- [双 Agent 架构](#双-agent-架构)
- [五维并行审查](#五维并行审查)
- [RAG 检索系统](#rag-检索系统)
- [题材模板](#题材模板)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [故障恢复](#故障恢复)
- [License](#license)

---

## 核心理念

### 防幻觉三定律

| 定律 | 说明 | 执行方式 |
|------|------|---------|
| **大纲即法律** | 遵循大纲，不擅自发挥 | Context Agent 强制加载章节大纲 |
| **设定即物理** | 遵守设定，不自相矛盾 | Consistency Checker 实时校验 |
| **发明需识别** | 新实体必须入库管理 | Data Agent 自动提取并消歧 |

### Strand Weave 节奏系统

三线交织的叙事节奏控制：

| Strand | 含义 | 理想占比 | 说明 |
|--------|------|---------|------|
| **Quest** | 主线剧情 | 60% | 推动核心冲突 |
| **Fire** | 感情线 | 20% | 人物关系发展 |
| **Constellation** | 世界观扩展 | 20% | 背景/势力/设定 |

**节奏红线**：
- Quest 连续不超过 5 章
- Fire 断档不超过 10 章
- 每章至少包含 2 种 Strand

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                             │
├─────────────────────────────────────────────────────────────┤
│  Skills (6个)                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │  init    │ │   plan   │ │  write   │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │  review  │ │  query   │ │  resume  │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
├─────────────────────────────────────────────────────────────┤
│  Agents (8个)                                                │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  Context Agent  │  │   Data Agent    │                   │
│  │     (读取)      │  │     (写入)      │                   │
│  └─────────────────┘  └─────────────────┘                   │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐         │
│  │ 爽点  │ │ 一致性│ │ 节奏  │ │  OOC  │ │ 连贯性│         │
│  └───────┘ └───────┘ └───────┘ └───────┘ └───────┘         │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │state.json│ │ index.db │ │vectors.db│                     │
│  │ (状态)   │ │ (索引)   │ │ (向量)   │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 前置要求

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| Python | >= 3.8 | 数据处理脚本运行环境 |
| Claude Code | 最新版 | Anthropic 官方 CLI 工具 |
| Git | 任意版本 | 版本控制和章节备份 |

### 1. 安装

```bash
# 进入你的小说项目目录
cd your-novel-project

# 克隆插件到 .claude 目录
git clone https://github.com/lingfengQAQ/webnovel-writer.git .claude

# 安装 Python 依赖
pip install -r .claude/scripts/requirements.txt
```

**Python 依赖说明**：

| 包名 | 用途 |
|------|------|
| aiohttp | 异步 HTTP 客户端，用于 Embedding/Reranker API 调用 |
| filelock | 文件锁，防止 state.json 并发写入冲突 |

### 2. 初始化项目

```bash
# 在 Claude Code 中执行
/webnovel-init
```

系统会引导你完成：
- 选择初始化模式（Quick/Standard/Deep）
- 选择题材类型
- 设计金手指/核心卖点
- 生成项目结构和设定模板

### 3. 规划大纲

```bash
# 规划第1卷大纲
/webnovel-plan 1
```

### 4. 开始创作

```bash
# 创作第1章
/webnovel-write 1
```

### 5. 质量审查（可选）

```bash
# 审查第1-5章
/webnovel-review 1-5
```

### 6. Web 界面（可选）

除了命令行方式，还可以使用可视化 Web 界面进行创作：

```bash
# 启动后端（端口 8080）
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8080

# 启动前端（新终端，端口 5173）
cd frontend
npm install  # 首次运行
npm run dev
```

打开浏览器访问 http://localhost:5173，即可使用图形界面进行：
- 项目初始化和配置
- 大纲编辑（树状图）
- 章节创作（Markdown 编辑器）
- 实体管理（角色、伏笔）
- RAG 语义检索测试

---

## 命令详解

### /webnovel-init - 项目初始化

初始化项目结构、题材模板、世界观设定。

**初始化模式**：

| 模式 | 时间 | 内容 |
|------|------|------|
| ⚡ Quick | 5分钟 | 基础结构 + 核心卖点 |
| 📝 Standard | 15-20分钟 | + 金手指设计 + 题材模板 |
| 🎯 Deep | 30-45分钟 | + 深度世界观 + 创意验证 |

**产出文件**：
- `.webnovel/state.json` - 项目状态
- `设定集/` - 世界观、力量体系、角色卡
- `大纲/总纲.md` - 故事框架

---

### /webnovel-plan [卷号] - 大纲规划

制定详细的卷大纲，规划爽点分布和节奏。

```bash
/webnovel-plan 1        # 规划第1卷
/webnovel-plan 2-3      # 规划第2-3卷
```

**产出**：
- `大纲/第N卷-详细大纲.md`
- 每章目标、爽点设计、Strand 类型
- 新增实体预告

---

### /webnovel-write [章号] - 章节创作

采用双 Agent 架构的自动化章节创作。

```bash
/webnovel-write 1       # 创作第1章
/webnovel-write 45      # 创作第45章
```

**创作流程**：

```
Step 1: Context Agent 搜集上下文
        ↓
Step 2: 生成 3000-5000 字正文
        ↓
Step 3: 5 Agent 并行审查
        ↓
Step 4: 润色 + AI 痕迹检测
        ↓
Step 5: Data Agent 提取实体/更新索引
        ↓
Step 6: Git 自动提交备份
```

**产出**：
- `正文/第N章-标题.md`
- 章节末尾自动附加摘要

---

### /webnovel-review [范围] - 质量审查

对已完成章节进行多维度深度扫描。

```bash
/webnovel-review 1-5    # 审查第1-5章
/webnovel-review 45     # 审查单章
```

**审查维度**：
- 爽点密度与质量
- 设定一致性
- 节奏 Strand 分布
- 人物 OOC 检测
- 场景连贯性

---

### /webnovel-query [关键词] - 信息查询

查询角色、境界、伏笔、系统状态等运行时信息。

```bash
/webnovel-query 萧炎         # 查询角色信息
/webnovel-query 伏笔         # 查看待回收伏笔
/webnovel-query 紧急         # 查看紧急伏笔
```

---

### /webnovel-resume - 任务恢复

在任务中断时检测中断点并提供安全恢复选项。

```bash
/webnovel-resume
```

**恢复选项**：
- 从断点继续
- 回滚到上一个安全点
- 重新开始当前步骤

---

## 双 Agent 架构

### Context Agent（上下文包工程师）

**职责**：为写作准备精准的上下文

**工作流程**：
1. 读取本章大纲，分析需要什么信息
2. 从 `state.json` 获取主角状态快照
3. 调用 `index.db` (v5.1 schema) 查询相关实体和别名
4. 调用 RAG 语义检索相关历史场景
5. 搜索设定集获取相关设定
6. 评估伏笔紧急度
7. 组装上下文包 JSON

**输出结构**：
```json
{
  "core": {
    "chapter_outline": "本章大纲",
    "protagonist_snapshot": {...},
    "recent_summaries": [...]
  },
  "scene": {
    "location_context": {...},
    "appearing_characters": [...],
    "urgent_foreshadowing": [...]
  },
  "global": {
    "worldview_skeleton": "...",
    "power_system_skeleton": "...",
    "style_contract_ref": "..."
  },
  "rag": [...],
  "alerts": {
    "disambiguation_warnings": [...],
    "disambiguation_pending": [...]
  }
}
```

---

### Data Agent（数据链工程师）

**职责**：从正文中语义化提取实体并同步状态

**工作流程**：
1. **实体提取**：识别角色/地点/物品/招式/势力
2. **实体消歧**：
   - 高置信度 (>0.8)：自动采用
   - 中置信度 (0.5-0.8)：采用但记录 warning
   - 低置信度 (<0.5)：标记待人工确认
3. **写入存储**：更新 `index.db` (entities/aliases/state_changes)
4. **场景切片**：按地点/时间/视角切分场景
5. **向量嵌入**：调用 RAG 存入向量库

**输出格式**：
```json
{
  "entities_extracted": [...],
  "state_changes": [...],
  "scenes": [...],
  "warnings": [...],
  "stats": {
    "new_entities": 3,
    "updated_entities": 2,
    "scenes_created": 4
  }
}
```

---

## 五维并行审查

| Checker | 检查内容 | 关键指标 |
|---------|---------|---------|
| **High-point Checker** | 爽点密度与质量 | 6种执行模式、30/40/30结构 |
| **Consistency Checker** | 战力/地点/时间线 | 设定即物理定律 |
| **Pacing Checker** | Strand 比例分布 | Quest/Fire/Constellation |
| **OOC Checker** | 人物言行是否符合人设 | 角色卡片对照 |
| **Continuity Checker** | 场景转换流畅度 | 伏笔回收情况 |

### 爽点六大执行模式

| 模式 | 模式标识 | 典型触发 |
|------|---------|---------|
| 装逼打脸 | Flex & Counter | 嘲讽 → 反转 → 震惊 |
| 扮猪吃虎 | Underdog Reveal | 示弱 → 暴露 → 碾压 |
| 越级反杀 | Underdog Victory | 差距 → 策略 → 逆转 |
| 打脸权威 | Authority Challenge | 权威 → 挑战 → 成功 |
| 反派翻车 | Villain Downfall | 得意 → 反杀 → 落幕 |
| 甜蜜超预期 | Sweet Surprise | 期待 → 超预期 → 升华 |

### 爽点密度基准

- **每章**：≥ 1 cool-point (任何单一模式)
- **每5章**：≥ 1 combo cool-point (2种以上模式叠加)
- **每10章**：≥ 1 milestone victory (改变主角地位的阶段性胜利)

---

## RAG 检索系统

混合检索系统，支持语义搜索历史场景：

### 架构

```
查询 → [向量检索] + [BM25关键词] → RRF融合 → Rerank排序 → Top-K结果
```

### 配置

| 组件 | 默认提供商 | 默认模型 |
|-----|----------|---------|
| Embedding | ModelScope (魔搭) | Qwen/Qwen3-Embedding-8B |
| Reranker | Jina AI | jina-reranker-v3 |

### 环境变量

```bash
# .env 文件

# Embedding 配置 (默认使用魔搭)
EMBED_API_TYPE=openai          # openai 兼容接口
EMBED_BASE_URL=https://api-inference.modelscope.cn/api-inference/v1/models/iic/nlp_corom_sentence-embedding_chinese-base
EMBED_MODEL=iic/nlp_corom_sentence-embedding_chinese-base
EMBED_API_KEY=ms-041068cc-89cd-401d-99b6-1a0d9eea31f3

# Reranker 配置
RERANK_API_TYPE=openai         # openai (兼容 Jina/Cohere)
RERANK_BASE_URL=https://api.jina.ai/v1
RERANK_MODEL=jina-reranker-v3
RERANK_API_KEY=jina_xxx
```

### 使用方式

- **Context Agent** 自动调用 RAG 检索相关历史场景
- **Data Agent** 自动将章节场景向量化存入数据库
- 支持失败重试（指数退避，最多3次）

---

## 题材模板

系统内置 10+ 种热门网文题材模板：

| 题材 | 说明 |
|------|------|
| 修仙 | 境界体系、宗门体系、秘境夺宝 |
| 系统流 | 面板设计、任务系统、奖励机制 |
| 都市异能 | 隐藏实力、家族势力、权贵互动 |
| 规则怪谈 | 规则推理、恐怖氛围、反杀怪谈 |
| 替身文 | 五阶段心理线、追妻火葬场、身份反转 |
| 多子多福 | 后宫系统、子嗣养成、系统奖励 |
| 黑暗题材 | 吞噬进化、势力建立、压扬比例 |
| ... | 更多模板持续更新 |

---

## 配置说明

### 核心配置 (`config.py`)

```python
# API 设置
embed_concurrency = 50          # 嵌入并发数
cold_start_timeout = 120        # 冷启动超时(秒)
normal_timeout = 30             # 正常超时(秒)
api_max_retries = 3             # 最大重试次数
api_retry_delay = 1.0           # 重试延迟(秒)

# 节奏红线
strand_quest_max_consecutive = 5   # Quest 最大连续章数
strand_fire_max_gap = 10           # Fire 最大断档章数

# 爽点密度
pacing_words_per_point = (1000, 2000)  # 每个爽点字数范围

# 实体置信度
extraction_confidence_high = 0.8   # 高置信度阈值（自动采用）
extraction_confidence_low = 0.5    # 低置信度阈值（待确认）

# 上下文窗口
context_recent_summaries_window = 5   # 最近摘要数量
context_max_appearing_characters = 10 # 最大出场角色数
context_max_urgent_foreshadowing = 5  # 最大紧急伏笔数
```

---

## 项目结构

```
your-novel-project/
├── .claude/                    # 插件目录
│   ├── agents/                 # 8 个专职 Agent
│   │   ├── context-agent.md    # 上下文包工程师
│   │   ├── data-agent.md       # 数据链工程师
│   │   ├── high-point-checker.md
│   │   ├── consistency-checker.md
│   │   ├── pacing-checker.md
│   │   ├── ooc-checker.md
│   │   └── continuity-checker.md
│   ├── skills/                 # 6 个核心 Skill
│   │   ├── webnovel-init/
│   │   ├── webnovel-plan/
│   │   ├── webnovel-write/
│   │   ├── webnovel-review/
│   │   ├── webnovel-query/
│   │   └── webnovel-resume/
│   ├── scripts/                # Python 脚本
│   │   ├── data_modules/
│   │   │   ├── index_manager.py    # SQLite 索引管理 (v5.1)
│   │   │   ├── rag_adapter.py      # RAG 检索层
│   │   │   ├── api_client.py       # API 客户端
│   │   │   └── config.py           # 配置管理
│   │   ├── context_pack_builder.py # 上下文包构建器
│   │   └── ...
│   ├── templates/              # 题材模板
│   │   └── genres/
│   │       ├── 修仙.md
│   │       ├── 系统流.md
│   │       ├── 替身文.md
│   │       ├── 多子多福.md
│   │       ├── 黑暗题材.md
│   │       └── ...
│   └── references/             # 写作指南
│       ├── strand-weave.md
│       ├── cool-points-guide.md
│       └── ...
├── .webnovel/                  # 运行时数据
│   ├── state.json              # 权威状态 (< 5KB)
│   ├── index.db                # SQLite 索引
│   └── vectors.db              # RAG 向量库
├── 正文/                       # 章节文件
│   ├── 第1章-标题.md
│   └── ...
├── 大纲/                       # 卷纲/章纲
│   ├── 总纲.md
│   ├── 第1卷-详细大纲.md
│   └── ...
└── 设定集/                     # 世界观/角色/力量体系
    ├── 世界观.md
    ├── 力量体系.md
    └── 角色/
        └── ...
```

---

## 故障恢复

### 索引重建

当 `index.db` 损坏或与实际数据不一致时：

```bash
# 重新处理单章
python -m data_modules.index_manager process-chapter --chapter 1 --project-root "."

# 批量重新处理
for i in $(seq 1 50); do
  python -m data_modules.index_manager process-chapter --chapter $i --project-root "."
done

# 查看索引统计
python -m data_modules.index_manager stats --project-root "."
```

### 向量重建

当 `vectors.db` 损坏或嵌入模型更换时：

```bash
# 重新索引单章
python -m data_modules.rag_adapter index-chapter --chapter 1 --project-root "."

# 查看向量统计
python -m data_modules.rag_adapter stats --project-root "."
```

### Git 回滚

每章自动创建 Git 标签，支持按章回滚：

```bash
# 查看章节标签
git tag | grep "ch"

# 回滚到第45章
git checkout ch0045
```

---

## 版本历史

### v5.1 (当前)
- SQLite 存储：entities/aliases/state_changes 迁移到 index.db
- state.json 精简至 < 5KB
- API 重试机制（指数退避）
- 6 种爽点执行模式

### v5.0
- 双 Agent 架构 (Context + Data)
- 纯正文写作，无需 XML 标签
- 5 维并行审查

---

## License

GPL v3 - 详见 [LICENSE](LICENSE)

---

## 致谢

本项目使用 **Claude Code + Gemini CLI + Codex** 配合 Vibe Coding 方式开发。

灵感来源：[Linux.do 帖子](https://linux.do/t/topic/1397944/49)

---

## 贡献

欢迎提交 Issue 和 PR！

```bash
# Fork 项目后
git checkout -b feature/your-feature
git commit -m "feat: add your feature"
git push origin feature/your-feature
```
