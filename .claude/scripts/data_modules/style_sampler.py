#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Style Sampler - 风格样本管理模块

管理高质量章节片段作为风格参考：
- 风格样本存储
- 按场景类型分类
- 样本选择策略
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from contextlib import contextmanager

from .config import get_config


class SceneType(Enum):
    """场景类型"""
    BATTLE = "战斗"
    DIALOGUE = "对话"
    DESCRIPTION = "描写"
    TRANSITION = "过渡"
    EMOTION = "情感"
    TENSION = "紧张"
    COMEDY = "轻松"


@dataclass
class StyleSample:
    """风格样本"""
    id: str
    chapter: int
    scene_type: str
    content: str
    score: float
    tags: List[str]
    created_at: str = ""


class StyleSampler:
    """风格样本管理器"""

    def __init__(self, config=None):
        self.config = config or get_config()
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        self.config.ensure_dirs()
        with self._get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS samples (
                    id TEXT PRIMARY KEY,
                    chapter INTEGER,
                    scene_type TEXT,
                    content TEXT,
                    score REAL,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_samples_type ON samples(scene_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_samples_score ON samples(score DESC)")

            conn.commit()

    @contextmanager
    def _get_conn(self):
        """获取数据库连接（确保关闭，避免 Windows 下文件句柄泄漏导致无法清理临时目录）"""
        db_path = self.config.webnovel_dir / "style_samples.db"
        conn = sqlite3.connect(str(db_path))
        try:
            yield conn
        finally:
            conn.close()

    # ==================== 样本管理 ====================

    def add_sample(self, sample: StyleSample) -> bool:
        """添加风格样本"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO samples
                    (id, chapter, scene_type, content, score, tags, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    sample.id,
                    sample.chapter,
                    sample.scene_type,
                    sample.content,
                    sample.score,
                    json.dumps(sample.tags, ensure_ascii=False),
                    sample.created_at or datetime.now().isoformat()
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_samples_by_type(
        self,
        scene_type: str,
        limit: int = 5,
        min_score: float = 0.0
    ) -> List[StyleSample]:
        """按场景类型获取样本"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, chapter, scene_type, content, score, tags, created_at
                FROM samples
                WHERE scene_type = ? AND score >= ?
                ORDER BY score DESC
                LIMIT ?
            """, (scene_type, min_score, limit))

            return [self._row_to_sample(row) for row in cursor.fetchall()]

    def get_best_samples(self, limit: int = 10) -> List[StyleSample]:
        """获取最高分样本"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, chapter, scene_type, content, score, tags, created_at
                FROM samples
                ORDER BY score DESC
                LIMIT ?
            """, (limit,))

            return [self._row_to_sample(row) for row in cursor.fetchall()]

    def _row_to_sample(self, row) -> StyleSample:
        """将数据库行转换为样本对象"""
        return StyleSample(
            id=row[0],
            chapter=row[1],
            scene_type=row[2],
            content=row[3],
            score=row[4],
            tags=json.loads(row[5]) if row[5] else [],
            created_at=row[6]
        )

    # ==================== 样本提取 ====================

    def extract_candidates(
        self,
        chapter: int,
        content: str,
        review_score: float,
        scenes: List[Dict]
    ) -> List[StyleSample]:
        """
        从章节中提取风格样本候选 - 多维度质量控制

        评分标准更严格：
        - review_score >= 85 (提高门槛)
        - 必须通过AI痕迹检测
        - 必须通过对话真实性检测
        """
        if review_score < 85:  # 提高门槛
            return []

        candidates = []

        for scene in scenes:
            # 预检测AI痕迹
            ai_trace_score = self._detect_ai_traces(scene.get("content", ""))
            if ai_trace_score > 30:  # AI痕迹过重，跳过
                continue

            # 预检测对话真实性（如果包含对话）
            if self._has_dialogue(scene.get("content", "")):
                dialogue_score = self._check_dialogue_reality(scene.get("content", ""))
                if dialogue_score < 70:  # 对话不够真实，跳过
                    continue

            scene_type = self._classify_scene_type(scene)
            scene_content = scene.get("content", "")

            # 跳过过短的场景
            if len(scene_content) < 300:  # 提高最小长度要求
                continue

            # 计算综合质量分数
            quality_score = self._calculate_quality_score(
                review_score, ai_trace_score, dialogue_score if self._has_dialogue(scene_content) else 90
            )

            # 创建样本
            sample = StyleSample(
                id=f"ch{chapter}_s{scene.get('index', 0)}",
                chapter=chapter,
                scene_type=scene_type,
                content=scene_content[:2000],  # 限制长度
                score=quality_score / 100.0,
                tags=self._extract_tags(scene_content)
            )
            candidates.append(sample)

        return candidates

    def _detect_ai_traces(self, content: str) -> float:
        """检测AI痕迹，返回0-100分数，越高越像AI写的"""
        ai_patterns = [
            "眼中闪过.*情绪", "心中五味杂陈", "时间仿佛.*静止",
            "空气中弥漫着", "波澜不惊", "古井无波",
            "缓缓.*", "轻轻.*", "静静.*"
        ]

        trace_count = 0
        for pattern in ai_patterns:
            import re
            if re.search(pattern, content):
                trace_count += 1

        # 简单计算：每个AI模式扣10分
        return min(trace_count * 10, 100)

    def _has_dialogue(self, content: str) -> bool:
        """检测是否包含对话"""
        dialogue_markers = ['"', '"', '"', '说道', '问道', '答道']
        return any(marker in content for marker in dialogue_markers)

    def _check_dialogue_reality(self, content: str) -> float:
        """检测对话真实性，返回0-100分数"""
        if not self._has_dialogue(content):
            return 90  # 无对话默认高分

        # 检测书面化程度
        formal_words = ["因此", "然而", "显然", "毫无疑问", "事实上"]
        formal_count = sum(1 for word in formal_words if word in content)

        # 检测口语特征
        oral_features = ["嗯", "啊", "哦", "呃", "那个", "就是", "算了"]
        oral_count = sum(1 for feature in oral_features if feature in content)

        # 简单评分：口语特征加分，书面化扣分
        score = 70 + oral_count * 5 - formal_count * 10
        return max(0, min(100, score))

    def _calculate_quality_score(self, review_score: float, ai_trace_score: float, dialogue_score: float) -> float:
        """计算综合质量分数"""
        # 加权平均：审查分数50%，AI痕迹30%，对话真实性20%
        return (review_score * 0.5 +
                (100 - ai_trace_score) * 0.3 +
                dialogue_score * 0.2)

    def _classify_scene_type(self, scene: Dict) -> str:
        """分类场景类型 - 基于语义和情感层次，而非机械关键词"""
        summary = scene.get("summary", "").lower()
        content = scene.get("content", "").lower()
        text = summary + content

        # 多维度权重评分，而非简单关键词匹配
        scores = {
            SceneType.BATTLE.value: 0,
            SceneType.DIALOGUE.value: 0,
            SceneType.EMOTION.value: 0,
            SceneType.TENSION.value: 0,
            SceneType.DESCRIPTION.value: 0
        }

        # 战斗场景：动作密度 + 冲突强度
        battle_patterns = [
            (["战斗", "攻击", "出手"], 3),  # 直接动作
            (["血", "伤", "痛", "死"], 2),  # 后果
            (["快", "猛", "狠", "准"], 1),  # 动作特征
            (["拳", "剑", "刀", "枪"], 1)   # 武器
        ]
        for keywords, weight in battle_patterns:
            if any(kw in text for kw in keywords):
                scores[SceneType.BATTLE.value] += weight

        # 对话场景：交流密度 + 语言特征
        dialogue_patterns = [
            (["说", "道", "问", "答"], 3),
            (["声音", "语气", "口吻"], 2),
            (["沉默", "停顿", "犹豫"], 1),
            (["\"", """, """], 2)  # 引号密度
        ]
        for keywords, weight in dialogue_patterns:
            if any(kw in text for kw in keywords):
                scores[SceneType.DIALOGUE.value] += weight

        # 情感场景：内心活动 + 情绪表现
        emotion_patterns = [
            (["心", "想", "觉得", "感觉"], 3),
            (["泪", "笑", "哭", "怒"], 2),
            (["温暖", "冰冷", "颤抖"], 1),
            (["回忆", "想起", "忘记"], 1)
        ]
        for keywords, weight in emotion_patterns:
            if any(kw in text for kw in keywords):
                scores[SceneType.EMOTION.value] += weight

        # 紧张场景：压迫感 + 不确定性
        tension_patterns = [
            (["危险", "恐惧", "害怕"], 3),
            (["紧张", "焦虑", "不安"], 2),
            (["黑暗", "阴影", "寂静"], 1),
            (["突然", "忽然", "猛地"], 1)
        ]
        for keywords, weight in tension_patterns:
            if any(kw in text for kw in keywords):
                scores[SceneType.TENSION.value] += weight

        # 描写场景：环境细节 + 感官体验
        description_patterns = [
            (["看到", "听到", "闻到"], 2),
            (["风", "雨", "阳光", "月亮"], 1),
            (["房间", "街道", "山", "水"], 1),
            (["颜色", "声音", "味道"], 1)
        ]
        for keywords, weight in description_patterns:
            if any(kw in text for kw in keywords):
                scores[SceneType.DESCRIPTION.value] += weight

        # 返回得分最高的类型，如果都是0则默认为描写
        max_type = max(scores.items(), key=lambda x: x[1])
        return max_type[0] if max_type[1] > 0 else SceneType.DESCRIPTION.value

    def _extract_tags(self, content: str) -> List[str]:
        """提取内容标签"""
        tags = []

        # 简单标签提取
        if "战斗" in content or "攻击" in content:
            tags.append("战斗")
        if "修炼" in content or "突破" in content:
            tags.append("修炼")
        if "对话" in content or "说道" in content:
            tags.append("对话")
        if "描写" in content or "景色" in content:
            tags.append("描写")

        return tags[:5]

    # ==================== 样本选择 ====================

    def select_samples_for_chapter(
        self,
        chapter_outline: str,
        target_types: List[str] = None,
        max_samples: int = 3
    ) -> List[StyleSample]:
        """
        为章节写作选择合适的风格样本

        基于大纲分析需要什么类型的样本
        """
        if target_types is None:
            # 根据大纲推断需要的场景类型
            target_types = self._infer_scene_types(chapter_outline)

        samples = []
        per_type = max(1, max_samples // len(target_types)) if target_types else max_samples

        for scene_type in target_types:
            type_samples = self.get_samples_by_type(scene_type, limit=per_type, min_score=0.8)
            samples.extend(type_samples)

        return samples[:max_samples]

    def _infer_scene_types(self, outline: str) -> List[str]:
        """从大纲推断需要的场景类型"""
        types = []

        if any(kw in outline for kw in ["战斗", "对决", "比试", "交手"]):
            types.append(SceneType.BATTLE.value)

        if any(kw in outline for kw in ["对话", "谈话", "商议", "讨论"]):
            types.append(SceneType.DIALOGUE.value)

        if any(kw in outline for kw in ["情感", "感情", "心理"]):
            types.append(SceneType.EMOTION.value)

        if not types:
            types = [SceneType.DESCRIPTION.value]

        return types

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取样本统计"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM samples")
            total = cursor.fetchone()[0]

            cursor.execute("""
                SELECT scene_type, COUNT(*) as count
                FROM samples
                GROUP BY scene_type
            """)
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT AVG(score) FROM samples")
            avg_score = cursor.fetchone()[0] or 0

            return {
                "total": total,
                "by_type": by_type,
                "avg_score": round(avg_score, 3)
            }


# ==================== CLI 接口 ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Style Sampler CLI")
    parser.add_argument("--project-root", type=str, help="项目根目录")

    subparsers = parser.add_subparsers(dest="command")

    # 获取统计
    subparsers.add_parser("stats")

    # 列出样本
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--type", help="按类型过滤")
    list_parser.add_argument("--limit", type=int, default=10)

    # 提取样本
    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--chapter", type=int, required=True)
    extract_parser.add_argument("--score", type=float, required=True)
    extract_parser.add_argument("--scenes", required=True, help="JSON 格式的场景列表")

    # 选择样本
    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("--outline", required=True, help="章节大纲")
    select_parser.add_argument("--max", type=int, default=3)

    args = parser.parse_args()

    # 初始化
    config = None
    if args.project_root:
        from .config import DataModulesConfig
        config = DataModulesConfig.from_project_root(args.project_root)

    sampler = StyleSampler(config)

    if args.command == "stats":
        stats = sampler.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif args.command == "list":
        if args.type:
            samples = sampler.get_samples_by_type(args.type, args.limit)
        else:
            samples = sampler.get_best_samples(args.limit)

        for s in samples:
            print(f"\n[{s.scene_type}] 第 {s.chapter} 章 (score: {s.score:.2f})")
            print(f"  {s.content[:100]}...")

    elif args.command == "extract":
        scenes = json.loads(args.scenes)
        candidates = sampler.extract_candidates(
            chapter=args.chapter,
            content="",
            review_score=args.score,
            scenes=scenes
        )

        for c in candidates:
            if sampler.add_sample(c):
                print(f"✓ 添加样本: {c.id} ({c.scene_type})")
            else:
                print(f"✗ 样本已存在: {c.id}")

    elif args.command == "select":
        samples = sampler.select_samples_for_chapter(args.outline, max_samples=args.max)

        print(f"选择了 {len(samples)} 个风格样本:")
        for s in samples:
            print(f"\n[{s.scene_type}] 第 {s.chapter} 章")
            print(f"  {s.content[:200]}...")


if __name__ == "__main__":
    main()
