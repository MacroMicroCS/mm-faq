"""MacroMicro FAQ System - FastAPI Application."""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import frontmatter
import markdown
from fastapi import FastAPI, Request, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="MacroMicro FAQ")
BASE_DIR = Path(__file__).parent
CONTENT_DIR = BASE_DIR / "content"
INDEX_PATH = BASE_DIR / "index.json"

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

LOCALE_NAMES = {"zh-tw": "繁體中文", "zh-cn": "简体中文", "en": "English"}


def load_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_index(data):
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_faq(file_path: str):
    full_path = CONTENT_DIR / file_path
    if not full_path.exists():
        return None
    post = frontmatter.load(str(full_path))
    return post


def get_content_by_locale(post, locale: str) -> str:
    raw = post.content
    sections = re.split(r'<!--locale:(\S+?)-->', raw)
    # sections[0] = zh-tw content
    # sections[1] = "zh-cn", sections[2] = zh-cn content
    # sections[3] = "en", sections[4] = en content
    if locale == "zh-tw":
        return sections[0].strip()
    for i in range(1, len(sections), 2):
        if sections[i].strip() == locale and i + 1 < len(sections):
            return sections[i + 1].strip()
    return sections[0].strip()


def get_categories(index, locale="zh-tw"):
    cats = {}
    for item in index:
        if item["status"] != "published":
            continue
        if not item["locales"].get(locale, False):
            continue
        cat = item["category"]
        sec = item["section"]
        if cat not in cats:
            cats[cat] = {}
        if sec not in cats[cat]:
            cats[cat][sec] = []
        cats[cat][sec].append(item)
    # Sort items by order
    for cat in cats:
        for sec in cats[cat]:
            cats[cat][sec].sort(key=lambda x: x.get("order", 0))
    return cats


CATEGORY_ICONS = {
    "新手入門": "rocket",
    "方案與訂閱": "credit-card",
    "帳號與登入": "user",
    "付款與帳務": "dollar-sign",
    "功能操作指南": "tool",
    "總經線上學院": "book-open",
}


def get_category_list(index, locale="zh-tw"):
    cats = {}
    for item in index:
        if item["status"] != "published":
            continue
        if not item["locales"].get(locale, False):
            continue
        cat = item["category"]
        if cat not in cats:
            cats[cat] = 0
        cats[cat] += 1
    return cats


def get_related_faqs(index, current_item, locale="zh-tw", limit=5):
    related = []
    for item in index:
        if item["id"] == current_item["id"]:
            continue
        if item["status"] != "published":
            continue
        if not item["locales"].get(locale, False):
            continue
        if item["section"] == current_item["section"]:
            related.append(item)
    if len(related) < limit:
        for item in index:
            if item["id"] == current_item["id"]:
                continue
            if item in related:
                continue
            if item["status"] != "published":
                continue
            if not item["locales"].get(locale, False):
                continue
            if item["category"] == current_item["category"]:
                related.append(item)
            if len(related) >= limit:
                break
    return related[:limit]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, locale: str = Query("zh-tw")):
    index = load_index()
    category_list = get_category_list(index, locale)
    return templates.TemplateResponse(request, "index.html", context={
        "category_list": category_list,
        "category_icons": CATEGORY_ICONS,
        "locale": locale,
        "locale_names": LOCALE_NAMES,
    })


@app.get("/category/{category_name}", response_class=HTMLResponse)
async def category_page(request: Request, category_name: str, locale: str = Query("zh-tw")):
    index = load_index()
    categories = get_categories(index, locale)
    sections = categories.get(category_name, {})
    if not sections:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)
    return templates.TemplateResponse(request, "category.html", context={
        "category_name": category_name,
        "sections": sections,
        "locale": locale,
        "locale_names": LOCALE_NAMES,
    })


@app.get("/faq/{faq_id}", response_class=HTMLResponse)
async def faq_detail(request: Request, faq_id: str, locale: str = Query("zh-tw")):
    index = load_index()
    item = next((i for i in index if i["id"] == faq_id), None)
    if not item:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    post = load_faq(item["file"])
    if not post:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    content_md = get_content_by_locale(post, locale)
    content_html = markdown.markdown(content_md, extensions=["tables", "fenced_code"])
    title = item["title"].get(locale, item["title"]["zh-tw"])
    related = get_related_faqs(index, item, locale)

    return templates.TemplateResponse(request, "faq_detail.html", context={
        "item": item,
        "title": title,
        "content_html": content_html,
        "related": related,
        "locale": locale,
        "locale_names": LOCALE_NAMES,
    })


@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "", locale: str = Query("zh-tw")):
    index = load_index()
    results = []
    if q:
        q_lower = q.lower()
        for item in index:
            if item["status"] != "published":
                continue
            if not item["locales"].get(locale, False):
                continue
            title = item["title"].get(locale, item["title"]["zh-tw"])
            if q_lower in title.lower():
                results.append(item)
                continue
            post = load_faq(item["file"])
            if post:
                content = get_content_by_locale(post, locale)
                if q_lower in content.lower():
                    results.append(item)
    return templates.TemplateResponse(request, "search.html", context={
        "query": q,
        "results": results,
        "locale": locale,
        "locale_names": LOCALE_NAMES,
    })


# === Admin API ===

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    index = load_index()
    return templates.TemplateResponse(request, "admin.html", context={
        "faqs": index,
        "locale_names": LOCALE_NAMES,
    })


