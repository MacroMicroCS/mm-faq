"""Import FAQ from Excel to Markdown files."""
import re
import json
import pandas as pd
from pathlib import Path

EXCEL_PATH = "/Users/tingting/Downloads/FAQ_三語版.xlsx"
SHEET_NAME = "FAQ 語氣優化全版（97條）"
CONTENT_DIR = Path(__file__).parent.parent / "content"

def slugify(text):
    text = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', text)
    return re.sub(r'[\s]+', '-', text.strip())

def escape_yaml(text):
    if not text or pd.isna(text):
        return ""
    text = str(text).strip()
    if any(c in text for c in ':{}[]&*?|>!%@`#,'):
        return '"' + text.replace('"', '\\"') + '"'
    return text

def main():
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    index = []
    for _, row in df.iterrows():
        faq_id = str(int(row['#'])).zfill(3) if pd.notna(row['#']) else "000"
        category = str(row['類別']).strip() if pd.notna(row['類別']) else "未分類"
        section = str(row['段落']).strip() if pd.notna(row['段落']) else "一般"
        order = int(row['段落內排序']) if pd.notna(row['段落內排序']) else 0
        title_tw = str(row['標題']).strip() if pd.notna(row['標題']) else ""
        content_tw = str(row['語氣優化版（Gmail 口吻）']).strip() if pd.notna(row['語氣優化版（Gmail 口吻）']) else ""
        title_cn = str(row['简中标题']).strip() if pd.notna(row['简中标题']) else ""
        content_cn = str(row['简中内文']).strip() if pd.notna(row['简中内文']) else ""
        title_en = str(row['英文标题']).strip() if pd.notna(row['英文标题']) else ""
        content_en = str(row['英文内文']).strip() if pd.notna(row['英文内文']) else ""

        # Create category/section directory
        cat_dir = CONTENT_DIR / slugify(category) / slugify(section)
        cat_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{faq_id}-{slugify(title_tw)}.md"
        filepath = cat_dir / filename

        has_cn = bool(title_cn and content_cn)
        has_en = bool(title_en and content_en)

        # Write markdown with frontmatter
        md = f"""---
id: "{faq_id}"
category: {escape_yaml(category)}
section: {escape_yaml(section)}
order: {order}
status: "published"
locales:
  zh-tw: true
  zh-cn: {str(has_cn).lower()}
  en: {str(has_en).lower()}
title:
  zh-tw: {escape_yaml(title_tw)}
  zh-cn: {escape_yaml(title_cn)}
  en: {escape_yaml(title_en)}
---

{content_tw}

<!--locale:zh-cn-->

{content_cn}

<!--locale:en-->

{content_en}
"""
        filepath.write_text(md.strip() + "\n", encoding="utf-8")

        index.append({
            "id": faq_id,
            "category": category,
            "section": section,
            "order": order,
            "status": "published",
            "locales": {"zh-tw": True, "zh-cn": has_cn, "en": has_en},
            "title": {"zh-tw": title_tw, "zh-cn": title_cn, "en": title_en},
            "file": str(filepath.relative_to(CONTENT_DIR)),
        })

    # Write index.json
    index_path = CONTENT_DIR.parent / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"Imported {len(index)} FAQs")
    cats = {}
    for item in index:
        key = f"{item['category']} > {item['section']}"
        cats[key] = cats.get(key, 0) + 1
    for k, v in sorted(cats.items()):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
