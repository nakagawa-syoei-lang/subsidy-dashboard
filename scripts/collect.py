#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import json, time, logging, re, hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HISTORY_FILE = Path("docs/data.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
KANTO_PREFS = ["東京都", "神奈川県", "埼玉県", "千葉県"]

ALL_PREFS = [
    "北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県",
    "茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県",
    "新潟県","富山県","石川県","福井県","山梨県","長野県","岐阜県",
    "静岡県","愛知県","三重県","滋賀県","京都府","大阪府","兵庫県",
    "奈良県","和歌山県","鳥取県","島根県","岡山県","広島県","山口県",
    "徳島県","香川県","愛媛県","高知県","福岡県","佐賀県","長崎県",
    "熊本県","大分県","宮崎県","鹿児島県","沖縄県",
]

SUBSIDY_KEYWORDS = [
    "補助金","助成金","支援金","給付金","補助","助成","支援事業","公募",
    "IT導入","DX","ものづくり","持続化","事業再構築","雇用","省エネ",
    "融資","貸付","資金","創業","起業","販路","設備","物価","高騰",
    "物価高騰","支援について","給付","奨励金","交付金","補填",
    "医療機関","介護","薬局","病院","診療所",
]

# 公募開始日・掲載日を探すキーワード
START_DATE_KEYWORDS = [
    "公募開始", "受付開始", "掲載日", "掲載開始", "公開日", "開始日",
    "募集開始", "申請受付開始", "受付期間", "申請期間", "公募期間",
    "募集期間", "掲載年月日", "更新日", "作成日",
]

EXPIRY_DAYS = 547  # 1年半 = 365 + 182

def make_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:16]

def is_subsidy(title):
    return any(kw in title for kw in SUBSIDY_KEYWORDS)

def classify(title):
    mapping = {
        "IT・デジタル":     ["IT","DX","デジタル","AI","クラウド","ICT","システム","電子"],
        "雇用・人材":       ["雇用","人材","採用","訓練","賃上げ","賃金","労働","働き方"],
        "設備・機械":       ["設備","機械","装置","工場","製造","ものづくり"],
        "創業・起業":       ["創業","起業","スタートアップ","開業"],
        "販路拡大":         ["販路","輸出","海外","EC","展示会"],
        "省エネ・環境":     ["省エネ","環境","脱炭素","再生可能","GX","太陽光"],
        "研究開発":         ["研究","開発","技術","イノベーション"],
        "融資・貸付":       ["融資","貸付","ローン","資金"],
        "事業再構築":       ["再構築","転換","新事業","多角化"],
        "物価・光熱費対策": ["物価","光熱費","エネルギー","電気代","燃料","高騰","物価高騰"],
        "医療・福祉":       ["医療","診療","病院","薬局","介護","福祉","医療機関"],
        "農業・水産":       ["農業","水産","漁業","林業"],
        "観光・飲食":       ["観光","飲食","宿泊","ホテル"],
        "防災・安全":       ["防災","耐震","BCP"],
    }
    for cat, kws in mapping.items():
        if any(kw in title for kw in kws):
            return cat
    return "補助金・助成金（一般）"

def parse_japanese_date(text):
    """テキストから日付を解析してdateオブジェクトを返す"""
    if not text:
        return None

    # 令和X年Y月Z日
    m = re.search(r'令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日', text)
    if m:
        try:
            year = 2018 + int(m.group(1))
            month = int(m.group(2))
            day = int(m.group(3))
            if 2019 <= year <= 2035 and 1 <= month <= 12 and 1 <= day <= 31:
                return date(year, month, day)
        except:
            pass

    # YYYY年MM月DD日
    m = re.search(r'(\d{4})\s*年\s*(\d+)\s*月\s*(\d+)\s*日', text)
    if m:
        try:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2019 <= year <= 2035 and 1 <= month <= 12 and 1 <= day <= 31:
                return date(year, month, day)
        except:
            pass

    # YYYY-MM-DD
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        try:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2019 <= year <= 2035 and 1 <= month <= 12 and 1 <= day <= 31:
                return date(year, month, day)
        except:
            pass

    # YYYY/MM/DD
    m = re.search(r'(\d{4})/(\d{2})/(\d{2})', text)
    if m:
        try:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2019 <= year <= 2035 and 1 <= month <= 12 and 1 <= day <= 31:
                return date(year, month, day)
        except:
            pass

    return None

