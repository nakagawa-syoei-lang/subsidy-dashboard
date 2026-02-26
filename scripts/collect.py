#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import xml.etree.ElementTree as ET
import json, time, logging, re
from datetime import date, datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HISTORY_FILE = Path("docs/data.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SubsidyBot/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}
KANTO_PREFS = ["東京都", "神奈川県", "埼玉県", "千葉県"]

RSS_SOURCES = [
    # ミラサポplus RSS（補助金・助成金）
    ("https://mirasapo-plus.go.jp/rss_feed/subsidy/", "中小企業庁"),
    ("https://mirasapo-plus.go.jp/rss_feed/", "中小企業庁"),
    # 経済産業省
    ("https://www.meti.go.jp/rss/press.rdf", "経済産業省"),
    # 中小企業庁
    ("https://www.chusho.meti.go.jp/rss/index.rdf", "中小企業庁"),
    # 厚生労働省
    ("https://www.mhlw.go.jp/rss/shinsei/shinsei_14.rdf", "厚生労働省"),
    # 東京都
    ("https://www.metro.tokyo.lg.jp/rss/metro_news.rss", "東京都"),
    ("https://www.sangyo-rodo.metro.tokyo.lg.jp/rss/news.xml", "東京都産業労働局"),
    # 神奈川県
    ("https://www.pref.kanagawa.jp/rss/rss_news_13.rss", "神奈川県"),
    # 埼玉県
    ("https://www.pref.saitama.lg.jp/rss/news.rdf", "埼玉県"),
    # 千葉県
    ("https://www.pref.chiba.lg.jp/rss/news.rdf", "千葉県"),
]

SUBSIDY_KEYWORDS = [
    "補助金","助成金","支援金","給付金","補助","助成","支援事業","公募",
    "IT導入","DX","ものづくり","持続化","事業再構築","雇用","省エネ",
]

def is_subsidy(title, desc=""):
    text = title + " " + (desc or "")
    return any(kw in text for kw in SUBSIDY_KEYWORDS)

def get_pref(text, org=""):
    combined = text + " " + org
    for kanto in KANTO_PREFS:
        if kanto in combined:
            return kanto
    for pref in ["北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県",
                 "茨城県","栃木県","群馬県","新潟県","富山県","石川県","福井県",
                 "山梨県","長野県","岐阜県","静岡県","愛知県","三重県","滋賀県",
                 "京都府","大阪府","兵庫県","奈良県","和歌山県","鳥取県","島根県",
                 "岡山県","広島県","山口県","徳島県","香川県","愛媛県","高知県",
                 "福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"]:
        if pref in combined:
            return pref
    return "全国"

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
        "物価・光熱費対策": ["物価","光熱費","エネルギー","電気代","燃料","高騰"],
        "医療・福祉":       ["医療","診療","病院","薬局","介護","福祉"],
        "農業・水産":       ["農業","水産","漁業","林業"],
        "観光・飲食":       ["観光","飲食","宿泊","ホテル"],
        "防災・安全":       ["防災","耐震","BCP"],
    }
    for cat, kws in mapping.items():
        if any(kw in title for kw in kws):
            return cat
    return "補助金・助成金（一般）"

def fetch_rss(url, org):
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        logger.info(f"  {org} ({url[-40:]}): {res.status_code}")
        if res.status_code != 200:
            return []
        # XML解析
        root = ET.fromstring(res.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = []
        # RSS 2.0
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            if not title or not link:
                continue
            if not is_subsidy(title, desc):
                continue
            pref = get_pref(title + desc, org)
            items.append({
                "id": abs(hash(link)) % 10**12,
                "title": title[:120],
                "org": org[:40],
                "pref": pref,
                "amount": "",
                "deadline": "",
                "target": "",
                "category": classify(title),
                "url": link,
                "source": "自治体" if pref != "全国" else "国・省庁",
                "date": str(date.today()),
            })
        # Atom
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            title = (title_el.text if title_el is not None else "").strip()
            link = (link_el.get("href","") if link_el is not None else "").strip()
            if not title or not link:
                continue
            if not is_subsidy(title):
                continue
            pref = get_pref(title, org)
            items.append({
                "id": abs(hash(link)) % 10**12,
                "title": title[:120],
                "org": org[:40],
                "pref": pref,
                "amount": "",
                "deadline": "",
                "target": "",
                "category": classify(title),
                "url": link,
                "source": "自治体" if pref != "全国" else "国・省庁",
                "date": str(date.today()),
            })
        logger.info(f"    → {len(items)}件の補助金情報")
        return items
    except Exception as e:
        logger.warning(f"  エラー ({org}): {e}")
        return []

def main():
    all_items = []
    seen_ids = set()

    for url, org in RSS_SOURCES:
        items = fetch_rss(url, org)
        for item in items:
            sid = str(item["id"])
            if sid not in seen_ids:
                seen_ids.add(sid)
                all_items.append(item)
        time.sleep(1)

    # 1都3県を先頭に
    kanto = [x for x in all_items if x["pref"] in KANTO_PREFS]
    others = [x for x in all_items if x["pref"] not in KANTO_PREFS]
    all_items = kanto + others
    logger.info(f"収集完了: {len(all_items)}件（1都3県: {len(kanto)}件）")

    existing = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            try: existing = json.load(f).get("items", [])
            except: existing = []

    today_str = str(date.today())
    old_data = [r for r in existing if r.get("date") != today_str]
    combined = all_items + old_data
    cutoff = str(date.today() - timedelta(days=90))
    combined = [r for r in combined if r.get("date","") >= cutoff]

    Path("docs").mkdir(exist_ok=True)
    output = {
        "updated": datetime.now().strftime("%Y年%m月%d日 %H:%M"),
        "count": len(all_items),
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
