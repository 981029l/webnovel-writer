---
name: Webnovel Writer
description: 网文长篇辅助创作系统的可视化工作台——晴窗编辑部
colors:
  primary: "#2E63E8"
  primary-hover: "#2557D1"
  primary-active: "#1E48B8"
  primary-tint: "#EAF0FE"
  bg: "#F2F3F7"
  surface: "#F7F8FA"
  card: "#FFFFFF"
  border: "#E3E5EC"
  border-strong: "#C9CEDA"
  ink: "#1F2329"
  ink-secondary: "#4B5160"
  ink-muted: "#676E7C"
  success: "#178744"
  warning: "#B25E09"
  danger: "#D93A31"
typography:
  page-title:
    fontFamily: "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "1.375rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  section-title:
    fontFamily: "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.35
  card-title:
    fontFamily: "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
  data:
    fontFamily: "'IBM Plex Mono', ui-monospace, Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.4
  manuscript:
    fontFamily: "'LXGW WenKai Screen', 'Noto Serif SC', Georgia, serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 2
    letterSpacing: "0.02em"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "10px 14px"
  card:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.lg}"
    padding: "20px"
  nav-item-active:
    backgroundColor: "{colors.primary-tint}"
    textColor: "{colors.primary-active}"
    rounded: "{rounded.md}"
    padding: "9px 12px"
---

# Design System: Webnovel Writer

## 1. Overview

**Creative North Star: "晴窗编辑部"**

一间明亮的云端编辑部:灰白的工位台面、整洁的白纸、编辑手里唯一一支蓝笔。界面本身是中性、清晰、值得信任的现代协作工具(气质对标飞书/Notion),它的职责是把作者的注意力完整地交还给故事。文学气质不由界面 chrome 承担——全站只有一个地方允许「文人声音」:正文手稿区的文楷排版。其余一切,都是编辑部里安静高效的工位。

这套系统明确拒绝四样东西:满屏渐变发光的「AI 应用套壳感」、功能堆砌弹窗轰炸的「臃肿后台风」、藏起功能的「性冷淡极简风」、字小行密的「老式编辑器感」。同时告别上一代「墨控台」的深色 IDE 左轨与直角工程感——这是一个写作工作台,不是终端。

**Key Characteristics:**
- 灰底白纸的双层表面秩序:灰色画布上铺白色内容纸,层级靠表面与 1px 边框表达,不靠重阴影
- 单一无衬线家族(Inter + 思源黑体)承担全部 UI;等宽字体只做数据读数;文楷只属于正文
- 蓝笔单强调色:主操作、激活态、链接;语义色只做状态反馈
- 8px 圆角控件、12px 圆角容器、1px 边框、极轻中性阴影;悬停反馈小而干脆
- 150–250ms ease-out 过渡;动效只表达状态,不做装饰
- 明暗双主题同等公民,每个令牌都有暗色值

## 2. Colors

克制的单强调色体系(Restrained):大面积中性灰白承载一切,蓝笔只在值得点击的地方落笔。