def extract_deadline(text):
    """テキストから申請期限を抽出"""
    if not text:
        return ""

    deadline_patterns = [
        r'(?:締[切め]|期限|受付終了|申請期間|公募期間|募集期間|応募期限|提出期限).*?'
        r'令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日',
        r'(?:締[切め]|期限|受付終了|申請期間|公募期間|募集期間|応募期限|提出期限).*?'
        r'(\d{4})\s*年\s*(\d+)\s*月\s*(\d+)\s*日',
        r'令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日',
        r'(\d{4})\s*年\s*(\d+)\s*月\s*(\d+)\s*日',
        r'(\d{4})-(\d{2})-(\d{2})',
    ]

    for pattern in deadline_patterns:
        matches = re.findall(pattern, text)
        if matches:
            for m in matches:
                try:
                    if len(m[0]) <= 2:  # 令和
                        year = 2018 + int(m[0])
                    else:
                        year = int(m[0])
                    month = int(m[1])
                    day = int(m[2])
                    if 2020 <= year <= 2035 and 1 <= month <= 12 and 1 <= day <= 31:
                        return f"令和{year-2018}年{month}月{day}日締切"
                except:
                    continue
    return ""

def extract_start_date_from_text(text):
    """テキストから公募開始日・掲載日などを抽出してdateオブジェクトを返す"""
    if not text:
        return None

    for kw in START_DATE_KEYWORDS:
        # キーワードの近くにある日付を探す
        pattern = re.escape(kw) + r'.{0,30}'
        m = re.search(pattern, text)
        if m:
            snippet = m.group(0) + text[m.end():m.end()+30]
            d = parse_japanese_date(snippet)
            if d:
                return d

    return None

def fetch_page_info(url):
    """個別ページから申請期限・公募開始日を取得"""
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return "", None
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "lxml")

        main = soup.find("main") or soup.find(id="content") or soup.find(class_="content") or soup

        # 申請期限を取得
        deadline = ""
        deadline_keywords = ["締切","期限","受付終了","申請期間","公募期間","募集期間","受付期間"]
        for kw in deadline_keywords:
            for tag in main.find_all(string=re.compile(kw)):
                parent = tag.parent
                text = parent.get_text(" ", strip=True)
                deadline = extract_deadline(text)
                if deadline:
                    break
            if deadline:
                break

        # 公募開始日を取得
        start_date = None
        full_text = main.get_text(" ", strip=True)

        # まずキーワード近辺から探す
        start_date = extract_start_date_from_text(full_text)

        # 見つからなければページ全体の最初の日付（最も古い日付）を使う
        if not start_date:
            all_dates = []
            # 令和X年
            for m in re.finditer(r'令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日', full_text):
                try:
                    d = date(2018 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    if 2019 <= d.year <= 2035:
                        all_dates.append(d)
                except:
                    pass
            # YYYY年
            for m in re.finditer(r'(\d{4})\s*年\s*(\d+)\s*月\s*(\d+)\s*日', full_text):
                try:
                    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    if 2019 <= d.year <= 2035:
                        all_dates.append(d)
                except:
                    pass
            if all_dates:
                # 最も古い日付を開始日と見なす
                start_date = min(all_dates)

        if not deadline:
            deadline = extract_deadline(full_text)

        return deadline, start_date

    except Exception as e:
        logger.debug(f"ページ取得エラー ({url[-40:]}): {e}")
        return "", None

def is_expired_by_start_date(start_date):
    """開始日から1年半以上経過していたらTrue"""
    if not start_date:
        return False
    return (date.today() - start_date).days >= EXPIRY_DAYS

def enrich_items(items, max_fetch=60):
    """期限未取得のアイテムについて個別ページから期限・開始日を取得"""
    no_deadline = [item for item in items if not item.get("deadline")]
    logger.info(f"期限未取得: {len(no_deadline)}件 → 最大{max_fetch}件を個別取得")
    fetched = 0
    for item in no_deadline:
        if fetched >= max_fetch:
            break
        if "jgrants-portal" in item.get("url", ""):
            continue
        deadline, start_date = fetch_page_info(item["url"])
        if deadline:
            item["deadline"] = deadline
        if start_date:
            item["start_date"] = str(start_date)
            # 開始日から1年半以上経過 → 期限切れフラグ
            if is_expired_by_start_date(start_date) and not item.get("deadline"):
                item["expired_by_age"] = True
        fetched += 1
        time.sleep(0.5)
    logger.info(f"個別取得完了: {fetched}件処理")
    return items

def scrape_page(url, pref, org, link_pattern=None, title_filter=True, fetch_detail=False):
    items = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        logger.info(f"  {org}: {res.status_code} ({url[-60:]})")
        if res.status_code != 200:
            return items
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "lxml")
        parsed_base = urlparse(url)
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            href = a["href"]
            if not title or len(title) < 8:
                continue
            if title_filter and not is_subsidy(title):
                continue
            if href.startswith("http"):
                full_url = href
            elif href.startswith("/"):
                full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
            else:
                continue
            if link_pattern and not re.search(link_pattern, href):
                continue

            parent_text = ""
            for p in [a.parent, a.parent.parent if a.parent else None]:
                if p:
                    parent_text = p.get_text(" ", strip=True)
                    break
            deadline = extract_deadline(parent_text)
            # リスト上の日付から開始日も推定
            start_date_obj = extract_start_date_from_text(parent_text)

            item = {
                "id": make_id(full_url),
                "title": title[:120],
                "org": org,
                "pref": pref,
                "amount": "",
                "deadline": deadline,
                "target": "",
                "category": classify(title),
                "url": full_url,
                "source": "自治体",
                "date": str(date.today()),
            }
            if start_date_obj:
                item["start_date"] = str(start_date_obj)
                if is_expired_by_start_date(start_date_obj) and not deadline:
                    item["expired_by_age"] = True

            items.append(item)
        logger.info(f"    → {len(items)}件")
    except Exception as e:
        logger.warning(f"  エラー ({org}): {e}")
    return items

