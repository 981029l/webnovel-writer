# CLAUDE.md

## Design Context

本项目的前端设计工作有正式规范,任何涉及 UI 的改动前先读:

- **PRODUCT.md**(项目根):产品定位、用户、品牌人格、反面教材、设计原则。定位主张是「AI 记得住 200 万字」;语域为 product(工作台工具),平台为 web。
- **DESIGN.md**(项目根):视觉规范。创意北极星是「晴窗编辑部」,飞书/Notion 式浅色协作工具风:灰底白纸双层表面 + 蓝笔单强调色 + 明暗双主题,含命名规则(蓝笔十分之一律、灰底白纸律、正文即主角律、四百字重律、素影律)与 Do's/Don'ts。
- `.impeccable/design.json`:机器可读的令牌与组件快照,供 impeccable live 面板使用。

UI 改动必须遵守 DESIGN.md 的 Named Rules 与 Don'ts;与规范冲突时,先改规范再改代码。
