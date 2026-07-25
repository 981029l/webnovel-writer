"""方案A 落地验证脚本：编译检查 + 快照/迁移 + 六槽位渲染冒烟。

只在系统临时目录里建测试项目，不触碰真实项目数据与全局包。
用法：python scripts/verify_prompt_slots.py
"""

from __future__ import annotations

import compileall
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

FILES_TO_COMPILE = [
    "backend/services/prompt_fallbacks.py",
    "backend/services/project_prompt_store.py",
    "backend/services/skill_executor.py",
    "backend/services/ai_service.py",
    "backend/routers/projects.py",
    "scripts/generate_prompt_slots.py",
]

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f"  {detail}" if detail and not ok else ""))
    if ok:
        PASS += 1
    else:
        FAIL += 1


def main() -> int:
    # 1. 编译检查
    for rel in FILES_TO_COMPILE:
        ok = compileall.compile_file(str(REPO_ROOT / rel), quiet=2)
        check(f"compile {rel}", bool(ok))

    # 2. 兜底模块自检
    from services import prompt_fallbacks as pf

    for sid, base in pf.SLOT_BASES.items():
        toks = pf.list_tokens(base)
        check(f"基底 token 有默认词表 [{sid}]", all(t in pf.DEFAULT_VOCAB for t in toks))
        check(f"兜底常量无残留 token [{sid}]", "%%" not in pf.SLOT_FALLBACKS[sid])
        missing_vars = [v for v in pf.SLOT_VARIABLES[sid] if "{" + v + "}" not in base]
        check(f"基底含全部变量 [{sid}]", not missing_vars, f"缺 {missing_vars}")

    # 3. 槽位注册
    from services import project_prompt_store as store

    slot_ids = [s["id"] for s in store.PROMPT_SLOTS]
    expected_new = [
        "outline_master", "outline_rewrite", "outline_volume", "outline_polish",
        "continuity_summary", "opening_three",
    ]
    check("槽位总数 = 14", len(slot_ids) == 14, f"实际 {len(slot_ids)}: {slot_ids}")
    check("新槽位全部注册", all(s in slot_ids for s in expected_new))
    check("meta 版本常量 = 6", store.PROMPTS_META_VERSION == 6)

    # 4. 临时项目：快照 + 版本迁移
    tmp = Path(tempfile.mkdtemp(prefix="webnovel_verify_"))
    try:
        proj = tmp / "proj"
        (proj / ".webnovel").mkdir(parents=True)
        (proj / ".webnovel" / "state.json").write_text(
            json.dumps({"project_info": {"title": "验证书", "genre": "末世", "substyle": "囤货流"},
                        "genre": "末世", "substyle": "囤货流"}, ensure_ascii=False),
            encoding="utf-8",
        )

        meta = store.ensure_project_prompts(proj, "末世", "囤货流")
        check("快照 meta 版本 = 6", meta.get("version") == store.PROMPTS_META_VERSION)
        snap_dir = proj / ".webnovel" / "prompts"
        snapped = sorted(p.name for p in snap_dir.glob("*.md"))
        check("快照 14 个槽位文件", len(snapped) == 14, f"实际 {len(snapped)}: {snapped}")

        extract_snap = (snap_dir / "extract-state.md").read_text(encoding="utf-8")
        check("提取快照为新契约", '"new_characters"' in extract_snap and '"new_entities"' not in extract_snap)
        check("提取快照含末世词汇", "异能" in extract_snap and "炼气" not in extract_snap)
        volume_snap = (snap_dir / "outline-volume.md").read_text(encoding="utf-8")
        check("大纲快照存在且非空", volume_snap.strip() != "")
        check("分卷快照含章级方法论", "章级方法论" in volume_snap and "伏笔F-01" in volume_snap)
        check("分卷快照含桶级大纲附加（末世）", "末世大纲附加要求" in volume_snap)
        check("提取快照含子风格词表（囤货流）", "囤货台账" in extract_snap)
        opening_snap = (snap_dir / "opening-three.md").read_text(encoding="utf-8")
        check("黄金三章快照含三章功能分配", "三章功能分配" in opening_snap and "{chapter}" in opening_snap)

        # 4b. 模拟 v1 旧项目：旧契约 extract-state + version 1 → 迁移
        old_proj = tmp / "old"
        old_prompts = old_proj / ".webnovel" / "prompts"
        old_prompts.mkdir(parents=True)
        (old_prompts / "extract-state.md").write_text(
            '旧模板 {core_constraints} {content}\n"new_entities": []', encoding="utf-8")
        (old_prompts / "meta.json").write_text(
            json.dumps({"version": 1, "genre": "玄幻", "substyle": "热血升级流",
                        "slots": {"extract_state": {"customized": True}}}, ensure_ascii=False),
            encoding="utf-8",
        )
        store.ensure_project_prompts(old_proj, "玄幻", "热血升级流")
        migrated = (old_prompts / "extract-state.md").read_text(encoding="utf-8")
        baks = list(old_prompts.glob("extract-state.md.bak-*"))
        check("旧契约即使 customized 也被强刷", '"new_characters"' in migrated and '"new_entities"' not in migrated)
        check("旧契约强刷前有 .bak 备份", len(baks) == 1)
        old_meta = json.loads((old_prompts / "meta.json").read_text(encoding="utf-8"))
        check("旧项目迁移后 version = 6", old_meta.get("version") == 6)
        check("旧项目迁移补齐 14 槽位", len(list(old_prompts.glob("*.md"))) >= 14)

        # 5. 渲染冒烟：六个槽位模板 + 契约块
        from services.skill_executor import SkillExecutor

        ex = SkillExecutor(project_root=proj, ai_service=None)
        dummy = {v: f"<{v}>" for sid in pf.SLOT_VARIABLES for v in pf.SLOT_VARIABLES[sid]}
        for sid in pf.SLOT_BASES:
            tmpl = ex._load_slot_template_or_fallback(sid)
            check(f"槽位模板可加载且非空 [{sid}]", bool(tmpl.strip()))
            check(f"模板无生成器标记残留 [{sid}]", "generated slot=" not in tmpl)
            rendered = ex._render_slot_template(tmpl, dummy)
            leftover = [v for v in pf.SLOT_VARIABLES[sid] if "{" + v + "}" in rendered]
            check(f"渲染后无残留变量 [{sid}]", not leftover, f"残留 {leftover}")

        # 提取契约块渲染完整性
        extract_full = ex._render_slot_template(
            ex._load_slot_template_or_fallback("extract_state"), dummy) + pf.EXTRACT_CONTRACT
        check("提取契约块九键齐全", all(k in extract_full for k in pf.EXTRACT_REQUIRED_KEYS))

        # 5b. 辅助文件族：包内生成齐全、无残留 token；按关键词条件加载冒烟
        aux_pkg = REPO_ROOT / ".claude" / "skills" / "webnovel-write" / "prompts" / "genres" / "apocalypse" / "囤货流"
        for fname in pf.AUX_FILENAMES.values():
            fp = aux_pkg / fname
            text = fp.read_text(encoding="utf-8") if fp.exists() else ""
            check(f"辅助文件生成 [{fname}]", bool(text) and "%%" not in text and "generated slot=" in text)
        battle_bundle = ex._load_scene_technique_bundle("本章大纲：主角与掠夺者在废墟交手厮杀，弹药告急")
        check("场景技巧条件加载（战斗触发）", bool(battle_bundle) and "generated slot=" not in battle_bundle)
        check("场景技巧限额（≤2 文件）", len(battle_bundle) <= 2000, f"实际 {len(battle_bundle)} 字")
        check("无触发词不注入", ex._load_scene_technique_bundle("本章大纲：主角清点仓库物资") == "")

        # 5c. 黄金三章注入条件（槽位模板渲染冒烟已含 opening_three）
        o3 = ex._render_slot_template(
            ex._load_slot_template_or_fallback("opening_three"),
            {"chapter": 2, "genre": "末世", "substyle": "囤货流"},
        )
        check("黄金三章渲染含三章功能与压迫-反击", "三章功能分配" in o3 and "压迫-反击" in o3)

        # 分卷契约块与映射共渲染（v6：卷标题用全卷范围，覆盖范围用批次范围）
        vol_contract = ex._render_slot_template(pf.OUTLINE_VOLUME_CONTRACT, {
            "volume": 2, "start_chapter": 31, "end_chapter": 45, "chapters_count": 15,
            "vol_start_chapter": 31, "vol_end_chapter": 90})
        check("分卷契约块变量渲染", "{volume}" not in vol_contract and "第 31 章到第 45 章" in vol_contract)
        check("契约卷标题用全卷范围", "第 31-90 章" in vol_contract)
        check("契约禁止过程性段落", "本批概览" in vol_contract)

        # 分批续写契约（v4）
        vol_cont = ex._render_slot_template(pf.OUTLINE_VOLUME_CONTRACT_CONT, {
            "volume": 2, "start_chapter": 16, "end_chapter": 30, "chapters_count": 15})
        check("续写批次契约渲染", "禁止输出卷标题行" in vol_cont and "第 16 章" in vol_cont)

        # 玄幻开局禁令落包（v4/v5：分卷 + 总纲 + 重写三处都要有）
        xh_pkg = (REPO_ROOT / ".claude" / "skills" / "webnovel-write" / "prompts"
                  / "genres" / "xuanhuan" / "热血升级流")
        for fname in ("outline-volume.md", "outline-master.md", "outline-rewrite.md"):
            text = (xh_pkg / fname).read_text(encoding="utf-8")
            check(f"玄幻开局禁令 [{fname}]", "欠债催缴" in text)
        rewrite_text = (xh_pkg / "outline-rewrite.md").read_text(encoding="utf-8")
        check("重写模板含违禁桥段修正令", "禁止原样保留" in rewrite_text)

        # 6. 死代码确认
        check("execute_state_extraction 已删除", not hasattr(ex, "execute_state_extraction"))
        from services.ai_service import AIService
        check("ai_service.generate_outline 已删除", not hasattr(AIService, "generate_outline"))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n结果：{PASS} 通过 / {FAIL} 失败")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