def scrape_tokyo_portal():
    items = []
    seen = set()
    target_urls = [
        ("https://www.sangyo-rodo.metro.tokyo.lg.jp/chushou/shoko/jyosei/", "東京都産業労働局"),
        ("https://www.hokeniryo.metro.tokyo.lg.jp/iryo/jigyo/h_gaiyou/", "東京都保健医療局"),
    ]
    for url, org in target_urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            logger.info(f"  {org}: {res.status_code} ({url[-60:]})")
            if res.status_code != 200:
                continue
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, "lxml")
            parsed_base = urlparse(url)
            for a in soup.find_all("a", href=True):
                title = a.get_text(strip=True)
                href = a["href"]
                if not title or len(title) < 8:
                    continue
                if not is_subsidy(title):
                    continue
                if href.startswith("http"):
                    full_url = href
                elif href.startswith("/"):
                    full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                else:
                    continue
                if full_url in seen:
                    continue
                seen.add(full_url)
                parent_text = ""
                for p in [a.parent, a.parent.parent if a.parent else None]:
                    if p:
                        parent_text = p.get_text(" ", strip=True)
                        break
                deadline = extract_deadline(parent_text)
                start_date_obj = extract_start_date_from_text(parent_text)

                item = {
                    "id": make_id(full_url),
                    "title": title[:120],
                    "org": org,
                    "pref": "東京都",
                    "amount": "",
                    "deadline": deadline,
                    "target": "",
                    "category": classify(title),
                    "url": full_url,
                    "source": "自治体",
                    "date": str(date.today()),
                }
                if start_date_obj:
                    item["start_date"] = str(start_date_obj)
                    if is_expired_by_start_date(start_date_obj) and not deadline:
                        item["expired_by_age"] = True

                items.append(item)
            logger.info(f"    → {len(items)}件累計")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"  東京都ポータルエラー ({org}): {e}")
    return items

