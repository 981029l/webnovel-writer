import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path("backend/services").absolute()))
from skill_executor import SkillExecutor

# Mock AI service to just test the flow, but wait, we need real AI to extract.
# Let's import the real one.
sys.path.insert(0, str(Path("backend").absolute()))
from services.ai_service import get_ai_service

async def main():
    root = Path("backend/data/诡异世界：我的家族能分摊代价").resolve()
    ai = get_ai_service()
    executor = SkillExecutor(root, ai)
    
    content = "第326章 顾忠的新武器\n\n顾忠在祠堂前，获得了家族新锻造的一把法宝【泣血刃】。这是一把能吸食敌人精血反哺使用者的兵器，邪恶但强大。同时，顾家的公库香火因为重铸兵器，消耗巨大，目前只余下8000点。另外顾忠在之前的战斗中损失的左臂，被大长老用秘术接上了一条木制偃甲臂。"
    
    print("Testing extraction...")
    res = await executor.execute_state_extraction(326, content)
    print("Result:", res)

asyncio.run(main())
