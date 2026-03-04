import re
from pathlib import Path

content = Path("/Users/lvkuanyou/Desktop/webnovel-writer/大纲/第2卷-详细大纲.md").read_text(encoding="utf-8")
pattern = re.compile(r"###?\s*第(\d+)章[：:\s]*(.+?)(?:\n|$)")

print(f"Total content length: {len(content)}")

matches = list(pattern.finditer(content))
print(f"Found {len(matches)} matches")

for m in matches:
    chap = int(m.group(1))
    if chap >= 99:
        print(f"Match: Chapter {chap}, Title captured: '{m.group(2)}'")

# Check if there are lines that look like chapters but were missed
lines = content.split('\n')
for i, line in enumerate(lines):
    if "第10" in line and "章" in line:
         # simple heuristic to find potential chapter lines
         is_matched = False
         for m in matches:
             if m.group(0) in line: # rough check
                 is_matched = True
                 break
         # print(f"Line {i+1}: {line.strip()} (Matched: {is_matched})")