def scrape_kanagawa_tag(pages=5):
    items = []
    seen = set()
    base = "https://www.pref.kanagawa.jp/search/tag.html"
    for tag_id in ["26", "27"]:
        for page in range(1, pages + 1):
            url = f"{base}?q={tag_id}&page={page}"
            try:
                res = requests.get(url, headers=HEADERS, timeout=20)
                logger.info(f"  神奈川タグ{tag_id}(p{page}): {res.status_code}")
                if res.status_code != 200:
                    break
                res.encoding = res.apparent_encoding
                soup = BeautifulSoup(res.text, "lxml")
                found = 0
                for a in soup.find_all("a", href=True):
                    title = a.get_text(strip=True)
                    href = a["href"]
                    if not title or len(title) < 8:
                        continue
                    if not is_subsidy(title):
                        continue
                    if href.startswith("/"):
                        full_url = f"https://www.pref.kanagawa.jp{href}"
                    elif href.startswith("http"):
                        full_url = href
                    else:
                        continue
                    if full_url in seen:
                        continue
                    seen.add(full_url)
                    found += 1
                    parent_text = ""
                    for p in [a.parent, a.parent.parent if a.parent else None]:
                        if p:
                            parent_text = p.get_text(" ", strip=True)
                            break
                    deadline = extract_deadline(parent_text)
                    start_date_obj = extract_start_date_from_text(parent_text)

                    item = {
                        "id": make_id(full_url),
                        "title": title[:120],
                        "org": "神奈川県",
                        "pref": "神奈川県",
                        "amount": "",
                        "deadline": deadline,
                        "target": "",
                        "category": classify(title),
                        "url": full_url,
                        "source": "自治体",
                        "date": str(date.today()),
                    }
                    if start_date_obj:
                        item["start_date"] = str(start_date_obj)
                        if is_expired_by_start_date(start_date_obj) and not deadline:
                            item["expired_by_age"] = True

                    items.append(item)
                logger.info(f"    → 新規{found}件")
                if not soup.find("a", string=re.compile("次")):
                    break
                time.sleep(1)
            except Exception as e:
                logger.warning(f"  神奈川タグエラー: {e}")
                break
        time.sleep(2)

    health_urls = [
        ("https://www.pref.kanagawa.jp/div/1336/index.html", "神奈川県健康医療局"),
        ("https://www.pref.kanagawa.jp/menu/2/6/31/index.html", "神奈川県医療政策"),
    ]
    for url, org in health_urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            logger.info(f"  {org}: {res.status_code} ({url[-60:]})")
            if res.status_code != 200:
                continue
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, "lxml")
            found = 0
            for a in soup.find_all("a", href=True):
                title = a.get_text(strip=True)
                href = a["href"]
                if not title or len(title) < 8:
                    continue
                if not is_subsidy(title):
                    continue
                if href.startswith("/"):
                    full_url = f"https://www.pref.kanagawa.jp{href}"
                elif href.startswith("http"):
                    full_url = href
                else:
                    continue
                if full_url in seen:
                    continue
                seen.add(full_url)
                found += 1
                parent_text = ""
                for p in [a.parent, a.parent.parent if a.parent else None]:
                    if p:
                        parent_text = p.get_text(" ", strip=True)
                        break
                deadline = extract_deadline(parent_text)
                start_date_obj = extract_start_date_from_text(parent_text)

                item = {
                    "id": make_id(full_url),
                    "title": title[:120],
                    "org": org,
                    "pref": "神奈川県",
                    "amount": "",
                    "deadline": deadline,
                    "target": "",
                    "category": classify(title),
                    "url": full_url,
                    "source": "自治体",
                    "date": str(date.today()),
                }
                if start_date_obj:
                    item["start_date"] = str(start_date_obj)
                    if is_expired_by_start_date(start_date_obj) and not deadline:
                        item["expired_by_age"] = True

                items.append(item)
            logger.info(f"    → 新規{found}件")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"  神奈川健康医療局エラー ({org}): {e}")

    logger.info(f"  神奈川合計: {len(items)}件")
    return items

