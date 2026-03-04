
import re

content = """
## 第1章：无灯巷口的纸人
- **主要情节**：...

## 第2章：讨债诡上门，账单弹出
"""

# My current regex
params = r"^\s*(?:#+|[-*]\s+\*\*?|[-*])?\s*第(\d+)章[：:\s]*([^\n]+?)(?:\*\*|\s|$)"
chapter_pattern = re.compile(params, re.MULTILINE)

print(f"Testing regex: {params}")
matches = list(chapter_pattern.finditer(content))
print(f"Found {len(matches)} matches")

for m in matches:
    print(f"Match: {m.group(1)} - {m.group(2)}")
