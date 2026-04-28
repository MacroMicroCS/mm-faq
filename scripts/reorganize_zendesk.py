"""
Delete old content and reorganize Zendesk-imported articles into proper categories.
Run from the faq/ directory.
"""

import json
import shutil
from pathlib import Path
import frontmatter

CONTENT_DIR = Path("content")
INDEX_FILE = Path("index.json")

# Map FAQ ID → (category, section)
CATEGORY_MAP = {
    # ── 新手入門 ──────────────────────────────────────────
    "105": ("新手入門", "免費試用與入門"),
    "117": ("新手入門", "註冊與入門"),
    "130": ("新手入門", "註冊與入門"),
    "131": ("新手入門", "註冊與入門"),
    "204": ("新手入門", "學習資源"),
    "140": ("新手入門", "學習資源"),
    "200": ("新手入門", "學習資源"),
    "201": ("新手入門", "學習資源"),
    "118": ("新手入門", "網站單元介紹"),
    "119": ("新手入門", "網站單元介紹"),
    "120": ("新手入門", "網站單元介紹"),
    "121": ("新手入門", "網站單元介紹"),
    "122": ("新手入門", "網站單元介紹"),
    "123": ("新手入門", "網站單元介紹"),

    # ── 帳號與登入 ────────────────────────────────────────
    "116": ("帳號與登入", "登入問題"),
    "132": ("帳號與登入", "登入問題"),
    "133": ("帳號與登入", "登入問題"),
    "134": ("帳號與登入", "登入問題"),
    "135": ("帳號與登入", "登入問題"),
    "138": ("帳號與登入", "登入問題"),
    "108": ("帳號與登入", "帳號管理"),
    "109": ("帳號與登入", "帳號管理"),
    "110": ("帳號與登入", "帳號管理"),
    "126": ("帳號與登入", "帳號管理"),
    "127": ("帳號與登入", "帳號管理"),
    "136": ("帳號與登入", "帳號管理"),
    "137": ("帳號與登入", "帳號管理"),
    "139": ("帳號與登入", "帳號管理"),

    # ── 方案與訂閱 ────────────────────────────────────────
    "124": ("方案與訂閱", "訂閱方案介紹"),
    "125": ("方案與訂閱", "訂閱方案介紹"),
    "142": ("方案與訂閱", "訂閱方案介紹"),
    "145": ("方案與訂閱", "訂閱方案介紹"),
    "171": ("方案與訂閱", "訂閱方案介紹"),
    "106": ("方案與訂閱", "訂閱資訊"),
    "146": ("方案與訂閱", "訂閱資訊"),
    "147": ("方案與訂閱", "訂閱資訊"),
    "148": ("方案與訂閱", "訂閱資訊"),
    "149": ("方案與訂閱", "訂閱資訊"),
    "150": ("方案與訂閱", "訂閱資訊"),
    "151": ("方案與訂閱", "訂閱資訊"),
    "152": ("方案與訂閱", "訂閱資訊"),
    "153": ("方案與訂閱", "訂閱資訊"),
    "154": ("方案與訂閱", "訂閱資訊"),
    "155": ("方案與訂閱", "訂閱資訊"),
    "156": ("方案與訂閱", "訂閱資訊"),
    "157": ("方案與訂閱", "訂閱資訊"),
    "158": ("方案與訂閱", "訂閱資訊"),
    "159": ("方案與訂閱", "訂閱資訊"),
    "161": ("方案與訂閱", "訂閱資訊"),
    "170": ("方案與訂閱", "訂閱資訊"),
    "176": ("方案與訂閱", "推薦朋友與 M幣"),
    "174": ("方案與訂閱", "推薦朋友與 M幣"),
    "175": ("方案與訂閱", "推薦朋友與 M幣"),

    # ── 付款與帳務 ────────────────────────────────────────
    "112": ("付款與帳務", "付款方式"),
    "113": ("付款與帳務", "付款方式"),
    "160": ("付款與帳務", "付款方式"),
    "162": ("付款與帳務", "付款方式"),
    "163": ("付款與帳務", "付款方式"),
    "164": ("付款與帳務", "付款方式"),
    "165": ("付款與帳務", "付款方式"),
    "166": ("付款與帳務", "付款方式"),
    "167": ("付款與帳務", "付款方式"),
    "168": ("付款與帳務", "發票與帳單"),
    "169": ("付款與帳務", "發票與帳單"),
    "172": ("付款與帳務", "發票與帳單"),
    "173": ("付款與帳務", "發票與帳單"),
    "206": ("付款與帳務", "發票與帳單"),

    # ── 功能操作指南 ──────────────────────────────────────
    "098": ("功能操作指南", "企業功能"),
    "099": ("功能操作指南", "數據下載"),
    "100": ("功能操作指南", "數據下載"),
    "101": ("功能操作指南", "數據下載"),
    "102": ("功能操作指南", "數據下載"),
    "103": ("功能操作指南", "數據下載"),
    "107": ("功能操作指南", "數據下載"),
    "182": ("功能操作指南", "數據下載"),
    "111": ("功能操作指南", "圖表功能"),
    "114": ("功能操作指南", "圖表功能"),
    "129": ("功能操作指南", "圖表功能"),
    "177": ("功能操作指南", "圖表功能"),
    "178": ("功能操作指南", "圖表功能"),
    "180": ("功能操作指南", "圖表功能"),
    "181": ("功能操作指南", "圖表功能"),
    "183": ("功能操作指南", "圖表功能"),
    "115": ("功能操作指南", "報告與授權"),
    "185": ("功能操作指南", "報告與授權"),
    "187": ("功能操作指南", "報告與授權"),
    "203": ("功能操作指南", "報告與授權"),
    "141": ("功能操作指南", "通知設定"),
    "143": ("功能操作指南", "通知設定"),
    "144": ("功能操作指南", "通知設定"),
    "179": ("功能操作指南", "總經知識"),
    "184": ("功能操作指南", "總經知識"),
    "196": ("功能操作指南", "財經日曆"),
    "197": ("功能操作指南", "財經日曆"),
    "199": ("功能操作指南", "API 服務"),
    "202": ("功能操作指南", "其他功能"),
    "205": ("功能操作指南", "其他功能"),

    # ── 總經線上學院 ──────────────────────────────────────
    "104": ("總經線上學院", "Podcast"),
    "128": ("總經線上學院", "課程介紹"),
    "186": ("總經線上學院", "課程購買"),
    "188": ("總經線上學院", "課程購買"),
    "189": ("總經線上學院", "課程購買"),
    "190": ("總經線上學院", "課程購買"),
    "191": ("總經線上學院", "課程購買"),
    "192": ("總經線上學院", "課程購買"),
    "193": ("總經線上學院", "課程使用"),
    "194": ("總經線上學院", "課程使用"),
    "195": ("總經線上學院", "課程使用"),
    "198": ("總經線上學院", "Podcast"),
}


