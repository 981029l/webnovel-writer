
import asyncio
from pathlib import Path
from services.skill_executor import SkillExecutor
from services.ai_service import AIService
from data_modules.config import DataModulesConfig

async def main():
    project_root = Path("/Users/lvkuanyou/Desktop/webnovel-writer/backend/data/诡异世界：我的家族能分摊代价")
    
    # Initialize services
    config = DataModulesConfig.from_project_root(project_root)
    # Mock AI Service or use real one if configured
    ai_service = AIService(config) # This requires running server context or similar config
    
    executor = SkillExecutor(
        project_root=project_root,
        ai_service=ai_service
    )
    
    chapter = 198
    chapter_file = project_root / "正文" / f"第{chapter}章-新装备：诡兵符·硬皮.md"
    content = chapter_file.read_text(encoding="utf-8")
    
    print(f"Extracting characters from Chapter {chapter}...")
    await executor._update_character_state(chapter, content)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
