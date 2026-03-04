import re

content_v2 = "### 第100章《灰河村立“顾姓香牌”》"
content_v3 = "- **第121章：祠堂新主与旧账清算**"

# Combined pattern
# (?:###?|-\s*\*\*) : Match '###' or '##' OR '- **' (with flex spaces)
# \s*第(\d+)章       : Match '第121章'
# [：:\s]*           : Match separator
# (.+?)              : Capture title non-greedily
# (?:(?:\*\*)|(?:\n)|$) : End at '**' OR newline OR end of string
pattern = re.compile(r"(?:###?|-\s*\*\*)\s*第(\d+)章[：:\s]*(.+?)(?:(?:\*\*)|(?:\n)|$)")

print(f"Testing V2 line: '{content_v2}'")
m2 = pattern.search(content_v2)
if m2:
    print(f"  Match: Chapter {m2.group(1)}, Title: '{m2.group(2).strip()}'")
else:
    print("  No match")

print(f"Testing V3 line: '{content_v3}'")
m3 = pattern.search(content_v3)
if m3:
    print(f"  Match: Chapter {m3.group(1)}, Title: '{m3.group(2).strip()}'")
else:
    print("  No match")
