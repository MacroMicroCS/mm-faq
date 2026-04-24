"""
Import Zendesk CSV exports into the FAQ Markdown system.

Usage:
    python3 scripts/import_zendesk.py \
        --tc zendesk_tc.csv \
        --sc zendesk_sc.csv \
        --en zendesk_en.csv

The three CSV files must each have columns: id, Title, Body (tab-separated or comma-separated).
Articles are matched across languages by their Zendesk article ID.
All imported articles land in content/未分類/ with status=draft.
Run from the faq/ directory.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import frontmatter
from markdownify import markdownify as md


CONTENT_DIR = Path("content")
INDEX_FILE = Path("index.json")
DEFAULT_CATEGORY = "未分類"
DEFAULT_SECTION = "Zendesk 匯入"


def detect_delimiter(path: str) -> str:
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        sample = f.read(4096)
    tabs = sample.count("\t")
    commas = sample.count(",")
    return "\t" if tabs > commas else ","


def read_csv(path: str) -> dict:
    """Return {article_id: {title, body}} from a Zendesk CSV export."""
    if not path:
        return {}
    delim = detect_delimiter(path)
    rows = {}
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            # Zendesk exports use 'id', 'Title', 'Body' headers
            raw_id = row.get("id", row.get("Id", "")).strip()
            title = row.get("Title", row.get("title", "")).strip()
            body = row.get("Body", row.get("body", "")).strip()
            if not raw_id:
                continue
            # Normalise scientific notation IDs (e.g. 1.55683E+13 → 15568300000000)
            try:
                article_id = str(int(float(raw_id)))
            except ValueError:
                article_id = raw_id
            rows[article_id] = {"title": title, "body": body}
    return rows


def html_to_markdown(html: str) -> str:
    if not html:
        return ""
    text = md(
        html,
        heading_style="ATX",
        bullets="-",
        newline_style="backslash",
        strip=["script", "style"],
    )
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(text: str, max_len: int = 40) -> str:
    text = re.sub(r"[^\w一-鿿㐀-䶿]", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:max_len]


def next_id(content_dir: Path) -> str:
    """Find the highest numeric FAQ ID in use and return the next one."""
    existing = []
    for md_file in content_dir.rglob("*.md"):
        post = frontmatter.load(str(md_file))
        faq_id = post.metadata.get("id", "")
        try:
            existing.append(int(faq_id))
        except (ValueError, TypeError):
            pass
    if not existing:
        return "001"
    return str(max(existing) + 1).zfill(3)


def rebuild_index(content_dir: Path, index_file: Path):
    index = []
    for md_file in sorted(content_dir.rglob("*.md")):
        post = frontmatter.load(str(md_file))
        meta = post.metadata
        rel_path = md_file.relative_to(content_dir)
        index.append(
            {
                "id": meta.get("id", ""),
                "category": meta.get("category", ""),
                "section": meta.get("section", ""),
                "title": meta.get("title", {}),
                "status": meta.get("status", "draft"),
                "locales": meta.get(
                    "locales", {"zh-tw": True, "zh-cn": True, "en": True}
                ),
                "order": meta.get("order", 0),
                "file": str(rel_path),
            }
        )
    index.sort(key=lambda x: x.get("id", ""))
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"Rebuilt {index_file} with {len(index)} entries.")


def main():
    parser = argparse.ArgumentParser(description="Import Zendesk CSV into FAQ system")
    parser.add_argument("--tc", default="", help="Path to zendesk_tc.csv")
    parser.add_argument("--sc", default="", help="Path to zendesk_sc.csv")
    parser.add_argument("--en", default="", help="Path to zendesk_en.csv")
    parser.add_argument(
        "--category", default=DEFAULT_CATEGORY, help="Target category"
    )
    parser.add_argument(
        "--section", default=DEFAULT_SECTION, help="Target section"
    )
    parser.add_argument(
        "--status", default="draft", choices=["draft", "published", "archived"]
    )
    args = parser.parse_args()

    if not any([args.tc, args.sc, args.en]):
        parser.print_help()
        sys.exit(1)

    print("Reading CSV files…")
    tc_rows = read_csv(args.tc) if args.tc else {}
    sc_rows = read_csv(args.sc) if args.sc else {}
    en_rows = read_csv(args.en) if args.en else {}

    # Use TC IDs as primary; fall back to SC or EN
    all_ids = set(tc_rows) | set(sc_rows) | set(en_rows)
    print(f"Found {len(all_ids)} unique article IDs.")

    target_dir = CONTENT_DIR / args.category / args.section
    target_dir.mkdir(parents=True, exist_ok=True)

    # Find next available sequential FAQ ID
    current_max = 0
    for md_file in CONTENT_DIR.rglob("*.md"):
        post = frontmatter.load(str(md_file))
        faq_id = post.metadata.get("id", "")
        try:
            current_max = max(current_max, int(faq_id))
        except (ValueError, TypeError):
            pass

    created = 0
    for order, zendesk_id in enumerate(sorted(all_ids), start=1):
        tc = tc_rows.get(zendesk_id, {})
        sc = sc_rows.get(zendesk_id, {})
        en = en_rows.get(zendesk_id, {})

        title_tw = tc.get("title", sc.get("title", en.get("title", "")))
        title_sc = sc.get("title", "")
        title_en = en.get("title", "")

        body_tw = html_to_markdown(tc.get("body", ""))
        body_sc = html_to_markdown(sc.get("body", ""))
        body_en = html_to_markdown(en.get("body", ""))

        current_max += 1
        faq_id = str(current_max).zfill(3)

        slug = slugify(title_tw or title_en or zendesk_id)
        filename = f"{faq_id}-{slug}.md"
        filepath = target_dir / filename

        # Build multi-locale content body
        content_parts = [body_tw]
        if body_sc:
            content_parts.append(f"\n<!--locale:zh-cn-->\n\n{body_sc}")
        if body_en:
            content_parts.append(f"\n<!--locale:en-->\n\n{body_en}")
        full_content = "\n".join(content_parts)

        post = frontmatter.Post(
            full_content,
            id=faq_id,
            zendesk_id=zendesk_id,
            category=args.category,
            section=args.section,
            order=order,
            status=args.status,
            locales={
                "zh-tw": bool(body_tw),
                "zh-cn": bool(body_sc),
                "en": bool(body_en),
            },
            title={
                "zh-tw": title_tw,
                "zh-cn": title_sc,
                "en": title_en,
            },
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

        created += 1
        if created % 10 == 0:
            print(f"  {created}/{len(all_ids)} articles written…")

    print(f"Done. {created} articles written to {target_dir}")
    rebuild_index(CONTENT_DIR, INDEX_FILE)


if __name__ == "__main__":
    main()
