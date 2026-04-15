"""
Auto-link script: Convert plain-text URLs in FAQ markdown files to proper Markdown links.

Handles patterns like:
  文字（https://...）  →  [文字](https://...)
  文字(https://...)   →  [文字](https://...)
  文字 (https://...)  →  [文字](https://...)

Also detects keyword mentions without URLs and inserts appropriate links.
"""
import re
import sys
from pathlib import Path

CONTENT_DIR = Path(__file__).parent.parent / "content"

# ============================================================
# 1. Keyword → URL mapping (for mentions WITHOUT existing URLs)
#    Only insert link on first occurrence per locale section.
# ============================================================
KEYWORD_MAP_ZHTW = {
    # 方案
    "訂閱方案": "https://www.macromicro.me/subscribe",
    "方案比較": "https://www.macromicro.me/subscribe",
    # 功能頁面
    "操盤人必看": "https://www.macromicro.me/trader-insights",
    "外匯觀測站": "https://www.macromicro.me/forex",
    "股市觀測站": "https://www.macromicro.me/stocks",
    "ETF觀測站": "https://www.macromicro.me/etf",
    "ETF 觀測站": "https://www.macromicro.me/etf",
    "原物料觀測站": "https://www.macromicro.me/commodities",
    "債券觀測站": "https://www.macromicro.me/bonds",
    "加密貨幣觀測站": "https://www.macromicro.me/crypto",
    "波動率觀測站": "https://www.macromicro.me/volatility",
    "產業決策平台": "https://www.macromicro.me/industry-intelligence-hub",
    "美股財報資料庫": "https://www.macromicro.me/stocks/screener",
    "台灣產業專區": "https://www.macromicro.me/sectors",
    "國家數據中心": "https://www.macromicro.me/cross-country-database",
    "央行專區": "https://www.macromicro.me/central_bank/overview",
    "原物料專區": "https://www.macromicro.me/commodities/overview",
    "13F機構持倉": "https://www.macromicro.me/13f",
    "大額交易人持倉": "https://www.macromicro.me/cot-flow",
    "時間軸": "https://www.macromicro.me/time_line",
    # 分析
    "MM獨家報告": "https://www.macromicro.me/mails/monthly_report",
    "MM 獨家報告": "https://www.macromicro.me/mails/monthly_report",
    "MM短評": "https://www.macromicro.me/quickie",
    "MM 短評": "https://www.macromicro.me/quickie",
    "關鍵圖表": "https://www.macromicro.me/spotlights",
    # 工具
    "財經行事曆": "https://www.macromicro.me/calendar",
    "財經日曆": "https://www.macromicro.me/calendar",
    "研究工具箱": "https://www.macromicro.me/toolbox/chart-builder/line",
    "工具箱": "https://www.macromicro.me/toolbox/chart-builder/line",
    # 學院
    "線上學院": "https://www.macromicro.me/video",
    "用戶觀點": "https://www.macromicro.me/shared_chart",
    # 會員
    "MM福利兌換": "https://www.macromicro.me/user/mm-benefits",
    "MM 福利兌換": "https://www.macromicro.me/user/mm-benefits",
    "我的M幣": "https://www.macromicro.me/user/mcoins",
    "我的儀表板": "https://www.macromicro.me/user/dashboards",
    "會員檔案": "https://www.macromicro.me/user/settings",
    "推薦碼": "https://www.macromicro.me/user/mm-benefits",
    # 其他
    "新手教學": "https://www.macromicro.me/getting-started",
    "聯絡我們": "https://www.macromicro.me/contact-us",
    "服務條款": "https://www.macromicro.me/terms",
}

