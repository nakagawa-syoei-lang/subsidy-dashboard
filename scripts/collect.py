#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import json, re, time, warnings, logging
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36", "Accept-Language": "ja,en-US;q=0.9"}
SUBSIDY_KEYWORDS = ["補助金","助成金","支援金","給付金","交付金","補助事業","助成事業","支援事業","支援制度","物価","光熱費","エネルギー高騰","賃上げ","雇用調整","IT導入","DX補助","創業支援","設備投資支援","省エネ補助","販路開拓支援","輸出支援"]
EXCLUDE_KEYWORDS = ["奨学金","育英","後期高齢者","入札公告","競争入札"]
HISTORY_FILE = Path("docs/data.json")

def fetch(url, timeout=12):
    try:
        res = requests.get(url, headers=HEADERS, timeout=timeout)
        res.raise_for_status()
        ct = res.headers.get("Content-Type","")
        if "xml" in ct or url.endswith((".xml",".rdf",".rss")):
            return BeautifulSoup(res.content, "lxml-xml")
        res.encoding = res.apparent_encoding or "utf-8"
        return BeautifulSoup(res.text, "lxml")
    except Exception as e:
        logger.debug(f"取得失敗: {url} → {e}")
        return None

def is_subsidy(text):
    if any(kw in text for kw in EXCLUDE_KEYWORDS): return False
    return any(kw in text for kw in SUBSIDY_KEYWORDS)

def extract_detail(url):
    detail = {}
    soup = fetch(url, timeout=8)
    if not soup: return detail
    text = soup.get_text(separator="\n")
    for pat in [r"補助(率|額|上限)[^\n]{0,5}[：:]\s*([^\n]{3,50})", r"([\d,]+万円(?:以内|まで|を上限)?)", r"(補助率[\d/]+(?:以内)?)"]:
        m = re.search(pat, text)
        if m: detail["amount"] = m.group(0).strip()[:60]; break
    for pat in [r"(締切日?[^\n]{0,5}[：:]\s*(?:令和|平成)?\d+年\d{1,2}月\d{1,2}日)", r"(申請期限[^\n]{0,5}[：:]\s*[^\n]{5,50})", r"(募集期間[^\n]{0,5}[：:][^\n]{5,60})", r"((?:令和|平成)\d+年\d{1,2}月\d{1,2}日[^\n]{0,15}(?:締切|まで|期限))"]:
        m = re.search(pat, text)
        if m: detail["deadline"] = m.group(0).strip()[:60]; break
    for pat in [r"(対象[者事業施設][^\n]{0,5}[：:]\s*[^\n]{5,80})"]:
        m = re.search(pat, text)
        if m: detail["target"] = m.group(0).strip()[:80]; break
    return detail

def classify(title):
    mapping = {"IT・デジタル":["IT","DX","デジタル","AI","クラウド","ICT"],"雇用・人材":["雇用","人材","採用","訓練","両立","賃上げ","賃金"],"設備・機械":["設備","機械","装置","工場","製造"],"創業・起業":["創業","起業","スタートアップ","開業"],"販路拡大":["販路","輸出","海外","EC","展示会"],"省エネ・環境":["省エネ","環境","脱炭素","再生可能","GX"],"研究開発":["研究","開発","技術","イノベーション"],"融資・貸付":["融資","貸付","ローン","資金調達"],"事業再構築":["再構築","転換","新事業","多角化"],"物価・光熱費対策":["物価","光熱費","エネルギー","電気代","燃料"],"医療・福祉":["医療","診療","病院","薬局","介護","福祉"],"農業・水産":["農業","水産","漁業","林業"],"観光・飲食":["観光","飲食","宿泊","ホテル"],"防災・安全":["防災","耐震","BCP"]}
    for cat, kws in mapping.items():
        if any(kw in title for kw in kws): return cat
    return "補助金・助成金（一般）"

def collect_rss(name, pref, url):
    results = []
    soup = fetch(url)
    if not soup: return results
    items = soup.find_all("item") or soup.find_all("entry")
    for item in items[:60]:
        try:
            t = item.find("title")
            if not t: continue
            title = t.get_text(strip=True)
            if not is_subsidy(title): continue
            link_tag = item.find("link")
            link = (link_tag.get("href") or link_tag.get_text(strip=True)) if link_tag else url
            detail = {}
            if link and link.startswith("http") and link != url:
                detail = extract_detail(link)
                time.sleep(0.3)
            results.append(make_row(title, name, pref, link, detail))
        except Exception: pass
    return results

