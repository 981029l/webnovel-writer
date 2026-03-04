import re

# 模拟更新后的 patterns
chapter = 122
patterns = [
    rf"^###?\s*{chapter}\.\s*.*$",          # "### 1.《标题》" or "1.《标题》"
    rf"^###?\s*第{chapter}章.*$",           # "### 第1章..." or "第1章..."
    rf"^{chapter}\.\s*\*\*.*\*\*.*$",       # "1. **标题**..."
    rf"^-\s*\*\*第{chapter}章[：:\s].*$",   # "- **第122章：标题**" (第三卷格式)
]

# 测试所有格式
test_lines = [
    "### 第122章《家规升级，族印初生》",      # 第一二卷格式
    "- **第122章：家规升级，族印初生**",      # 第三卷格式
]

for line in test_lines:
    line_stripped = line.strip()
    match = False
    for p in patterns:
        if re.match(p, line_stripped):
            match = True
            break
    print(f"'{line[:40]}...' -> Match: {match}")
