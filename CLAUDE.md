# MacroMicro FAQ 幫助中心

## 專案概述

取代 Zendesk 的自建 FAQ 系統。Python + FastAPI 後端，Markdown 檔案作為內容資料庫，支援三語系（繁中/簡中/英文），只需維護繁中內容，未來可加自動翻譯。

## 技術架構

- **後端**：Python 3.13 + FastAPI
- **模板**：Jinja2
- **內容格式**：Markdown + YAML frontmatter
- **樣式**：純 CSS（MacroMicro 品牌色系）
- **無資料庫**：所有資料存在 Markdown 檔案 + index.json

## 啟動方式

```bash
cd faq
pip3 install fastapi uvicorn jinja2 python-frontmatter markdown python-multipart
python3 app.py
# → http://localhost:8000 (前台)
# → http://localhost:8000/admin (後台，前台不顯示連結)
```

## 目錄結構

```
faq/
├── app.py                  # FastAPI 主程式（路由 + API）
├── index.json              # FAQ 索引（自動產生，勿手動編輯）
├── requirements.txt
├── content/                # FAQ 內容（Markdown + frontmatter）
│   ├── 方案與訂閱/
│   │   ├── 訂閱資訊/
│   │   │   ├── 008-取消訂閱後...md
│   │   │   └── ...
│   │   ├── 推薦朋友與-M幣/
│   │   └── ...
│   ├── 付款與帳務/
│   ├── 功能操作指南/
│   ├── 帳號與登入/
│   ├── 新手入門/
│   ├── 總經線上學院/
│   └── 未分類/
├── static/
│   ├── css/style.css       # 全站樣式（MM 品牌色系）
│   ├── logo.svg            # MacroMicro logo
│   └── uploads/            # 後台上傳的圖片
├── templates/
│   ├── base.html           # 共用模板（header, nav, footer）
│   ├── index.html          # 首頁（分類卡片 + 搜尋框）
│   ├── category.html       # 分類頁（段落 > 文章列表）
│   ├── faq_detail.html     # FAQ 內文頁（含延伸閱讀）
│   ├── search.html         # 搜尋結果頁
│   ├── admin.html          # 後台列表頁
│   └── admin_edit.html     # 後台編輯頁
└── scripts/
    ├── import_excel.py     # 從 Excel 匯入 FAQ 到 Markdown
    └── auto_link.py        # 自動將關鍵字轉為超連結
```

## FAQ Markdown 格式

每篇 FAQ 是一個 `.md` 檔，格式如下：

```markdown
---
id: "008"
category: 方案與訂閱
section: 訂閱資訊
order: 1
status: "published"         # published / draft / archived
locales:
  zh-tw: true               # 繁中必定 true
  zh-cn: true               # 可個別控制是否顯示
  en: true
title:
  zh-tw: 取消訂閱後，會員期間收到的報告還能觀看嗎？
  zh-cn: 取消订阅后，会员期间收到的报告还能观看吗？
  en: "Can I still view reports after canceling?"
---

繁體中文內容（預設）

<!--locale:zh-cn-->

簡體中文內容

<!--locale:en-->

English content here.
```

### 重點規則
- **三層結構**：類別（category）> 段落（section）> 文章
- **語系分隔**：用 `<!--locale:zh-cn-->` 和 `<!--locale:en-->` 分隔
- **上下架**：改 `status` 欄位（published/draft/archived）
- **語系顯示控制**：`locales` 裡的 true/false 決定該語系是否顯示

## 功能清單

### 前台（/）
- 首頁：搜尋框 + 分類卡片（7 個類別）
- 分類頁：該類別下的段落和文章列表
- FAQ 內文頁：Markdown 渲染 + 延伸閱讀（同段落/同類別推薦）
- 搜尋：全文搜尋（標題 + 內容）
- 三語切換：繁中/簡中/英文

### 後台（/admin）
- FAQ 列表：篩選狀態/類別、直接切換上下架、勾選語系
- 編輯頁（/admin/edit/{id}）：
  - 基本資訊：ID、狀態、類別、段落、語系勾選
  - 三語標題編輯
  - 三語內容 Markdown 編輯（Tab 切換）
  - 工具列：插入連結、上傳圖片、粗體、標題、清單、表格編輯器
  - 儲存後同時更新 .md 檔和 index.json

### API（AI 可讀）
- `GET /api/faqs?locale=zh-tw&category=&status=published` — 列表
- `GET /api/faq/{id}?locale=zh-tw` — 單篇內容（Markdown 原文）
- `POST /api/faq/{id}/save` — 儲存編輯
- `POST /api/faq/{id}/status` — 更新狀態
- `POST /api/faq/{id}/locales` — 更新語系
- `POST /api/upload` — 上傳圖片

## 品牌色系（MacroMicro）

```css
--mm-primary: #50e3c2;     /* 主色（綠） */
--mm-blue: #199b7e;        /* 連結色 */
--mm-pro: #77A88d;
--mm-prime: #365C53;       /* 深綠 */
--mm-biz: #19435C;
--mm-max: #0F2219;
```

字型：`-apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif`

## 腳本說明

### import_excel.py
從 Excel 檔（`FAQ_三語版.xlsx`，sheet「FAQ 語氣優化全版（97條）」）匯入 FAQ 到 Markdown 檔案 + 產生 index.json。

### auto_link.py
掃描所有 FAQ 內容，自動：
1. 將 `文字（URL）` 轉成 `[文字](URL)` Markdown 超連結
2. 偵測關鍵字（如「訂閱方案」「研究工具箱」等）並插入對應的 MacroMicro 頁面連結
3. 支援三語系各自的關鍵字 → URL 對照

用法：
```bash
python3 scripts/auto_link.py --dry-run  # 預覽不改檔
python3 scripts/auto_link.py            # 正式執行
```

## 重建 index.json

如果手動修改了 content/ 下的 .md 檔案，需要重建索引：

```python
python3 -c "
import json, frontmatter
from pathlib import Path
content_dir = Path('content')
index = []
for md_file in sorted(content_dir.rglob('*.md')):
    post = frontmatter.load(str(md_file))
    meta = post.metadata
    rel_path = md_file.relative_to(content_dir)
    index.append({
        'id': meta.get('id', ''),
        'category': meta.get('category', ''),
        'section': meta.get('section', ''),
        'title': meta.get('title', {}),
        'status': meta.get('status', 'draft'),
        'locales': meta.get('locales', {'zh-tw': True, 'zh-cn': True, 'en': True}),
        'order': meta.get('order', 0),
        'file': str(rel_path),
    })
index.sort(key=lambda x: x.get('id', ''))
with open('index.json', 'w', encoding='utf-8') as f:
    json.dump(index, f, ensure_ascii=False, indent=2)
"
```

## 待開發功能

- **自動翻譯**：只維護繁中，用 AI 翻譯成簡中和英文（翻譯方案待定）
- **新增 FAQ**：目前需手動建 .md 檔或從後台複製，可加「新增」按鈕
- **MacroMicro URL 參考**：所有頁面 URL 在 skills/macromicro-knowledge/references/urls.md
- **訂閱方案資料**：在 skills/macromicro-knowledge/references/subscription.md

## 注意事項

- 前台不顯示 Admin 連結，後台透過 `/admin` 直接進入
- `index.json` 是自動產生的索引，透過後台編輯會自動更新
- 圖片上傳到 `static/uploads/`，用時間戳命名
- MacroMicro 三語系 URL 規則：繁中 `www`、簡中 `sc`、英文 `en`，路徑相同