def rebuild_index(content_dir: Path, index_file: Path):
    index = []
    for md_file in sorted(content_dir.rglob("*.md")):
        post = frontmatter.load(str(md_file))
        meta = post.metadata
        rel_path = md_file.relative_to(content_dir)
        index.append({
            "id": meta.get("id", ""),
            "category": meta.get("category", ""),
            "section": meta.get("section", ""),
            "title": meta.get("title", {}),
            "status": meta.get("status", "draft"),
            "locales": meta.get("locales", {"zh-tw": True, "zh-cn": True, "en": True}),
            "order": meta.get("order", 0),
            "file": str(rel_path),
        })
    index.sort(key=lambda x: x.get("id", ""))
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"Rebuilt index.json with {len(index)} entries.")


def main():
    # 1. Delete all non-Zendesk content
    print("Deleting old articles...")
    deleted = 0
    for md_file in list(CONTENT_DIR.rglob("*.md")):
        post = frontmatter.load(str(md_file))
        if "zendesk_id" not in post.metadata:
            md_file.unlink()
            deleted += 1
    # Clean up empty directories
    for d in sorted(CONTENT_DIR.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    print(f"Deleted {deleted} old articles.")

    # 2. Move Zendesk articles to correct categories
    print("Reorganizing Zendesk articles...")
    moved = 0
    unmapped = []
    for md_file in list(CONTENT_DIR.rglob("*.md")):
        post = frontmatter.load(str(md_file))
        faq_id = post.metadata.get("id", "")
        if faq_id not in CATEGORY_MAP:
            unmapped.append((faq_id, post.metadata.get("title", {}).get("zh-tw", "")))
            continue
        category, section = CATEGORY_MAP[faq_id]
        target_dir = CONTENT_DIR / category / section
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / md_file.name
        if md_file != target_path:
            post.metadata["category"] = category
            post.metadata["section"] = section
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
            md_file.unlink()
            moved += 1

    # Clean up empty dirs again
    for d in sorted(CONTENT_DIR.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    print(f"Moved {moved} articles to proper categories.")
    if unmapped:
        print(f"Unmapped ({len(unmapped)} articles → left in 未分類):")
        for fid, title in unmapped:
            print(f"  [{fid}] {title}")

    rebuild_index(CONTENT_DIR, INDEX_FILE)


if __name__ == "__main__":
    main()