KEYWORD_MAP_ZHCN = {
    "订阅方案": "https://sc.macromicro.me/subscribe",
    "方案比较": "https://sc.macromicro.me/subscribe",
    "操盘人必看": "https://sc.macromicro.me/trader-insights",
    "外汇观测站": "https://sc.macromicro.me/forex",
    "股市观测站": "https://sc.macromicro.me/stocks",
    "ETF观测站": "https://sc.macromicro.me/etf",
    "ETF 观测站": "https://sc.macromicro.me/etf",
    "原物料观测站": "https://sc.macromicro.me/commodities",
    "债券观测站": "https://sc.macromicro.me/bonds",
    "加密货币观测站": "https://sc.macromicro.me/crypto",
    "波动率观测站": "https://sc.macromicro.me/volatility",
    "产业决策平台": "https://sc.macromicro.me/industry-intelligence-hub",
    "美股财报数据库": "https://sc.macromicro.me/stocks/screener",
    "台湾产业专区": "https://sc.macromicro.me/sectors",
    "国家数据中心": "https://sc.macromicro.me/cross-country-database",
    "央行专区": "https://sc.macromicro.me/central_bank/overview",
    "原物料专区": "https://sc.macromicro.me/commodities/overview",
    "13F机构持仓": "https://sc.macromicro.me/13f",
    "大额交易人持仓": "https://sc.macromicro.me/cot-flow",
    "时间轴": "https://sc.macromicro.me/time_line",
    "MM独家报告": "https://sc.macromicro.me/mails/monthly_report",
    "MM 独家报告": "https://sc.macromicro.me/mails/monthly_report",
    "MM短评": "https://sc.macromicro.me/quickie",
    "MM 短评": "https://sc.macromicro.me/quickie",
    "关键图表": "https://sc.macromicro.me/spotlights",
    "财经行事历": "https://sc.macromicro.me/calendar",
    "财经日历": "https://sc.macromicro.me/calendar",
    "研究工具箱": "https://sc.macromicro.me/toolbox/chart-builder/line",
    "工具箱": "https://sc.macromicro.me/toolbox/chart-builder/line",
    "线上学院": "https://sc.macromicro.me/video",
    "用户观点": "https://sc.macromicro.me/shared_chart",
    "MM福利兑换": "https://sc.macromicro.me/user/mm-benefits",
    "MM 福利兑换": "https://sc.macromicro.me/user/mm-benefits",
    "我的M币": "https://sc.macromicro.me/user/mcoins",
    "我的仪表板": "https://sc.macromicro.me/user/dashboards",
    "会员档案": "https://sc.macromicro.me/user/settings",
    "推荐码": "https://sc.macromicro.me/user/mm-benefits",
    "新手教程": "https://sc.macromicro.me/getting-started",
    "联系我们": "https://sc.macromicro.me/contact-us",
    "服务条款": "https://sc.macromicro.me/terms",
}

KEYWORD_MAP_EN = {
    "subscription plans": "https://en.macromicro.me/subscribe",
    "Trader's Insights": "https://en.macromicro.me/trader-insights",
    "Trader Insights": "https://en.macromicro.me/trader-insights",
    "Forex Observatory": "https://en.macromicro.me/forex",
    "Stock Observatory": "https://en.macromicro.me/stocks",
    "ETF Observatory": "https://en.macromicro.me/etf",
    "Commodities Observatory": "https://en.macromicro.me/commodities",
    "Bond Observatory": "https://en.macromicro.me/bonds",
    "Crypto Observatory": "https://en.macromicro.me/crypto",
    "Industry Intelligence Hub": "https://en.macromicro.me/industry-intelligence-hub",
    "US Stock Screener": "https://en.macromicro.me/stocks/screener",
    "Cross-Country Database": "https://en.macromicro.me/cross-country-database",
    "Central Bank": "https://en.macromicro.me/central_bank/overview",
    "13F Holdings": "https://en.macromicro.me/13f",
    "MM Report": "https://en.macromicro.me/mails/monthly_report",
    "MM Daily": "https://en.macromicro.me/quickie",
    "Key Charts": "https://en.macromicro.me/spotlights",
    "Economic Calendar": "https://en.macromicro.me/calendar",
    "Research Toolbox": "https://en.macromicro.me/toolbox/chart-builder/line",
    "Toolbox": "https://en.macromicro.me/toolbox/chart-builder/line",
    "Online Academy": "https://en.macromicro.me/video",
    "User Charts": "https://en.macromicro.me/shared_chart",
    "MM Benefits": "https://en.macromicro.me/user/mm-benefits",
    "Getting Started": "https://en.macromicro.me/getting-started",
    "Contact Us": "https://en.macromicro.me/contact-us",
    "Terms of Service": "https://en.macromicro.me/terms",
}