def collect_html(name, pref, base_url, pattern=None):
    results = []
    soup = fetch(base_url)
    if not soup: return results
    base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(base_url))
    if pattern:
        links = soup.find_all("a", href=re.compile(pattern))[:40]
    else:
        content = soup.find("article") or soup.find("main") or soup
        for h in content.find_all(["h2","h3"])[:30]:
            title = h.get_text(strip=True)
            if len(title) >= 6 and is_subsidy(title):
                results.append(make_row(title, name, pref, base_url, {}))
        return results
    seen = set()
    for a in links:
        title = a.get_text(strip=True)
        if not title or len(title) < 6 or not is_subsidy(title): continue
        href = a.get("href","")
        url = href if href.startswith("http") else urljoin(base, href)
        if url in seen: continue
        seen.add(url)
        detail = extract_detail(url)
        time.sleep(0.3)
        results.append(make_row(title, name, pref, url, detail))
    return results

def make_row(title, org, pref, url, detail):
    return {"id": re.sub(r"\W","",title[:20])+str(abs(hash(url))%10000), "title":title[:120], "org":org, "pref":pref, "amount":detail.get("amount",""), "deadline":detail.get("deadline",""), "target":detail.get("target",""), "category":classify(title), "url":url, "source":"自治体" if pref not in ("全国",) else "国・省庁", "date":str(date.today())}

RSS_SOURCES = [("経済産業省","全国","https://www.meti.go.jp/feed/topics.rdf"),("厚生労働省","全国","https://www.mhlw.go.jp/rss/topics.rdf"),("中小企業庁","全国","https://www.chusho.meti.go.jp/rss/news.rdf"),("総務省","全国","https://www.soumu.go.jp/menu_kyotsuu/whatsnew/rss.xml"),("神奈川県","神奈川県","https://www.pref.kanagawa.jp/prs/list.xml"),("大阪府","大阪府","https://www.pref.osaka.lg.jp/rss/hodo/index.rdf"),("愛知県","愛知県","https://www.pref.aichi.jp/rss/news/index.rdf"),("福岡県","福岡県","https://www.pref.fukuoka.lg.jp/rss/news.rdf"),("埼玉県","埼玉県","https://www.pref.saitama.lg.jp/rss/atom/newsrelease.xml"),("千葉県","千葉県","https://www.pref.chiba.lg.jp/rss/news.xml"),("兵庫県","兵庫県","https://web.pref.hyogo.lg.jp/rss/news.rdf"),("広島県","広島県","https://www.pref.hiroshima.lg.jp/rss/news.rdf"),("北海道","北海道","https://www.pref.hokkaido.lg.jp/rss/news.rdf"),("静岡県","静岡県","https://www.pref.shizuoka.jp/rss/atom/top.xml"),("京都府","京都府","https://www.pref.kyoto.jp/rss/index.rdf"),("宮城県","宮城県","https://www.pref.miyagi.jp/rss/news.rdf")]
HTML_SOURCES = [("東京都産業労働局","東京都","https://www.sangyo-rodo.metro.tokyo.lg.jp/news/",r"/news/"),("東京中小企業振興公社","東京都","https://www.tokyo-kosha.or.jp/support/josei/index.html",r"/support/josei/"),("ミラサポplus","全国","https://mirasapo-plus.go.jp/subsidy/",r"/subsidy/\d+"),("J-Net21","全国","https://j-net21.smrj.go.jp/snavi/articles?category=C0302",r"/snavi/articles/\d+"),("補助金ポータル","全国","https://hojyokin-portal.jp/columns/sme_subsidy",None)]

def main():
    all_data = []
    for name, pref, url in RSS_SOURCES:
        logger.info(f"RSS: {name}")
        try:
            rows = collect_rss(name, pref, url)
            all_data.extend(rows)
            logger.info(f"  → {len(rows)}件")
        except Exception as e:
            logger.warning(f"  → エラー: {e}")
        time.sleep(0.8)
    for name, pref, url, pattern in HTML_SOURCES:
        logger.info(f"HTML: {name}")
        try:
            rows = collect_html(name, pref, url, pattern)
            all_data.extend(rows)
            logger.info(f"  → {len(rows)}件")
        except Exception as e:
            logger.warning(f"  → エラー: {e}")
        time.sleep(0.8)
    seen_titles = set()
    unique = []
    for row in all_data:
        key = re.sub(r"\s+","",row["title"])[:30]
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(row)
    logger.info(f"収集完了: {len(unique)}件")
    existing = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            try: existing = json.load(f).get("items",[])
            except Exception: existing = []
    today_str = str(date.today())
    old_data = [r for r in existing if r.get("date") != today_str]
    combined = unique + old_data
    cutoff = str(date.today() - timedelta(days=90))
    combined = [r for r in combined if r.get("date","") >= cutoff]
    Path("docs").mkdir(exist_ok=True)
    output = {"updated": datetime.now().strftime("%Y年%m月%d日 %H:%M"), "count": len(unique), "total": len(combined), "items": combined}
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    with open("docs/last_updated.txt","w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(f"保存完了: {len(combined)}件")

if __name__ == "__main__":
    main()
