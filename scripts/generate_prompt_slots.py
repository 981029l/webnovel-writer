"""子风格独立包提示词槽位生成器（方案A）。

为 `.claude/skills/webnovel-write/prompts/genres/<bucket>/<子风格>/` 下的
37 个子风格包生成/更新 6 个槽位文件：

    outline-master.md   总纲初稿
    outline-rewrite.md  总纲重写
    outline-volume.md   分卷详细大纲
    outline-polish.md   大纲润色
    extract-state.md    实体提取（重写旧死契约文件）
    continuity-summary.md  连续性摘要

内容 = backend/services/prompt_fallbacks.py 的模板基底
       + 桶级词汇表（BUCKET_VOCAB） + 子风格微调（SUBSTYLE_OVERRIDES）。

幂等策略：
- 生成文件首行写标记  <!-- generated slot=<id> gen_hash=<sha1[:10]> -->
- 重跑时：无文件 → 写入；有标记且正文哈希与标记一致（未手改）→ 允许覆盖更新；
  哈希不一致（手改过）→ 跳过并报告，--force 才覆盖。
- extract-state.md 特例：旧文件服务于已删除的死代码链路（旧 JSON 契约
  new_entities/state_updates），无标记也直接重写（首轮迁移）。

用法：
    python scripts/generate_prompt_slots.py [--dry-run] [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from services.prompt_fallbacks import (  # noqa: E402
    AUX_BASES,
    AUX_FILENAMES,
    DEFAULT_VOCAB,
    EXTRACT_REQUIRED_KEYS,
    SLOT_BASES,
    SLOT_FILENAMES,
    SLOT_VARIABLES,
    fill_vocab,
)

GENRES_DIR = REPO_ROOT / ".claude" / "skills" / "webnovel-write" / "prompts" / "genres"

MARKER_RE = re.compile(r"^<!--\s*generated slot=(\S+) gen_hash=([0-9a-f]+)\s*-->\s*\n")


# ---------------------------------------------------------------------------
# 桶级示例卷（用于组装 MASTER/REWRITE 格式示例）
# ---------------------------------------------------------------------------

BUCKET_VOLUME_EXAMPLE: Dict[str, Dict[str, str]] = {
    "xuanhuan": {
        "title": "外门崛起",
        "conflict": "身怀至宝的少年在外门夹缝求生，资源被势利执事层层克扣",
        "coolpoint": "炼气连破三层碾压同辈，当众打脸克扣灵石的执事",
        "climax": "宗门大比技惊四座，拜入内门并获长老亲传",
    },
    "apocalypse": {
        "title": "末日七十二小时",
        "conflict": "病毒爆发城市封锁，主角带家人在断水断粮中抢出一条生路",
        "coolpoint": "提前囤积的物资与首个觉醒异能，在尸群围城中救下整栋楼",
        "climax": "率幸存者突围抵达军方安全区，成为民间队伍话事人",
    },
    "alt-history": {
        "title": "寒门入仕",
        "conflict": "寒门子弟卷入州府赋税亏空案，被上官当作顶罪的替死鬼",
        "coolpoint": "以一手新式账法当堂揭破亏空真相，反将构陷者军法处置",
        "climax": "御前对策震动朝野，外放实权县令，携新政赴任",
    },
    "dark": {
        "title": "泥沼求生",
        "conflict": "主角从尸堆里爬出，在弱肉强食的底层用最小代价换活命机会",
        "coolpoint": "借刀杀人除掉压在头顶的地头蛇，第一次尝到掌控命运的滋味",
        "climax": "踩着仇人的尸体拿到进入上层的门票，代价是再也回不去的东西",
    },
    "dog-blood-romance": {
        "title": "错嫁豪门",
        "conflict": "替姐出嫁的女主被丈夫误当仇人之女，婚内冷暴力与白月光步步紧逼",
        "coolpoint": "身世反转当众揭穿白月光设局，男主追悔莫及跪求原谅",
        "climax": "离婚协议甩在脸上转身离开，男主雨夜追妻开启火葬场",
    },
    "folk-horror": {
        "title": "白事入门",
        "conflict": "少年被迫接下祖传白事手艺，第一场活就撞上不干净的主家",
        "coolpoint": "靠师父留下的三条规矩硬闯灵堂，送走缠了主家三代的老怨",
        "climax": "查明村中连环白事的根由，代价是自折三年阳寿",
    },
    "mystic-sequence": {
        "title": "序列之门",
        "conflict": "主角误饮魔药成为非凡者，被教会与秘密组织同时盯上",
        "coolpoint": "首次完整扮演序列角色压下失控，反手设局擒获追杀者",
        "climax": "晋升序列8，揭开自身来历的第一层迷雾",
    },
    "period-drama": {
        "title": "重回侯府",
        "conflict": "嫡女重生归来，面对夺她姻缘害她性命的继母与庶妹",
        "coolpoint": "当众拆穿庶妹伪造的嫁妆单子，夺回管家权",
        "climax": "继母母族倒台，女主执掌中馈并定下贵婿",
    },
    "realistic": {
        "title": "绝地翻身",
        "conflict": "被裁员背锅的主角负债百万，从摆摊起步寻找翻身机会",
        "coolpoint": "抓住供应链缺口第一桶金到账，当面回绝老东家的低价挖角",
        "climax": "公司拿到首轮融资，反手收购前东家核心业务线",
    },
    "rules-mystery": {
        "title": "入住第一夜",
        "conflict": "主角被困诡异公寓，入住须知与楼道告示互相矛盾",
        "coolpoint": "用两条规则互相卡死伪装成管理员的存在，救下同层住户",
        "climax": "验证出通往二层的真规则，带队突破首个安全区",
    },
    "scifi": {
        "title": "废土起航",
        "conflict": "殖民舰坠毁废土，主角以残破机甲护住幸存者营地",
        "coolpoint": "修复原型机甲首战击溃掠夺者车队，废土黑市一战成名",
        "climax": "夺回舰船核心，营地升级为有防御工事的定居点",
    },
    "zhihu-short": {
        "title": "摊牌",
        "conflict": "婚礼前夜我发现未婚夫和伴娘的聊天记录，选择按兵不动",
        "coolpoint": "婚礼致辞环节当众放出录音，宾客哗然中我笑着退场",
        "climax": "彩礼一分不退、婚房过户到手，反转揭出我早有准备",
    },
}


def _master_format_example(bucket: str) -> str:
    ex = BUCKET_VOLUME_EXAMPLE[bucket]
    return (
        f"   ## 第X卷 《{ex['title']}》（约XX章）\n"
        f"   - **核心冲突**：{ex['conflict']}\n"
        f"   - **关键爽点**：{ex['coolpoint']}\n"
        f"   - **卷末高潮**：{ex['climax']}"
    )


def _rewrite_format_example(bucket: str) -> str:
    ex = BUCKET_VOLUME_EXAMPLE[bucket]
    return (
        f"## 第1卷 《{ex['title']}》（约50-60章）\n"
        f"- **预计章数**：50-60章\n"
        f"- **核心冲突**：{ex['conflict']}\n"
        f"- **关键爽点**：{ex['coolpoint']}\n"
        f"- **卷末高潮**：{ex['climax']}"
    )


# ---------------------------------------------------------------------------
# 桶级词汇表（12 桶；未列出的 token 回退 DEFAULT_VOCAB）
# ---------------------------------------------------------------------------

_VOLUME_NUMERIC_TAIL = (
    "\n❌ 错误示例：\n"
    "   - \"死伤惨重\"（太模糊！必须写具体数字）\n"
    "   - \"消耗了大量资源\"（必须说明消耗了什么、多少）"
)

BUCKET_VOCAB: Dict[str, Dict[str, str]] = {
    "xuanhuan": {
        "NAMING_HINT": "（本题材命名语系：宗门、洞府、法器、丹药、道号、秘境等仙侠词汇。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【伤亡】外门弟子阵亡约30人，护矿长老陨落1名\n"
            "   - 【消耗】灵石消耗2000块，回元丹用去5枚、剩余3枚\n"
            "   - 【收益】获得地阶功法一部、灵石5000块，境界突破至筑基中期\n"
            "   - 【状态】主角经脉受损（需闭关7日恢复）" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "外门弟子/内门长老/散修/魔道妖人/世家子弟等",
        "REALM_LABEL": "境界",
        "REALM_DESC": "当前境界（如炼气三层、筑基初期、金丹圆满）",
        "LOCATION_DESC": "当前地点（如青云城、外门演武场、坊市）",
        "TIER_DESC": "品级（如：黄阶、玄阶、地阶上品、天阶）",
        "TECH_LABEL": "功法/武技",
        "TECH_TIER_DESC": "等级（如：黄阶、玄阶、地阶、天阶）",
        "ORG_TYPE_DESC": "类型（宗门/世家/王朝/魔道/商会等）",
        "LOC_TYPE_DESC": "类型（城池/宗门/秘境/山脉/坊市等）",
        "CHANGE_EG": "如突破筑基、走火入魔、重伤闭关",
        "RESOURCE_EG": "如灵石、丹药、贡献点、气运",
        "UNIT_DESC": "队伍名称（如'外门巡山队'、'护矿弟子'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **人员伤亡**：弟子、修士、凡人的死亡/受伤人数（必须提取！）\n"
            "2. **灵石/丹药/贡献点**：增减数值和原因\n"
            "3. **境界与寿元**：主角与重要角色的境界变化、寿元损耗\n"
            "4. **战力资产变化**：法器损毁、阵法破损、符箓消耗等"
        ),
        "CONTINUITY_EXTRA": (
            "- 境界与灵力：主角当前灵力余量、伤势对战力的影响\n"
            "- 消耗品存量：本章用掉的丹药/符箓/灵石必须记数"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【玄幻大纲附加要求】\n"
            "1. 升级节点写全四要素：触发条件、获得奖励、代价消耗、对局势的影响；升级频率保持前密后疏。\n"
            "2. 冲突按四层次逐卷抬升：个人恩怨 → 家族/宗门 → 势力版图 → 世界级危机。\n"
            "3. 每次大境界突破前，安排一次濒死绝境或大机缘铺垫。\n"
            "4. 开局与前期压迫必须用玄幻情境（灵根被夺/婚约被退/测灵淘汰危机/功法资源被扣/大比出局），"
            "禁止用「欠债催缴」「讨债上门」等市井桥段立主角困境；"
            "主角背景与剧情中不得出现「欠债/债务/欠灵石/催缴」元素，压迫一律改用宗门规矩、配额克扣、考核淘汰等玄幻手段。"
        ),
        "OPENING_HOOK_EG": "（如：废材当众被退婚/夺灵根，同一章内金手指苏醒给出第一个甜头。禁止欠债催缴式开局。）",
        "COMBAT_LABEL": "斗法/战斗场面",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 一对一斗法：重法术对轰节奏与灵力余量此消彼长；以弱胜强：重战术、地利与信息差；\n"
            "- 群战：重阵法配合与视角切换；秘境险境：重环境杀机与规则限制。"
        ),
    },
    "apocalypse": {
        "NAMING_HINT": "（本题材命名语系：庇护所、安全区、变异体、物资点、异能代号等末世词汇；禁用仙侠词。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【伤亡】幸存者小队折损4人，剩余11人\n"
            "   - 【消耗】弹药耗去120发、剩约80发；食物仅够5天\n"
            "   - 【收益】搜出药品一箱（抗生素20盒）、柴油200升\n"
            "   - 【状态】队长被抓伤（12小时内确认是否感染）" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "幸存者/军方军官/佣兵/掠夺者头目/基地管理层等",
        "REALM_LABEL": "异能等级/进化阶位",
        "REALM_DESC": "当前异能等级或进化阶位（如觉醒一阶、二级强化者、三阶变异）",
        "LOCATION_DESC": "当前地点（如废弃超市、庇护所B区、高速收费站）",
        "TIER_DESC": "等级（如：民用级、军用级、战略物资级）",
        "TECH_LABEL": "异能/技能",
        "TECH_TIER_DESC": "等级（如：一阶、二阶、强化系/精神系）",
        "ORG_TYPE_DESC": "类型（庇护所/军方残部/佣兵团/掠夺者/幸存者聚落等）",
        "LOC_TYPE_DESC": "类型（安全区/废墟/物资点/感染区等）",
        "CHANGE_EG": "如异能觉醒、被感染、断粮、重伤失血",
        "RESOURCE_EG": "如食物（按天数）、饮用水、弹药、燃油、药品",
        "UNIT_DESC": "队伍名称（如'巡逻小队'、'物资搜索队'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **幸存者伤亡**：死亡/受伤/感染人数（必须提取！）\n"
            "2. **物资账本**：食物、水、弹药、药品、燃油的消耗与入账（记具体数量）\n"
            "3. **异能与体力**：等级变化、体力透支、感染进程\n"
            "4. **载具与工事**：车辆损坏、防御工事状态"
        ),
        "CONTINUITY_EXTRA": (
            "- 物资账本：食物、水、弹药、药品当前存量（有数字必须记录）\n"
            "- 威胁态势：本章出现的变异体是否清除、尸潮/敌对势力动向"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【末世大纲附加要求】\n"
            "1. 物资线全程可见：关键章节标注食物/水/弹药/药品的收支与存量拐点（断粮危机是天然压抑点）。\n"
            "2. 威胁升级线：尸潮/变异体强度与人祸（掠夺者、内斗）交替施压，不许只打丧尸。\n"
            "3. 庇护所里程碑：藏身点→据点→聚落的每次升级都是卷级爽点。"
        ),
        "OPENING_HOOK_EG": "（如：末日爆发前 24 小时的异常征兆，主角率先囤货/觉醒，第一波危机中显出先手优势。）",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 尸潮阻击：重弹药消耗与防线崩点；变异体猎杀：重弱点发现与代价；\n"
            "- 人类火并：重掩体、偷袭与人心；突围转移：重护送队形与断后抉择。"
        ),
        "SCENE_FLAVOR": "场景以废弃与残留物讲故事：超市货架的空缺顺序、墙上涂改的告示都是信息。",
    },
    "alt-history": {
        "NAMING_HINT": "（本题材命名语系：官职、爵位、年号、州府、军镇、粮秣等古代词汇；严禁现代词入名。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【伤亡】前锋营阵亡约800人，被俘200余，溃散过半\n"
            "   - 【消耗】粮草耗去三千石，仅够大军十日之用\n"
            "   - 【收益】抄没赃银十二万两，得战马四百匹\n"
            "   - 【状态】主角中箭（左肩，军医断言须静养半月）" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "朝臣/武将/幕僚/世家子/商贾/流民首领等",
        "REALM_LABEL": "官职/地位",
        "REALM_DESC": "当前官职或地位（如从七品县丞、游击将军、侯府世子）",
        "LOCATION_DESC": "当前地点（如京城东市、雁门关、江南道）",
        "TIER_DESC": "规格（如：御赐之物、传国重器、军械制式）",
        "TECH_LABEL": "武艺/技艺",
        "TECH_TIER_DESC": "水准（如：军中枪法、大内秘传、家传绝学）",
        "ORG_TYPE_DESC": "类型（朝廷/藩镇/世家/商帮/军镇/江湖门派等）",
        "LOC_TYPE_DESC": "类型（都城/州府/关隘/军镇/村落等）",
        "CHANGE_EG": "如升官晋爵、贬官流放、重伤、身份败露",
        "RESOURCE_EG": "如白银、粮草、兵员、田亩、气运",
        "UNIT_DESC": "部队名称（如'前锋营'、'夜不收'、'家丁队'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **兵员伤亡**：阵亡、被俘、溃散人数（必须提取！）\n"
            "2. **钱粮账目**：白银、粮草、军械的收支数目\n"
            "3. **官爵与声望**：官职爵位变动、朝野风评\n"
            "4. **军资损耗**：城防、战马、器械的折损"
        ),
        "CONTINUITY_EXTRA": (
            "- 兵力钱粮：本章过后各方兵员、粮草、白银存量\n"
            "- 朝局态势：圣意向背、党争立场、把柄与人情债的变化"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【历史架空大纲附加要求】\n"
            "1. 权谋线与军事线双轨标注：朝堂博弈（把柄/站队/圣意）与战场胜负（兵员/粮草/城池）交替推进。\n"
            "2. 主角官爵/地位晋升节点明确标注，每次晋升必有政敌反扑。\n"
            "3. 大事件入纲：写明关键事件的年份背景锚点，保持史实感。"
        ),
        "OPENING_HOOK_EG": "（如：穿越即陷死局——顶罪/被贬/大军压境，主角用超时代见识撬开第一道生机。）",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 阵战：重兵种调度、令旗与战场大势；攻守城：重器械、粮道与士气；\n"
            "- 江湖搏杀：重招式往来与狠劲；朝堂对质：重礼法框架下的文斗机锋。"
        ),
        "DIALOGUE_FLAVOR": "对话必须符合古代语域与身份等差：称谓、敬语、避讳不可错，严禁现代词汇。",
    },
    "dark": {
        "NAMING_HINT": "（本题材基调冷硬写实，命名贴合具体世界观；禁止轻浮网络词。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【伤亡】同行七人只活下来3个，皆带伤\n"
            "   - 【代价】主角断了两根手指，欠下地头蛇一条命的人情\n"
            "   - 【收益】夺得过冬口粮半月份、御寒衣物3件\n"
            "   - 【状态】旧伤未愈再添内伤（战力折半，约十日）" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "狱友/仇家/上位者/线人/同伙等",
        "REALM_LABEL": "实力层级",
        "REALM_DESC": "当前实力层级或身份（用本书体系的说法，如血奴、执事、堂主）",
        "LOCATION_DESC": "当前地点（如下城区、刑房、废弃矿坑）",
        "TIER_DESC": "等级（用本书世界观的分级说法）",
        "TECH_LABEL": "手段/功法",
        "TECH_TIER_DESC": "等级（用本书世界观的分级说法）",
        "ORG_TYPE_DESC": "类型（帮派/牢营/教派/上位者府邸等）",
        "LOC_TYPE_DESC": "类型（贫民窟/矿坑/牢狱/黑市等）",
        "CHANGE_EG": "如残疾、背叛、上位、身份暴露",
        "RESOURCE_EG": "如口粮、药品、筹码、人手",
        "UNIT_DESC": "团伙/队伍名称（用正文中的称呼）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **死亡与代价**：谁死了、主角为达成目标付出了什么（必须记录！）\n"
            "2. **筹码把柄**：新到手/新易手的筹码、把柄、人情\n"
            "3. **人手资源**：可用人手、口粮药品存量\n"
            "4. **伤势后遗**：伤情及其对行动力的影响"
        ),
        "CONTINUITY_EXTRA": (
            "- 代价清单：主角为目标付出的代价（伤、债、把柄）逐条记录\n"
            "- 敌我暗账：谁知道主角的秘密、谁在暗中布局"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【黑暗流大纲附加要求】\n"
            "1. 每个爽点标注代价：主角得到什么、付出什么（伤/债/把柄/人性）；无代价的胜利不许出现。\n"
            "2. 背叛与反噬节点前置规划：谁会背叛、何时反噬、主角留了什么后手。\n"
            "3. 压抑段允许更长，但兑现时的反击烈度必须加倍。"
        ),
        "OPENING_HOOK_EG": "（如：主角从尸堆/牢狱睁眼，世界规则残酷直给，第一个选择就要付出代价。）",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 生死搏杀：重狠劲与代价，赢也要脱层皮；围杀脱身：重地形与弃子；\n"
            "- 阴谋反制：重后手揭晓次序；威逼对峙：重压迫感的层层加码，不写酷刑细节堆砌。"
        ),
        "EMOTION_FLAVOR": "本题材情绪表达吝啬而致命：越痛越冷，煽情是禁忌。",
    },
    "dog-blood-romance": {
        "NAMING_HINT": "（本题材命名语系：豪门、集团、旧宅、婚约等都市言情词汇；人名贴合华语都市。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【误会】男主亲眼\"目睹\"女主与旧识拥抱，误会+1（共3个未解）\n"
            "   - 【筹码】女主拿到婆婆挪用公款的转账凭证（金额870万）\n"
            "   - 【财产】离婚协议：房产归女主、股权分割15%\n"
            "   - 【状态】女主确诊胃溃疡（住院一周，男主不知情）" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "正牌未婚妻/白月光/恶婆婆/竹马/私生子等",
        "REALM_LABEL": "身份地位",
        "REALM_DESC": "当前身份地位（如集团继承人、私生女、落魄千金）",
        "LOCATION_DESC": "当前地点（如老宅、医院VIP病房、订婚宴现场）",
        "TIER_DESC": "价值（如：传家之物、定情信物、天价拍品）",
        "TECH_LABEL": "技能/专长",
        "TECH_TIER_DESC": "水准（如：业内顶尖、家传手艺）",
        "ORG_TYPE_DESC": "类型（豪门家族/集团/圈子/世交等）",
        "LOC_TYPE_DESC": "类型（宅邸/公司/会所/学校/医院等）",
        "CHANGE_EG": "如误会加深、身世曝光、断绝关系、旧病复发",
        "RESOURCE_EG": "如股权、财产、名声、人情、证据",
        "UNIT_DESC": "群体称呼（如'家族长辈们'、'董事会'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **情感债与误会账**：谁又欠了谁、哪个误会加深或解开（逐条记录！）\n"
            "2. **身世与秘密**：新暴露的身世线索、知情人范围\n"
            "3. **财产股权**：财产、股权、抚养权的变动数额\n"
            "4. **健康状态**：旧疾、怀孕、失忆等身体变化"
        ),
        "CONTINUITY_EXTRA": (
            "- 误会链：当前每个未解开的误会、各方信息差\n"
            "- 情感温度：主要CP当前关系温度、最后一次互动的余波"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【狗血言情大纲附加要求】\n"
            "1. 误会链条目化：【误会M-01】起因第X章 / 加深第Y章 / 解开第Z章；同一时间未解误会保持 2-3 个。\n"
            "2. 虐点按「铺垫→升级→细节放大→反转融合」标注节点；虐后 3 章内必须回甜或反击。\n"
            "3. 身世/秘密类反转提前埋 2 处以上线索，做到意料之外情理之中。"
        ),
        "OPENING_HOOK_EG": "（如：婚礼/葬礼/产房门口的背叛现场直击，女主当场立下反击的第一步。）",
        "COMBAT_LABEL": "对峙/撕破脸场面",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 当众对质：重围观反应与信息炸点的投放顺序；家宴/婚宴摊牌：重体面之下的暗流与破局一击；\n"
            "- 谈判交锋：重筹码亮出的次序与底牌时机；舆论反杀：重证据链释放节奏与人心逆转。"
        ),
        "EMOTION_FLAVOR": "本题材情绪浓度可以拉满，但爆发前的压抑铺垫必须扎实；虐点之后 3 章内必须回甜或反击。",
    },
    "folk-horror": {
        "NAMING_HINT": "（本题材命名语系：白事、香火、规矩、堂口、阴宅等民俗词汇。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【人命】村里又没了2人，皆是寅时咽气\n"
            "   - 【代价】主角折了三年阳寿，左眼见阴之力弱了三分\n"
            "   - 【消耗】糯米用去半袋、朱砂见底，黑狗血仅剩一碗\n"
            "   - 【规矩】新立规矩：过桥不回头；犯者立死" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "师父/同门/主家/阴差/被附身者等",
        "REALM_LABEL": "道行/师承",
        "REALM_DESC": "当前道行或师承身份（如入门学徒、掌坛师傅、三代传人）",
        "LOCATION_DESC": "当前地点（如灵堂、义庄、村口老槐树下）",
        "TIER_DESC": "规格（如：开过光、传了三代、阴物）",
        "TECH_LABEL": "手艺/法门",
        "TECH_TIER_DESC": "深浅（如：糊纸、扎灵、开路、镇物）",
        "ORG_TYPE_DESC": "类型（堂口/手艺世家/村落/阴差衙门等）",
        "LOC_TYPE_DESC": "类型（村落/阴宅/义庄/坟地/庙宇等）",
        "CHANGE_EG": "如冲撞脏东西、折阳寿、破了规矩、结了阴亲",
        "RESOURCE_EG": "如香火、纸钱、糯米朱砂、阳寿、人情",
        "UNIT_DESC": "群体称呼（如'白事班子'、'村里人'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **人命与阳寿**：谁没了、谁折寿（必须记录！）\n"
            "2. **规矩台账**：新立/新犯的规矩及其代价\n"
            "3. **法器供物**：香火、纸钱、糯米朱砂等消耗\n"
            "4. **邪祟状态**：封了/跑了/结了怨、期限几何"
        ),
        "CONTINUITY_EXTRA": (
            "- 规矩台账：当前必须遵守的每条规矩、犯规的代价\n"
            "- 怨怼未了：本章招惹/安抚的存在，其诉求与期限"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【民俗恐怖大纲附加要求】\n"
            "1. 规矩台账入纲：每条规矩标注 立规第X章 / 犯规代价 / 破解或补救第Y章。\n"
            "2. 白事/仪式场面是本题材的高潮章，前后各配一章铺垫与余波。\n"
            "3. 每卷至少一次「代价结算」：阳寿/香火/人情的支出明细。"
        ),
        "OPENING_HOOK_EG": "（如：第一场白事就撞上不干净的主家，师父留下的三条规矩救了主角一命。）",
        "COMBAT_LABEL": "斗法/驱邪场面",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 摆坛驱邪：重仪轨步骤与差错代价；斗法对峙：重香火道行的此消彼长；\n"
            "- 逃亡周旋：重规矩边界内的自保；镇物封印：重封而不灭的后患与代价结算。"
        ),
        "EMOTION_FLAVOR": "恐惧优先于悲伤：情绪场景多与规矩、亏欠、因果绑定，哭灵有哭灵的规矩。",
        "SCENE_FLAVOR": "场景以民俗器物与禁忌标记营造不安：白幡、长明灯、贡桌摆向皆可作画面锚点。",
    },
    "mystic-sequence": {
        "NAMING_HINT": "（本题材命名语系：序列、途径、仪式、非凡特性、教会等神秘学词汇。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【伤亡】值夜者小队折损2人，1人被污染需隔离\n"
            "   - 【消耗】金镑支出35镑购魔药材料，存款余120镑\n"
            "   - 【收益】缴获封印物一件（负面效应：夜半低语）\n"
            "   - 【状态】主角失控度上升（出现幻听，需扮演法压制）" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "非凡者/教会执事/秘密结社成员/普通人等",
        "REALM_LABEL": "序列",
        "REALM_DESC": "当前序列与途径（如序列9 占卜家、序列7 魔术师）",
        "LOCATION_DESC": "当前地点（如下城区公寓、教会密室、灰雾之上）",
        "TIER_DESC": "等级（如：非凡物品、2级封印物、神器）",
        "TECH_LABEL": "非凡能力/仪式",
        "TECH_TIER_DESC": "对应序列（如：序列8能力、途径仪式）",
        "ORG_TYPE_DESC": "类型（教会/秘密组织/贵族/侦探社等）",
        "LOC_TYPE_DESC": "类型（城区/秘境/仪式场/历史遗迹等）",
        "CHANGE_EG": "如晋升序列、失控加重、被污染、身份败露",
        "RESOURCE_EG": "如金镑、魔药材料、封印物、灵性材料",
        "UNIT_DESC": "队伍名称（如'值夜者小队'、'机动小组'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **人员伤亡失踪**：死亡、失踪、被污染人数（必须提取！）\n"
            "2. **金钱材料账**：金镑收支、魔药配方材料的获取与消耗\n"
            "3. **序列与失控**：晋升进度、失控度/污染度变化\n"
            "4. **收容台账**：封印物/非凡物品的获取、移交、失窃"
        ),
        "CONTINUITY_EXTRA": (
            "- 失控与污染：主角当前精神状态、失控征兆\n"
            "- 收容台账：持有的封印物/非凡物品及其负面效应"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【神秘序列大纲附加要求】\n"
            "1. 序列晋升节点写全：材料收集 → 仪式 → 消化期 → 失控风险；晋升章与大战章错开。\n"
            "2. 组织线（教会/结社）与个人调查线双轨交替，信息按「碎片→拼图→真相」三段释放。\n"
            "3. 每卷标注收容物/非凡物品的取得与其负面效应发作节点。"
        ),
        "OPENING_HOOK_EG": "（如：误饮魔药/继承遗物后第一次失控征兆，神秘敲门声在章末响起。）",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 非凡战斗：重能力组合与序列克制；仪式对抗：重步骤抢时与材料损耗；\n"
            "- 失控压制：重扮演法与心理防线；围捕逃脱：重身份掩护与街巷地形。"
        ),
        "SCENE_FLAVOR": "场景异常要可复查：读者回看时能发现早已存在的违和细节。",
    },
    "period-drama": {
        "NAMING_HINT": "（本题材命名语系：位份、诰命、嫁妆、陪房、宫规等古代宅门词汇。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【权柄】管家权易主：对牌钥匙从继室手中交到女主房里\n"
            "   - 【银钱】查抄庄子亏空白银三千两，追回一千二百两\n"
            "   - 【人手】拔除继母安插的眼线2人，新收买粗使婆子1人\n"
            "   - 【状态】庶妹禁足佛堂三月，月例减半" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "嫡母/庶妹/婆母/陪房嬷嬷/对家妃嫔等",
        "REALM_LABEL": "位份/地位",
        "REALM_DESC": "当前位份或地位（如嫡次女、贵妾、正五品诰命、昭仪）",
        "LOCATION_DESC": "当前地点（如荣安堂、西跨院、御花园）",
        "TIER_DESC": "规格（如：御赐、内造之物、嫁妆头面）",
        "TECH_LABEL": "本事/技艺",
        "TECH_TIER_DESC": "水准（如：管家理事、女红厨艺、宫廷礼仪）",
        "ORG_TYPE_DESC": "类型（府邸/宫廷派系/母族/姻亲等）",
        "LOC_TYPE_DESC": "类型（院落/正堂/宫殿/庄子/铺面等）",
        "CHANGE_EG": "如晋位、禁足、失宠、有孕、被夺管家权",
        "RESOURCE_EG": "如月例银子、嫁妆、庄子铺面、人脉",
        "UNIT_DESC": "群体称呼（如'陪房下人'、'各房女眷'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **位份权柄**：晋位/降位、管家权/宫权归属（必须记录！）\n"
            "2. **银钱产业**：月例、嫁妆、庄铺收益的具体数目\n"
            "3. **人手布局**：安插/拔除的眼线与心腹\n"
            "4. **把柄人情**：新抓的把柄、新欠的人情"
        ),
        "CONTINUITY_EXTRA": (
            "- 把柄与眼线：各方手里的把柄、安插的眼线现状\n"
            "- 孕产病症：有孕/病中角色的进度与真伪"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【宅斗宫斗大纲附加要求】\n"
            "1. 权柄线明确标注：管家权/宫权/位份的每次易手都是节点章。\n"
            "2. 对手按梯度排布：刁奴 → 庶出 → 继室/宠妃 → 家族/圣意，一卷收拾一层。\n"
            "3. 把柄与人情条目化：谁握谁的把柄、何章使用；宴会/节庆是天然冲突舞台，每卷至少两场。"
        ),
        "OPENING_HOOK_EG": "（如：重生睁眼正是前世冤案发生前夜，第一步先保命并拿回一件关键物证。）",
        "COMBAT_LABEL": "对峙/交锋场面",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 当堂对峙/祠堂问罪：重礼法压制与反将一军；宴席交锋：重座次规矩下的机锋暗涌；\n"
            "- 揭发反证：重人证物证亮出的次序；舆论造势：重下人口耳与各房态度逆转。"
        ),
        "EMOTION_FLAVOR": "情绪必须收在礼数之内：一次失仪就是大事件；隐忍与眼色是主要语言。",
        "DIALOGUE_FLAVOR": "对话符合宅门语域与尊卑：称谓、请安、避讳不可错；机锋藏在客气话里。",
        "SCENE_FLAVOR": "场景等级感优先：院落规制、器物成色、座次帘幕即是权力地图。",
    },
    "realistic": {
        "NAMING_HINT": "（本题材贴合当代现实语感；机构、公司、职位命名要像真的。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【资金】首单回款28万，扣除成本净利9万；负债还剩61万\n"
            "   - 【人事】核心技术员被竞对挖走1人，新招2人\n"
            "   - 【合同】拿下连锁商超年度供货合同（年流水约500万）\n"
            "   - 【状态】父亲手术成功（花费12万，术后休养3个月）" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "上司/同事/竞对高管/合伙人/亲属等",
        "REALM_LABEL": "职级/身份",
        "REALM_DESC": "当前职级或社会身份（如部门主管、创业公司CEO、编外顾问）",
        "LOCATION_DESC": "当前地点（如公司会议室、城中村出租屋、机场贵宾厅）",
        "TIER_DESC": "价值（如：限量款、专利技术、核心资产）",
        "TECH_LABEL": "技能/专长",
        "TECH_TIER_DESC": "水准（如：业内顶尖、持证专业、独门手艺）",
        "ORG_TYPE_DESC": "类型（公司/机构/家族/圈子/部门等）",
        "LOC_TYPE_DESC": "类型（写字楼/社区/园区/城市/场馆等）",
        "CHANGE_EG": "如升职、被裁、破产、康复、决裂",
        "RESOURCE_EG": "如存款、股权、流量、人脉、信誉",
        "UNIT_DESC": "团队名称（如'项目组'、'销售团队'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **金钱账目**：收入、欠款、投资的具体数额（必须提取！）\n"
            "2. **职级股权**：职位变动、股权比例变化\n"
            "3. **关键契约**：合同、证据、期限等硬约束\n"
            "4. **健康家庭**：健康与家庭状态变化"
        ),
        "CONTINUITY_EXTRA": (
            "- 钱与期限：当前资金、欠款、合同截止日\n"
            "- 承诺台账：答应过谁什么、约了谁没赴"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【都市现实大纲附加要求】\n"
            "1. 三层矛盾网交替推进：个人（事业/内心）、家庭（亲情/婚恋）、社会（行业/时代），每章至少触及一层。\n"
            "2. 金钱与机会线数值化：关键章标注资金/债务/合同的具体数额变化。\n"
            "3. 逆袭节点必须有现实逻辑支撑（技能/信息/人脉），禁止天降贵人式转机连续出现。"
        ),
        "OPENING_HOOK_EG": "（如：被裁员/背债的至暗时刻撞上第一个翻身信息差，主角当天就行动。）",
        "COMBAT_LABEL": "对峙/交锋场面",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 会议室交锋：重数据事实与话语权争夺；商务谈判：重筹码次序与底线试探；\n"
            "- 当众对质：重证据与围观风向；行业狙击：重信息差与时间窗口。"
        ),
        "EMOTION_FLAVOR": "本题材讲究情感克制与留白：情绪藏进做饭、递烟、倒茶等日常动作里流露，表面平静与内心翻涌形成双层。",
    },
    "rules-mystery": {
        "NAMING_HINT": "（本题材命名语系：规则条目、场所编号、禁忌事项等怪谈词汇。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【出局】同批入住者触发规则3死亡2人，剩余5人\n"
            "   - 【规则】验证规则7为真、规则2为诱导陷阱（已证伪）\n"
            "   - 【道具】安全符使用1次（剩2次），手电电量剩三成\n"
            "   - 【时限】距离\"查房\"还有4小时" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "同批入住者/前辈幸存者/伪装成人的存在/管理员等",
        "REALM_LABEL": "存活层级/身份",
        "REALM_DESC": "当前身份或层级（如新入住者、第7天幸存者、代理管理员）",
        "LOCATION_DESC": "当前地点（如3号病房、员工通道、顶层禁区）",
        "TIER_DESC": "属性（如：安全道具、诅咒物、规则载体）",
        "TECH_LABEL": "手段/规则用法",
        "TECH_TIER_DESC": "可靠度（如：已验证、待验证、高危）",
        "ORG_TYPE_DESC": "类型（场所方/幸存者团体/管理者/异常存在等）",
        "LOC_TYPE_DESC": "类型（楼层/房间/禁区/安全屋等）",
        "CHANGE_EG": "如违反规则、获得豁免、被同化、受伤",
        "RESOURCE_EG": "如道具、食物、可用次数、剩余时限",
        "UNIT_DESC": "群体称呼（如'三楼幸存者'、'夜班组'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **死亡出局**：谁触发了什么规则而死/出局（必须记录！）\n"
            "2. **规则台账**：新发现/新验证/被证伪的规则条目\n"
            "3. **道具次数**：道具使用次数、剩余量、时限\n"
            "4. **区域变化**：安全区与危险区的变动"
        ),
        "CONTINUITY_EXTRA": (
            "- 规则台账：已知每条规则的原文、验证状态、例外\n"
            "- 时限轮次：当前天数/轮次、下一个关键时间点"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【规则怪谈大纲附加要求】\n"
            "1. 副本按十模块规划：基础信息/规则表/场景/人物/剧情/推理链/冲突/爽点/反转/结局；"
            "剧情走八阶段（进入→获规则→探索→推理→冲突→真相→终战→离开）。\n"
            "2. 规则表在大纲中列明六类分布：表面/矛盾/隐藏/错误/代价/生存规则，隐藏规则的发现方式提前设计。\n"
            "3. 每个副本至少一次「规则反杀」爽点：用规则漏洞或规则互卡击败诡异/对手。"
        ),
        "OPENING_HOOK_EG": "（如：入住第一夜就目睹违规者的下场，主角发现两条规则互相矛盾。）",
        "COMBAT_LABEL": "规则冲突/逃生场面",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 规则反杀：重规则条文的当场引用与漏洞利用；诡异追逐：重时限、路线与规则边界；\n"
            "- 人祸内斗：重信任崩解与祸水东引；闯关验证：重试错代价与半张底牌。"
        ),
        "SCENE_FLAVOR": "场景异常要可复查：读者回看时能发现早已存在的违和细节；异常出现讲「常识轻微偏移」。",
    },
    "scifi": {
        "NAMING_HINT": "（本题材命名语系：舰船、殖民地、星域、机甲编号、科技等级等科幻词汇。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【伤亡】侦察中队阵亡6人、机甲损失2台\n"
            "   - 【消耗】聚变燃料棒用去3根（库存11根），穿甲弹耗尽\n"
            "   - 【收益】缴获掠夺者运输车2辆、净水设备1套\n"
            "   - 【状态】主角机甲左臂动力损毁（维修需备件+48小时）" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "舰长/机师/研究员/财团代表/废土游民等",
        "REALM_LABEL": "军衔/权限等级",
        "REALM_DESC": "当前军衔或权限等级（如少尉、A级驾驶员、三级研究员）",
        "LOCATION_DESC": "当前地点（如旗舰舰桥、殖民地穹顶区、废土前哨站）",
        "TIER_DESC": "级别（如：民用级、军规级、原型机、禁运科技）",
        "TECH_LABEL": "技术/战技",
        "TECH_TIER_DESC": "等级（如：民用级、军用级、实验性）",
        "ORG_TYPE_DESC": "类型（舰队/财团/殖民政府/佣兵团/研究所等）",
        "LOC_TYPE_DESC": "类型（星球/空间站/舰船/废土据点等）",
        "CHANGE_EG": "如晋衔、机体损毁、辐射病、叛逃",
        "RESOURCE_EG": "如星币、能源、弹药、零件、补给品",
        "UNIT_DESC": "部队名称（如'第七舰队'、'侦察中队'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **战斗伤亡**：舰员、机师、士兵伤亡数（必须提取！）\n"
            "2. **装备状态**：舰船/机甲损毁部位与维修进度\n"
            "3. **能源补给**：能源、弹药、补给品的账目\n"
            "4. **科技权限**：科技突破、权限等级变动"
        ),
        "CONTINUITY_EXTRA": (
            "- 装备状态：损伤部位、维修时限、弹药能源余量\n"
            "- 航程补给：当前位置、目的地、补给可撑天数"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【科幻大纲附加要求】\n"
            "1. 科技/装备升级节点写全：来源（缴获/研发/交易）、代价、性能边界；机甲/舰船损毁与修复周期入纲。\n"
            "2. 战役章标注兵力对比与战损预估；补给线（能源/弹药/零件）作为长线压力持续存在。\n"
            "3. 世界谜团按「现象→线索→假说→颠覆」节奏分卷释放。"
        ),
        "OPENING_HOOK_EG": "（如：舰船坠毁/系统重启的第一小时，主角靠专业能力稳住局面并发现异常信号。）",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 机甲/舰战：重武器循环、部位损毁与战场态势；枪战突袭：重掩体与弹药管理；\n"
            "- 环境战（太空/废土）：重物理限制成为武器；电子战博弈：重信息压制与反制时窗。"
        ),
    },
    "zhihu-short": {
        "NAMING_HINT": "（本题材第一人称现实语感，人物用常见姓氏+身份称呼；禁止玄幻词。）",
        "SCALE_HINT": "短篇连载体量，约20-60章，分为3-6个叙事单元（卷）",
        "VOLUME_COUNT_HINT": "建议3-6个单元（卷）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【钱账】彩礼18.8万已转回我卡；婚房首付我家出了42万（有转账记录）\n"
            "   - 【证据】新增录音1段（婆婆承认偏心）、聊天记录截图17张\n"
            "   - 【关系】与大姑姐正式撕破脸；妈妈站到我这边\n"
            "   - 【状态】我搬回娘家（第3天），他还不知道我见了律师" + _VOLUME_NUMERIC_TAIL
        ),
        "IDENTITY_EG": "配偶/前任/婆家人/同事/发小等",
        "REALM_LABEL": "身份",
        "REALM_DESC": "当前身份（如大厂程序员、县城教师、全职主妇）",
        "LOCATION_DESC": "当前地点（如出租屋、老家县城、公司工位）",
        "TIER_DESC": "价值（如：存款数额、房产、关键证据）",
        "TECH_LABEL": "技能/底牌",
        "TECH_TIER_DESC": "分量（如：一锤定音的证据、专业技能）",
        "ORG_TYPE_DESC": "类型（家庭/公司/亲戚圈/朋友圈等）",
        "LOC_TYPE_DESC": "类型（城市/小区/单位/老家等）",
        "CHANGE_EG": "如摊牌、离婚、录音曝光、当众反转",
        "RESOURCE_EG": "如存款、房产、证据、舆论支持",
        "UNIT_DESC": "群体称呼（如'婆家亲戚'、'部门同事'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **钱账**：彩礼、存款、转账的具体数额（必须提取！）\n"
            "2. **证据清单**：录音、聊天记录、票据等新增证据\n"
            "3. **关系节点**：破裂/修复/站队的关键变化\n"
            "4. **知情范围**：谁知道了什么、舆论走向"
        ),
        "CONTINUITY_EXTRA": (
            "- 证据链：目前手里的每份证据、谁知道它存在\n"
            "- 反转伏笔：已埋未爆的反转点、引爆条件"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【知乎短篇大纲附加要求】\n"
            "1. 全篇按五段式配比规划：炸裂开头（约10%）→ 铺垫发展（30-40%）→ 卡点（全篇60-70%处）"
            "→ 高潮反转（70-90%处）→ 结尾余韵（约10%）。\n"
            "2. 卡点章按五要素设计：卡在情绪顶点 / 核心钩子明确 / 关键信息刚好缺失 / 付费预期清晰 / 逻辑不突兀。\n"
            "3. 反转至少两层：读者以为的真相 → 第一层反转 → 终极反转；每层提前埋 2 处线索。"
        ),
        "OPENING_HOOK_EG": "（如：50 字内直击核爆点——「婚礼上我放出了伴娘和我老公的录音」，第一人称即刻入局。）",
        "COMBAT_LABEL": "对峙/撕破脸场面",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 当众对质：重围观反应与信息炸点投放顺序；饭桌/婚宴摊牌：重体面崩塌的一瞬；\n"
            "- 证据反杀：重证据链释放节奏；舆论逆转：重评论区式人心风向的翻转。"
        ),
        "EMOTION_FLAVOR": "第一人称内心独白是主战场：情绪要真实、口语化，带自嘲与后知后觉的痛感。",
        "DIALOGUE_FLAVOR": "对话短平快，贴当代口语；金句放在段尾。",
    },
}


# ---------------------------------------------------------------------------
# 子风格微调（仅覆盖确有差异的 token；键 = (bucket, 子风格目录名)）
# ---------------------------------------------------------------------------

SUBSTYLE_OVERRIDES: Dict[Tuple[str, str], Dict[str, str]] = {
    ("xuanhuan", "凡人流"): {
        "CONTINUITY_EXTRA": (
            "- 境界与灵力：主角当前灵力余量、伤势对战力的影响\n"
            "- 消耗品存量：本章用掉的丹药/符箓/灵石必须记数\n"
            "- 寿元与底牌：主角寿元余量、隐藏底牌是否暴露"
        ),
    },
    ("xuanhuan", "苟道流"): {
        "CONTINUITY_EXTRA": (
            "- 境界与灵力：主角当前灵力余量、伤势对战力的影响\n"
            "- 消耗品存量：本章用掉的丹药/符箓/灵石必须记数\n"
            "- 苟住程度：主角实力暴露了多少、被谁看破"
        ),
    },
    ("alt-history", "争霸流"): {
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **兵员伤亡**：各部阵亡、被俘、溃散、新募人数（必须逐项提取！）\n"
            "2. **城池地盘**：城池、关隘、州县的得失\n"
            "3. **钱粮军械**：白银、粮草、军械、战马的收支数目\n"
            "4. **将领人才**：来投/战死/叛离的将领谋士"
        ),
    },
    ("alt-history", "种田流"): {
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【产出】新垦田亩八十亩，秋收粟米四百石\n"
            "   - 【工坊】砖窑月产青砖两万块，净利白银六十两\n"
            "   - 【人口】新收流民47口（青壮19人），庄户共312口\n"
            "   - 【消耗】过冬存粮支出一百二十石，余六百石" + _VOLUME_NUMERIC_TAIL
        ),
    },
    ("apocalypse", "囤货流"): {
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **囤货台账**：新入库物资的品类与数量（必须逐项提取！）\n"
            "2. **消耗流水**：食物、水、弹药、药品的每笔支出\n"
            "3. **幸存者伤亡**：死亡/受伤/感染人数\n"
            "4. **空间/仓库**：储物空间容量、仓库安全状态"
        ),
    },
    ("dog-blood-romance", "追妻火葬场"): {
        "CONTINUITY_EXTRA": (
            "- 误会链：当前每个未解开的误会、各方信息差\n"
            "- 火葬场进度：男主悔意等级、女主死心程度、挽回动作的效果"
        ),
    },
    ("dark", "黑暗修仙"): {
        "REALM_LABEL": "境界",
        "REALM_DESC": "当前境界（如炼气、筑基、金丹，含邪修伪境）",
        "TECH_LABEL": "功法/邪术",
        "TECH_TIER_DESC": "等级（如：黄阶、玄阶、禁术）",
        "RESOURCE_EG": "如灵石、丹药、血食、炉鼎材料",
        "ORG_TYPE_DESC": "类型（魔宗/邪修窝点/正道宗门/修士坊市等）",
    },
    ("dark", "末路求生"): {
        "RESOURCE_EG": "如口粮（按天数）、净水、药品、燃料",
        "LOC_TYPE_DESC": "类型（废墟/避难点/危险区/交易点等）",
    },
    ("realistic", "都市异能"): {
        "REALM_LABEL": "异能等级",
        "REALM_DESC": "当前异能等级（如C级觉醒者、B级强化系）",
        "TECH_LABEL": "异能/技能",
        "TECH_TIER_DESC": "等级（如：D级、C级、觉醒系/强化系）",
    },
    ("scifi", "废土改造流"): {
        "RESOURCE_EG": "如废料零件、净水、燃料、种子",
    },
    ("scifi", "机甲战争流"): {
        "UNIT_DESC": "部队名称（如'机甲中队'、'突击小队'等）",
    },
    # 年代文：realistic 桶下的新子风格，词表全面年代化（票证/工分/四合院语系）
    ("realistic", "年代文"): {
        "IDENTITY_EG": "院里大爷/厂领导/对门邻居/乡下亲戚/媒人等",
        "REALM_LABEL": "身份/工位",
        "REALM_DESC": "当前身份（如轧钢厂二级钳工、街道办干事、返城知青）",
        "LOCATION_DESC": "当前地点（如四合院中院、轧钢厂车间、供销社）",
        "TIER_DESC": "价值（如：全院第一台彩电、祖传座钟、缝纫机票）",
        "TECH_LABEL": "手艺/本事",
        "TECH_TIER_DESC": "水准（如：八级钳工、祖传厨艺、老中医手艺）",
        "ORG_TYPE_DESC": "类型（工厂/街道/四合院/亲戚圈等）",
        "LOC_TYPE_DESC": "类型（四合院/厂区/胡同/乡下/供销社等）",
        "CHANGE_EG": "如转正提级、下乡返城、结婚分房、名声受损",
        "RESOURCE_EG": "如粮票布票、工资存款、工业券、人情",
        "UNIT_DESC": "群体称呼（如'全院住户'、'车间工友'等）",
        "EXTRACT_NUMERIC_FOCUS": (
            "1. **钱票账目**：工资、粮票布票、存款的具体数目（必须提取！）\n"
            "2. **物件添置**：自行车/缝纫机/彩电等大件的取得与花费\n"
            "3. **身份变动**：转正、提级、下乡、返城、分房\n"
            "4. **人情往来**：欠下/还清的人情、院内关系冷热变化"
        ),
        "CONTINUITY_EXTRA": (
            "- 钱票账本：工资、粮票、存款当前数目\n"
            "- 院内关系：各家态度冷热、欠着谁的人情、哪家在憋坏水"
        ),
        "OUTLINE_METHOD_EXTRA": (
            "\n【年代文大纲附加要求】\n"
            "1. 按年代节点划分章节：每章标注具体年份（如 1965 春），"
            "历史节点（票证收紧/恢复高考/改革开放）作为剧情引擎入纲。\n"
            "2. 三层矛盾网年代化：个人奋斗（工作/婚事）、院里邻里（占便宜/道德绑架/互助）、"
            "时代变迁（政策与观念碰撞），每章至少一层。\n"
            "3. 主角成长必须与时代变迁绑定：每个人生台阶对应一个时代机会（招工/参军/高考/下海）。\n"
            "4. 爽点以「怀旧共鸣+邻里反击+日子越过越好」为主：物质改善写具体清单（自行车/缝纫机/彩电）。"
        ),
        "OPENING_HOOK_EG": "（如：重生回到 1962 年分家现场，上辈子吃绝户的亲戚正堵在门口。）",
        "VOLUME_NUMERIC_EXAMPLE": (
            "✅ 正确示例：\n"
            "   - 【钱票】月工资 27.5 元，本月存下 8 元；粮票余 32 斤\n"
            "   - 【物件】添置二手自行车一辆（花 90 元 + 工业券 3 张）\n"
            "   - 【人情】帮三大爷家修屋顶，抵掉先前欠的半袋棒子面\n"
            "   - 【身份】转正定级二级工（月薪涨 4.5 元）" + _VOLUME_NUMERIC_TAIL
        ),
        "DIALOGUE_FLAVOR": "对话双重符合：人物性格 × 年代语汇（工分/粮票/介绍信/单位），禁止现代网络词穿越。",
        "EMOTION_FLAVOR": "年代文情绪走隐忍克制路线：大悲大喜都收着，落在一顿肉、一张票、一句体面话上。",
        "SCENE_FLAVOR": "场景年代化：家具电器、服饰、票证、广播声都是年代锚点；细节点到即止，不许堆砌伤流畅。",
        "COMBAT_LABEL": "对峙/撕破脸场面",
        "COMBAT_TYPES": (
            "【场面类型侧重】\n"
            "- 全院大会对质：重大爷们的和稀泥与舆论逆转；分家/分房摊牌：重账目清单与礼数攻防；\n"
            "- 厂里评级交锋：重手艺与资历的当场验证；亲戚上门打秋风：重软刀子与硬回绝。"
        ),
    },
    # 知乎短篇三子风格：卡点措辞微调
    ("zhihu-short", "高能反转"): {},
    ("zhihu-short", "情感反杀"): {},
    ("zhihu-short", "悬念揭秘"): {},
}

# 知乎三子风格在桶级方法论之上追加各自的卡点定位（引用桶词表需在两个字典定义之后）
_ZHIHU_EXTRA = BUCKET_VOCAB["zhihu-short"]["OUTLINE_METHOD_EXTRA"]
SUBSTYLE_OVERRIDES[("zhihu-short", "高能反转")]["OUTLINE_METHOD_EXTRA"] = (
    _ZHIHU_EXTRA + "\n4. 本子风格卡点优先卡在「第一层反转揭晓前的最后一句」。"
)
SUBSTYLE_OVERRIDES[("zhihu-short", "情感反杀")]["OUTLINE_METHOD_EXTRA"] = (
    _ZHIHU_EXTRA + "\n4. 本子风格卡点优先卡在「隐忍到顶、反击第一刀落下之前」。"
)
SUBSTYLE_OVERRIDES[("zhihu-short", "悬念揭秘")]["OUTLINE_METHOD_EXTRA"] = (
    _ZHIHU_EXTRA + "\n4. 本子风格卡点优先卡在「关键真相只差最后一块拼图」处。"
)


# ---------------------------------------------------------------------------
# 生成逻辑
# ---------------------------------------------------------------------------

def _body_hash(body: str) -> str:
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:10]


def _merged_vocab(bucket: str, substyle: str) -> Dict[str, str]:
    vocab = dict(DEFAULT_VOCAB)
    vocab.update(BUCKET_VOCAB.get(bucket, {}))
    vocab.update(SUBSTYLE_OVERRIDES.get((bucket, substyle), {}))
    return vocab


def _compose(file_key: str, base: str, bucket: str, substyle: str) -> str:
    body = fill_vocab(base, _merged_vocab(bucket, substyle), strict=True)
    marker = f"<!-- generated slot={file_key} gen_hash={_body_hash(body)} -->\n"
    return marker + body + "\n"


def _validate(kind: str, file_key: str, content: str, path: Path) -> list[str]:
    problems: list[str] = []
    if "%%" in content:
        problems.append(f"{path}: 残留 %%TOKEN%%")
    if kind == "slot":
        for var in SLOT_VARIABLES[file_key]:
            if "{" + var + "}" not in content:
                problems.append(f"{path}: 缺变量 {{{var}}}")
        if file_key == "extract_state":
            for key in EXTRACT_REQUIRED_KEYS:
                if f'"{key}"' not in content:
                    problems.append(f"{path}: 提取契约键缺失 {key}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="生成子风格包提示词槽位文件")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写盘")
    parser.add_argument("--force", action="store_true", help="覆盖手改过的生成文件")
    args = parser.parse_args()

    if not GENRES_DIR.exists():
        print(f"[ERROR] 题材包目录不存在: {GENRES_DIR}")
        return 1

    packages = sorted(
        (bucket_dir.name, sub_dir.name, sub_dir)
        for bucket_dir in GENRES_DIR.iterdir() if bucket_dir.is_dir()
        for sub_dir in bucket_dir.iterdir() if sub_dir.is_dir()
    )
    unknown_buckets = sorted({b for b, _, _ in packages} - set(BUCKET_VOCAB))
    if unknown_buckets:
        print(f"[ERROR] 以下桶缺少词汇表，请先补 BUCKET_VOCAB: {unknown_buckets}")
        return 1

    # 槽位族（进项目快照）+ 辅助文件族（包内直读，desire-description.md 不纳管）
    work_specs = [("slot", sid, fn, SLOT_BASES[sid]) for sid, fn in SLOT_FILENAMES.items()]
    work_specs += [("aux", key, fn, AUX_BASES[key]) for key, fn in AUX_FILENAMES.items()]

    created = updated = skipped = unchanged = 0
    skipped_paths: list[str] = []
    problems: list[str] = []

    for bucket, substyle, pkg_dir in packages:
        for kind, file_key, filename, base in work_specs:
            target = pkg_dir / filename
            content = _compose(file_key, base, bucket, substyle)
            problems.extend(_validate(kind, file_key, content, target))

            if not target.exists():
                action = "create"
            else:
                old = target.read_text(encoding="utf-8")
                if old == content:
                    unchanged += 1
                    continue
                m = MARKER_RE.match(old)
                if m:
                    old_body = MARKER_RE.sub("", old, count=1).rstrip("\n")
                    hand_edited = _body_hash(old_body) != m.group(2)
                else:
                    # 无标记：extract-state.md（旧死契约）与四个辅助文件
                    # （全仓库零引用的死占位）首轮直接重写；其余视为手写内容。
                    hand_edited = not (file_key == "extract_state" or kind == "aux")
                if hand_edited and not args.force:
                    skipped += 1
                    skipped_paths.append(str(target.relative_to(REPO_ROOT)))
                    continue
                action = "update"

            if not args.dry_run:
                target.write_text(content, encoding="utf-8")
            if action == "create":
                created += 1
            else:
                updated += 1

    print(f"[GEN] 包数: {len(packages)} | 新建 {created} | 更新 {updated} | 未变 {unchanged} | 跳过(手改) {skipped}")
    for p in skipped_paths:
        print(f"  [SKIP] {p}")
    if problems:
        print(f"[ERROR] 自校验失败 {len(problems)} 项：")
        for p in problems:
            print(f"  {p}")
        return 1
    print("[GEN] 自校验通过：变量完整、无残留 token、提取契约键在位")
    return 0


if __name__ == "__main__":
    sys.exit(main())
