import os
import re
import pathlib

# Configuration
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "backend/data/玄幻：我的能力是词条"
CHAPTER_THRESHOLD = 50

def get_chapter_number_from_filename(filename):
    match = re.search(r"第(\d+)章", filename)
    if match:
        return int(match.group(1))
    return None

def get_first_appearance_chapter(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # Match "首次出场：第XX章" or "首次出现：第XX章"
            # Flexible matching for colon and spaces
            match = re.search(r"首次(出场|出现)[:：]\s*第(\d+)章", content)
            if match:
                return int(match.group(2))
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return None

def main():
    print(f"Scanning for content after Chapter {CHAPTER_THRESHOLD} in {DATA_DIR}...")
    
    files_to_delete = []

    # 1. Scan Chapters
    chapter_dir = DATA_DIR / "正文"
    if chapter_dir.exists():
        for file in chapter_dir.iterdir():
            if file.is_file() and file.name.endswith(".md"):
                chap_num = get_chapter_number_from_filename(file.name)
                if chap_num and chap_num > CHAPTER_THRESHOLD:
                    files_to_delete.append(file)

    # 2. Scan Settings (Characters, Locations, etc.)
    setting_dir = DATA_DIR / "设定集"
    if setting_dir.exists():
        for file in setting_dir.rglob("*.md"):
            if file.is_file():
                chap_num = get_first_appearance_chapter(file)
                if chap_num and chap_num > CHAPTER_THRESHOLD:
                    files_to_delete.append(file)

    if not files_to_delete:
        print("No files found matching the criteria.")
        return

    print(f"\nFound {len(files_to_delete)} files to delete:")
    for f in files_to_delete:
        print(f" - {f.relative_to(DATA_DIR)}")

    # Since this is run by the agent in an automated context, we will proceed.
    # But usually we'd ask for input.
    print(f"\nDeleting {len(files_to_delete)} files...")
    for f in files_to_delete:
        try:
            f.unlink()
            print(f"Deleted: {f.name}")
        except Exception as e:
            print(f"Failed to delete {f.name}: {e}")

    print("\nCleanup complete.")

if __name__ == "__main__":
    main()
