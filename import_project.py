import sys
import os
from pathlib import Path

# Add current directory to path so we can import backend
sys.path.append(os.getcwd())

try:
    from backend.services import projects_manager
    
    target_path = "/Users/lvkuanyou/Desktop/webnovel-writer/backend/data/诡异世界：我的家族能分摊代价"
    print(f"Importing project from: {target_path}")
    
    result = projects_manager.import_project(target_path)
    print(f"Result: {result}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