### Primary(蓝笔)
- **蓝笔 Primary** (#2E63E8 / 暗 #3E6AE1):主按钮底色、选中态。白字对比 5.2:1(暗 5.4:1)。
- **蓝笔文本 Primary Text** (#2E63E8 / 暗 #6E9BFF):链接、激活态文字与图标。浅色下与主色同值,暗色下必须换用提亮值。
- **蓝笔按压 Primary Hover / Active** (#2557D1、#1E48B8 / 暗 #5079E8、#2F57C4)。
- **蓝笔洗 Primary Tint** (#EAF0FE / 暗 #232F52):激活态导航底、选中行底、focus 光环;其上文字用 #1E48B8(暗 #A9C3FF)。

### Neutral(工位)
| 令牌 | 浅色 | 暗色 | 用途 |
|---|---|---|---|
| bg 画布 | #F2F3F7 | #15171C | 应用最底层画布 |
| surface 台面 | #F7F8FA | #1B1E24 | 输入框底、次级面板、行悬停 |
| card 白纸 | #FFFFFF | #22252C | 内容纸、卡片、浮层 |
| border 边线 | #E3E5EC | #343842 | 1px 描边与分隔线 |
| border-strong | #C9CEDA | #4A505D | 悬停描边、可拖拽手柄 |
| ink 主墨 | #1F2329 | #E6E8ED | 标题与正文 |
| ink-secondary 次墨 | #4B5160 | #A9AFBA | 次级文字 |
| ink-muted 弱墨 | #676E7C | #8A919E | 辅助信息、占位符(对白纸 ≥4.5:1) |
| disabled | #9AA0AC | #626977 | 仅禁用态文字 |

### Semantic(状态)
| 令牌 | 浅色 | 暗色 | 淡染底(浅/暗) |
|---|---|---|---|
| success | #178744 | #3DBE6E | #E5F6EC / #17301F |
| warning | #B25E09 | #E0A23C | #FBF0DD / #332711 |
| danger | #D93A31 | #EF6A5E(文字)/#C93A32(底) | #FCEAE8 / #3A1D1A |

语义色只用于状态反馈(成功/警示/危险/未保存),不参与装饰。

### Named Rules
**蓝笔十分之一律。** 任何一屏中蓝笔(含按压、洗)占据的视觉面积不得超过 10%。它是编辑的笔,不是墙漆;稀有才有指向性。

**灰底白纸律。** 表面只有两层秩序:灰画布(bg)与白纸(card/内容纸)。白纸内部用分隔线与台面色(surface)组织内容,禁止卡片套卡片;全站不得出现第三层浮起表面(浮层/弹窗除外)。

## 3. Typography

**UI Font:** Inter(中文回退 Noto Sans SC / PingFang SC / Microsoft YaHei)——全站唯一 UI 家族
**Data Font:** IBM Plex Mono——字数、章节号、统计读数,开启 tnum
**Manuscript Font:** 霞鹜文楷 LXGW WenKai Screen(回退思源宋体)——写作区正文专用,全站唯一衬线声音

**Character:** 产品语域用单一无衬线家族,靠字重(400/500/600)与字号分层,不靠换字体制造噪音。等宽读数是「系统记得住」的可视化语言。文楷让「写小说」和「用工具」分属两个世界。

### Hierarchy(固定 rem,不做流式缩放)
- **Page Title** (600, 1.375rem, 1.3, -0.01em):页面主标题,一页一个。
- **Section Title** (600, 1.125rem, 1.35):区块标题、弹窗标题。
- **Card Title** (600, 1rem, 1.4):卡片与列表项标题。
- **Body** (400, 0.9375rem, 1.6):界面正文段落。
- **Label** (500, 0.875rem, 1.4):按钮、表单标签、导航项、表格正文。
- **Meta** (400, 0.8125rem, 1.4):时间戳、计数等辅助信息的最小字号,禁止用于成段文字。
- **Data** (mono 400, 0.8125–0.875rem, tnum):数字读数。
- **Manuscript** (400, 1.0625rem, 2.0, +0.02em):章节正文编辑区。全站唯一允许双倍行高的地方,也是最神圣的排版。

### Named Rules
**正文即主角律。** 写作区的排版永远优先于任何 chrome。若工具面板与正文争夺注意力,砍工具面板。

**四百字重律。** 中文界面文字的 font-weight 永远 ≥400。300 字重不出现在任何地方。

## 4. Elevation

层级靠表面与边框,不靠阴影堆叠。静止的白纸只有 1px 边线和一层几乎不可见的环境影;阴影只在元素真正脱离纸面时出现(下拉、拖拽、弹窗)。

### Shadow Vocabulary(全部中性墨色)
- **shadow-sm** (`0 1px 2px 0 rgb(31 35 41 / 0.05)`):静止卡片的默认存在感。
- **shadow-md** (`0 4px 12px -4px rgb(31 35 41 / 0.10)`):悬停卡片、下拉浮层。
- **shadow-lg** (`0 12px 28px -8px rgb(31 35 41 / 0.14)`):拖拽中的元素、popover。
- **shadow-xl** (`0 20px 48px -12px rgb(31 35 41 / 0.18)`):模态弹窗,最高层级。

暗色主题用纯黑基底、更高透明度(0.28/0.42/0.55/0.65)。

### Named Rules
**素影律。** 阴影永远是中性墨色的低透明度,任何组件不得使用彩色投影或发光(glow)。强调靠蓝笔本身,不靠光晕。

## 5. Components

组件性格:安静、标准、可预期。同一控件全站同一长相;反馈快(150–250ms)、形态圆润但结构方正。

### Buttons
- **Shape:** 8px 圆角矩形(告别药丸形),内边距 8px 16px,字重 500,字号 0.875rem。
- **Primary:** 蓝笔底白字,一屏至多一个。Hover 加深为 primary-hover,无位移无彩影。
- **Secondary:** 白纸底 + 1px 边线 + 次墨文字;悬停台面底、边线加深。
- **Ghost:** 透明底次墨字,悬停台面底。低优先级操作。
- **Danger:** 语义红底白字,仅用于不可逆操作。
- **Focus:** 2px 蓝笔外描边(outline),offset 2px。

### Inputs / Fields
- **Style:** 台面底(surface)+ 1px 边线 + 8px 圆角,内边距 10px 14px,字号 0.875–0.9375rem。
- **Focus:** 边线转蓝笔 + 底色转白纸 + 3px 蓝笔洗光环。
- **Placeholder:** 弱墨(≥4.5:1)。

### Cards / Containers
- **Corner Style:** 12px 圆角。
- **Background:** 白纸,置于灰画布上,靠 1px 边线界定,静止 shadow-sm。
- **Hover(可点击卡):** 边线加深 + shadow-md,位移不超过 1px。
- **Internal Padding:** 16–20px。禁止卡片套卡片。

### Content Sheet(签名组件)
工作区的「白纸」:主内容区是一张 12px 圆角、1px 边线的白色大纸,铺在灰画布上,与侧栏之间留 8–12px 呼吸缝。每个视图都生长在这张纸上——纸内用分隔线、台面色与留白组织信息,不再层层叠卡。这是「晴窗编辑部」的骨架性隐喻:侧栏是工位走廊,白纸是摊开的稿件。

### Navigation(侧栏)
- 浅色侧栏,直接坐在灰画布上(无独立底色),宽 240px,可折叠至 64px 图标态。
- 导航项 8px 圆角、字号 0.875rem/500、内边距 9px 12px;悬停台面底;激活态蓝笔洗底 + 蓝笔文本,无左缘条纹。
- 分组标题用 Meta 字号弱墨,不用全大写宽字距。

### Chips / Tags
- 台面底 + 次墨文字,6px 圆角(非药丸),0.75rem/500;语义状态用对应淡染底 + 深文字。

### Tables / Lists
- 行高 40–48px,行悬停台面底,选中行蓝笔洗底;表头 Label 字号次墨,底部 1px 边线;数字列右对齐 + mono。

### Modal / Overlay
- 白纸底、12px 圆角、shadow-xl,遮罩 rgb(15 17 21 / 0.45);出场 200ms ease-out 轻缩放(0.98→1)+ 淡入。

### Manuscript Page(签名组件)
写作区的「稿件」:居中 min(800px, 90%),正文以 Manuscript 字体双倍行高书写。这是整个产品的灵魂组件,任何改动需以「正文即主角律」为最终裁决。它是全站唯一保留文学气质的地方。

## 6. Do's and Don'ts

### Do:
- **Do** 全站图标统一 lucide-vue-next,线宽 1.5,尺寸 16/20/24px 三档。
- **Do** 每个动效提供 `prefers-reduced-motion: reduce` 降级。
- **Do** 明暗双主题同等公民:每个新增颜色必须同时定义暗色值,且分别验证对比度(正文 ≥4.5:1)。
- **Do** 交互反馈 150–250ms,缓动 ease-out 家族(`cubic-bezier(0.4, 0, 0.2, 1)` 状态过渡、`cubic-bezier(0.16, 1, 0.3, 1)` 浮层出场)。
- **Do** 同一操作全站同一控件长相;保存按钮在哪个页面都长一样。
- **Do** 空状态给出下一步动作;加载用骨架屏,不在内容中央转圈。
- **Do** 数字读数(字数、章节、进度)一律 mono + tnum,右对齐。

### Don't:
- **Don't** 「AI 应用套壳感」:满屏渐变、发光按钮、紫蓝渐变配色、✨ 魔法话术。AI 能力用结果和确定感表达。
- **Don't** 「臃肿后台风」:一屏超过一个主操作、无请求的弹窗、装饰性统计卡、面包屑堆叠。
- **Don't** 「性冷淡极简风」:常用功能不得藏进二级菜单;空状态必须可行动。
- **Don't** 「老式编辑器感」:界面正文不小于 0.875rem,写作区不小于 1.0625rem/行高 2。
- **Don't** 深色侧栏、终端/IDE 隐喻、直角工程感——上一代「墨控台」的遗产全部清除。
- **Don't** emoji 图标、原生 `alert()`。
- **Don't** 渐变文字、装饰性玻璃拟态、大于 1px 的彩色侧边条纹、彩色阴影。
- **Don't** 在蓝笔之外引入新的装饰性色相;数据可视化色板除外(单独定义,遵循 dataviz 规范)。
- **Don't** 药丸形按钮(chips 除外)、卡片套卡片、无边框纯阴影卡。

## 7. Implementation Notes

- 令牌落地在 `frontend/src/assets/main.css`:`:root` 浅色 + `[data-theme="dark"]` 暗色,主题切换由 `useTheme` composable 与 `index.html` 预挂载脚本(`wnw-theme`)驱动,保持现状。
- UI 字体由 `main.js` 导入 `@fontsource/inter`(400/500/600)+ `@fontsource/noto-sans-sc`;IBM Plex Sans 不再作为 UI 字体;Fraunces 已退役。
- 迁移期保留旧变量别名(`--cream-*`、`--ink-*`、`--terracotta`、`--accent`、`--rail-*`),全部指向新令牌;各视图改造完成后统一删除别名层。