@app.get("/admin/edit/{faq_id}", response_class=HTMLResponse)
async def admin_edit_page(request: Request, faq_id: str):
    index = load_index()
    item = next((i for i in index if i["id"] == faq_id), None)
    if not item:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    post = load_faq(item["file"])
    if not post:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    content_zhtw = get_content_by_locale(post, "zh-tw")
    content_zhcn = get_content_by_locale(post, "zh-cn")
    content_en = get_content_by_locale(post, "en")

    return templates.TemplateResponse(request, "admin_edit.html", context={
        "item": item,
        "content_zhtw": content_zhtw,
        "content_zhcn": content_zhcn,
        "content_en": content_en,
        "locale_names": LOCALE_NAMES,
    })


@app.post("/api/faq/{faq_id}/status")
async def update_status(faq_id: str, request: Request):
    body = await request.json()
    new_status = body.get("status")
    if new_status not in ("published", "draft", "archived"):
        return JSONResponse({"error": "Invalid status"}, status_code=400)

    index = load_index()
    item = next((i for i in index if i["id"] == faq_id), None)
    if not item:
        return JSONResponse({"error": "Not found"}, status_code=404)

    item["status"] = new_status

    # Update frontmatter in markdown file
    full_path = CONTENT_DIR / item["file"]
    post = frontmatter.load(str(full_path))
    post.metadata["status"] = new_status
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post) + "\n")

    save_index(index)
    return JSONResponse({"ok": True, "status": new_status})


@app.post("/api/faq/{faq_id}/save")
async def save_faq(faq_id: str, request: Request):
    body = await request.json()
    index = load_index()
    item = next((i for i in index if i["id"] == faq_id), None)
    if not item:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Update title
    if "title" in body:
        for loc in ["zh-tw", "zh-cn", "en"]:
            if loc in body["title"]:
                item["title"][loc] = body["title"][loc]

    # Update status
    if "status" in body and body["status"] in ("published", "draft", "archived"):
        item["status"] = body["status"]

    # Update locales
    if "locales" in body:
        for loc in ["zh-tw", "zh-cn", "en"]:
            if loc in body["locales"]:
                item["locales"][loc] = bool(body["locales"][loc])

    # Update category / section
    if "category" in body:
        item["category"] = body["category"]
    if "section" in body:
        item["section"] = body["section"]

    # Update markdown content
    full_path = CONTENT_DIR / item["file"]
    post = frontmatter.load(str(full_path))
    post.metadata["status"] = item["status"]
    post.metadata["locales"] = item["locales"]
    post.metadata["title"] = item["title"]
    post.metadata["category"] = item["category"]
    post.metadata["section"] = item["section"]

    # Rebuild content with locale markers
    content_parts = [body.get("content_zhtw", "").strip()]
    zhcn = body.get("content_zhcn", "").strip()
    en = body.get("content_en", "").strip()
    if zhcn:
        content_parts.append(f"\n<!--locale:zh-cn-->\n{zhcn}")
    if en:
        content_parts.append(f"\n<!--locale:en-->\n{en}")
    post.content = "\n".join(content_parts)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post) + "\n")

    save_index(index)
    return JSONResponse({"ok": True})


@app.post("/api/faq/{faq_id}/locales")
async def update_locales(faq_id: str, request: Request):
    body = await request.json()
    locales = body.get("locales", {})

    index = load_index()
    item = next((i for i in index if i["id"] == faq_id), None)
    if not item:
        return JSONResponse({"error": "Not found"}, status_code=404)

    for loc in ["zh-tw", "zh-cn", "en"]:
        if loc in locales:
            item["locales"][loc] = bool(locales[loc])

    # Update frontmatter
    full_path = CONTENT_DIR / item["file"]
    post = frontmatter.load(str(full_path))
    post.metadata["locales"] = item["locales"]
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post) + "\n")

    save_index(index)
    return JSONResponse({"ok": True, "locales": item["locales"]})


@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    # Validate file type
    allowed = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        return JSONResponse({"error": f"不支援的檔案格式: {ext}"}, status_code=400)

    # Generate unique filename
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    unique = uuid.uuid4().hex[:6]
    filename = f"{ts}_{unique}{ext}"

    upload_dir = BASE_DIR / "static" / "uploads"
    upload_dir.mkdir(exist_ok=True)
    filepath = upload_dir / filename

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    url = f"/static/uploads/{filename}"
    md_code = f"![{file.filename}]({url})"
    return JSONResponse({"ok": True, "url": url, "markdown": md_code, "filename": filename})


# === AI-friendly API ===

@app.get("/api/faqs")
async def api_list_faqs(locale: str = "zh-tw", category: Optional[str] = None, status: str = "published"):
    index = load_index()
    results = []
    for item in index:
        if item["status"] != status:
            continue
        if category and item["category"] != category:
            continue
        if not item["locales"].get(locale, False):
            continue
        results.append({
            "id": item["id"],
            "category": item["category"],
            "section": item["section"],
            "title": item["title"].get(locale, item["title"]["zh-tw"]),
        })
    return results


@app.get("/api/faq/{faq_id}")
async def api_get_faq(faq_id: str, locale: str = "zh-tw"):
    index = load_index()
    item = next((i for i in index if i["id"] == faq_id), None)
    if not item:
        return JSONResponse({"error": "Not found"}, status_code=404)

    post = load_faq(item["file"])
    if not post:
        return JSONResponse({"error": "Not found"}, status_code=404)

    content = get_content_by_locale(post, locale)
    title = item["title"].get(locale, item["title"]["zh-tw"])
    return {
        "id": item["id"],
        "category": item["category"],
        "section": item["section"],
        "title": title,
        "content": content,
        "locales": item["locales"],
        "status": item["status"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