def convert_inline_urls(text):
    """
    Convert plain-text URL patterns to proper Markdown links.

    Real-world patterns found in FAQ files:
      「MM 福利兌換」頁面（URL）  →  [MM 福利兌換](URL)頁面
      「圖表 > 操盤人必看」（URL）→  [圖表 > 操盤人必看](URL)
      MM全球財經日曆（URL）       →  [MM全球財經日曆](URL)
      企業方案(URL)               →  [企業方案](URL)
      相關課程（URL）             →  [相關課程](URL)
      User Charts page (URL)      →  [User Charts page](URL)
    """
    # Skip lines that are already markdown links
    # Process line by line to avoid cross-line issues
    lines = text.split('\n')
    result_lines = []

    for line in lines:
        # Skip if line has no URL
        if 'http' not in line:
            result_lines.append(line)
            continue

        # Skip if already a proper markdown link on this line
        # (has ](http pattern — already converted)
        # We still process because there might be OTHER URLs on the line

        # Pattern 1: 「text」optional-suffix（URL）or 「text」optional-suffix(URL)
        # Capture text inside「」as the label, discard suffix like 頁面/單元/中
        line = re.sub(
            r'「([^」]+)」[^\s（(]*\s*[（(](https?://[^\s）)]+)[）)]',
            r'[\1](\2)',
            line
        )

        # Pattern 2: phrase before （URL） or (URL)
        def replace_phrase_url(m):
            before_text = m.group(1)
            url = m.group(2)

            # Already a markdown link
            if before_text.rstrip().endswith(']') or '](http' in before_text[-50:]:
                return m.group(0)

            # Extract label: work backwards from the URL paren
            # Split at natural boundaries: ，、。；：！？,;:!? and sentence-level phrases
            # Then take the last meaningful segment as label
            stripped = before_text.rstrip()

            # Find the last natural break point
            break_pattern = re.compile(r'[，、。；：！？,;:!?\n]|(?:可以參考|前往|請至|請到|登入後|登录后|Visit\s+the|Go\s+to\s+the|go\s+to\s+the|Check\s+out\s+the|See\s+the|check\s+out)')
            breaks = list(break_pattern.finditer(stripped))

            if breaks:
                last_break = breaks[-1]
                label_start = last_break.end()
                prefix = before_text[:last_break.end()]
                label = stripped[label_start:].strip()
            else:
                # No break found — use the whole text but limit
                label = stripped.strip()
                prefix = ''

            # Clean up label
            # Strip leading Chinese particles
            label = re.sub(r'^[\s的與和或在到為是了與]+', '', label)
            # Strip leading English articles/prepositions
            label = re.sub(r'^(?:the|a|an|to|of|in|on|at|our|your|my|their)\s+', '', label, flags=re.IGNORECASE)

            if label and len(label) >= 2:
                # Ensure space before [ if prefix ends with a letter/CJK
                if prefix and not prefix.endswith((' ', '\t', '\n', '「', '（', '(')):
                    return f'{prefix} [{label}]({url})'
                return f'{prefix}[{label}]({url})'

            return m.group(0)

        # Match: anything + （URL） or (URL)
        line = re.sub(
            r'(.+?)\s*[（(](https?://[^\s）)]+)[）)]',
            replace_phrase_url,
            line
        )

        # Pattern 3: Standalone URLs not already in markdown link
        def replace_standalone(m):
            before = m.group(1)
            url = m.group(2)
            # Skip if already inside markdown link syntax
            if before.endswith('](') or before.endswith('['):
                return m.group(0)
            return f'{before}[{url}]({url})'

        line = re.sub(
            r'(^|.+?)(https?://[^\s）)「」\[\]]+)(?![^\[]*\])',
            replace_standalone,
            line
        )

        result_lines.append(line)

    return '\n'.join(result_lines)