SCRAPE_TARGETS = [
    # 東京都
    {
        "url": "https://www.tokyo-kosha.or.jp/support/josei/index.html",
        "pref": "東京都", "org": "東京都中小企業振興公社",
    },
    {
        "url": "https://www.sangyo-rodo.metro.tokyo.lg.jp/support/chusho/",
        "pref": "東京都", "org": "東京都産業労働局",
    },
    # 神奈川県
    {
        "url": "https://www.pref.kanagawa.jp/docs/jf2/index.html",
        "pref": "神奈川県", "org": "神奈川県中小企業支援課",
    },
    {
        "url": "https://www.pref.kanagawa.jp/menu/5/20/116/index.html",
        "pref": "神奈川県", "org": "神奈川県",
        "title_filter": False,
    },
    # 埼玉県
    {
        "url": "https://www.pref.saitama.lg.jp/a0801/kigyoushien_portal.html",
        "pref": "埼玉県", "org": "埼玉県",
    },
    {
        "url": "https://www.pref.saitama.lg.jp/shigoto/sangyo/kigyo/kigyoshien/index.html",
        "pref": "埼玉県", "org": "埼玉県産業労働部",
    },
    # 千葉県
    {
        "url": "https://www.pref.chiba.lg.jp/keishi/index.html",
        "pref": "千葉県", "org": "千葉県商工労働部",
    },
]

def main():
    all_new_items = []
    seen_ids = set()

    logger.info("=== 1都3県 公式サイトスクレイピング ===")
    for target in SCRAPE_TARGETS:
        title_filter = target.get("title_filter", True)
        items = scrape_page(
            target["url"], target["pref"], target["org"],
            target.get("link_pattern"), title_filter
        )
        for item in items:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                all_new_items.append(item)
        time.sleep(2)

    logger.info("=== 東京都ポータル ===")
    for item in scrape_tokyo_portal():
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            all_new_items.append(item)

    logger.info("=== 神奈川県（タグ検索＋健康医療局）===")
    for item in scrape_kanagawa_tag(pages=5):
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            all_new_items.append(item)

    # 期限未取得の自治体アイテムを個別ページから補完（開始日も取得）
    logger.info("=== 期限・開始日情報を個別ページから補完 ===")
    local_new = [i for i in all_new_items if i.get("source") == "自治体"]
    enrich_items(local_new, max_fetch=60)

    logger.info(f"新規スクレイピング合計: {len(all_new_items)}件")

    existing = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            try: existing = json.load(f).get("items", [])
            except: existing = []

    for item in existing:
        if item.get("pref") == "全国":
            title = item.get("title","") + item.get("org","")
            for kanto in KANTO_PREFS:
                if kanto in title:
                    item["pref"] = kanto
                    item["source"] = "自治体"
                    break
            else:
                for pref in ALL_PREFS:
                    if pref in title:
                        item["pref"] = pref
                        item["source"] = "自治体"
                        break

    existing_ids = {item["id"] for item in existing}
    for item in all_new_items:
        if item["id"] not in existing_ids:
            existing.insert(0, item)
            existing_ids.add(item["id"])
        else:
            # 既存アイテムの期限・開始日を更新（新たに取得できた場合）
            for ex in existing:
                if ex["id"] == item["id"]:
                    if item.get("deadline") and not ex.get("deadline"):
                        ex["deadline"] = item["deadline"]
                    if item.get("start_date") and not ex.get("start_date"):
                        ex["start_date"] = item["start_date"]
                    if item.get("expired_by_age"):
                        ex["expired_by_age"] = True
                    break

    # 既存アイテムのうち start_date があるものに expired_by_age を付与
    for item in existing:
        if item.get("start_date") and not item.get("deadline") and not item.get("expired_by_age"):
            try:
                sd = date.fromisoformat(item["start_date"])
                if is_expired_by_start_date(sd):
                    item["expired_by_age"] = True
            except:
                pass

    cutoff = str(date.today() - timedelta(days=90))
    combined = [r for r in existing if r.get("date","") >= cutoff]

    kanto = [x for x in combined if x.get("pref") in KANTO_PREFS]
    others = [x for x in combined if x.get("pref") not in KANTO_PREFS]
    combined = kanto + others

    logger.info(f"1都3県: {len(kanto)}件 / 全{len(combined)}件")

    Path("docs").mkdir(exist_ok=True)
    output = {
        "updated": datetime.now().strftime("%Y年%m月%d日 %H:%M"),
        "count": len(all_new_items),
        "total": len(combined),
        "items": combined,
    }
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    with open("docs/last_updated.txt", "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(f"保存完了: {len(combined)}件")

if __name__ == "__main__":
    main()