def add_keyword_links(text, keyword_map):
    """
    For each keyword in the map, if it appears in the text but is NOT already
    inside a markdown link, wrap the FIRST occurrence as a link.
    """
    # Sort by length descending so longer matches take priority
    sorted_keywords = sorted(keyword_map.keys(), key=len, reverse=True)

    for keyword in sorted_keywords:
        url = keyword_map[keyword]

        # Skip if keyword is not in text
        if keyword not in text:
            continue

        # Skip if keyword is already linked (inside [...] or already has URL nearby)
        # Check if it appears as [keyword] already
        if f'[{keyword}]' in text:
            continue

        # Replace only first occurrence that is NOT inside a markdown link
        # We use a negative lookbehind for [ and negative lookahead for ]
        pattern = re.compile(re.escape(keyword))

        # Find all occurrences and only replace if not inside a link
        new_text = []
        last_end = 0
        replaced = False

        for m in pattern.finditer(text):
            start, end = m.start(), m.end()

            # Check if this occurrence is inside a markdown link [...](...)
            # by looking at surrounding context
            before = text[:start]
            after = text[end:]

            # Inside link text: [...keyword...]
            open_bracket = before.rfind('[')
            close_bracket = before.rfind(']')
            if open_bracket > close_bracket:
                # We're inside [ ... ], skip
                continue

            # Inside link URL: ](url_with_keyword)
            if before.endswith('](') or '](http' in before[max(0, start-200):start]:
                paren_open = before.rfind('](')
                paren_close = before.rfind(')')
                if paren_open > paren_close:
                    continue

            if not replaced:
                new_text.append(text[last_end:start])
                new_text.append(f'[{keyword}]({url})')
                last_end = end
                replaced = True

        if replaced:
            new_text.append(text[last_end:])
            text = ''.join(new_text)

    return text


def split_by_locale(content):
    """Split content into locale sections."""
    parts = re.split(r'(<!--locale:\S+?-->)', content)
    sections = []
    current_locale = 'zh-tw'

    for part in parts:
        locale_match = re.match(r'<!--locale:(\S+?)-->', part)
        if locale_match:
            current_locale = locale_match.group(1)
            sections.append(('marker', part, current_locale))
        else:
            sections.append(('content', part, current_locale))

    return sections


def process_file(filepath, dry_run=False):
    """Process a single markdown file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()

    # Split frontmatter and content
    parts = raw.split('---', 2)
    if len(parts) < 3:
        return False

    frontmatter = parts[1]
    content = parts[2]
    original_content = content

    # Split by locale sections
    sections = split_by_locale(content)

    new_content_parts = []
    for section_type, text, locale in sections:
        if section_type == 'marker':
            new_content_parts.append(text)
            continue

        # Step 1: Convert inline URLs to markdown links
        processed = convert_inline_urls(text)

        # Step 2: Add keyword links based on locale
        if locale == 'zh-tw':
            processed = add_keyword_links(processed, KEYWORD_MAP_ZHTW)
        elif locale == 'zh-cn':
            processed = add_keyword_links(processed, KEYWORD_MAP_ZHCN)
        elif locale == 'en':
            processed = add_keyword_links(processed, KEYWORD_MAP_EN)

        new_content_parts.append(processed)

    new_content = ''.join(new_content_parts)

    if new_content != original_content:
        if dry_run:
            print(f"  [WOULD CHANGE] {filepath.name}")
        else:
            result = f'---{frontmatter}---{new_content}'
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"  [UPDATED] {filepath.name}")
        return True
    else:
        return False


def main():
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print("=== DRY RUN MODE (no files will be changed) ===\n")

    md_files = sorted(CONTENT_DIR.rglob('*.md'))
    print(f"Found {len(md_files)} FAQ files.\n")

    changed = 0
    for f in md_files:
        if process_file(f, dry_run):
            changed += 1

    print(f"\n{'Would change' if dry_run else 'Changed'}: {changed} / {len(md_files)} files")
    if dry_run:
        print("\nRun without --dry-run to apply changes.")


if __name__ == '__main__':
    main()
