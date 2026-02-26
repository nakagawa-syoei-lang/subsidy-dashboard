#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import json, re, time, logging
from datetime import date, datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HISTORY_FILE = Path("docs/data.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9",
}
KANTO_PREFS = ["東京都", "神奈川県", "埼玉県", "千葉県"]

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

def get_pref(text):
    for kanto in KANTO_PREFS:
        if kanto in text:
            return kanto
    for pref in ["北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県",
                 "茨城県","栃木県","群馬県","新潟県","富山県","石川県","福井県",
                 "山梨県","長野県","岐阜県","静岡県","愛知県","三重県","滋賀県",
                 "京都府","大阪府","兵庫県","奈良県","和歌山県","鳥取県","島根県",
                 "岡山県","広島県","山口県","徳島県","香川県","愛媛県","高知県",
                 "福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"]:
        if pref in text:
            return pref
    return "全国"

def scrape_jgrants():
    """Jグランツのウェブサイトから補助金情報をスクレイピング"""
    items = []
    seen_ids = set()
    
    # ページ番号を変えながら取得
    for page in range(1, 15):  # 最大14ページ
        url = f"https://www.jgrants-portal.go.jp/subsidy/list?page={page}&sort=created_date&order=DESC"
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            logger.info(f"Page {page}: {res.status_code}")
            if res.status_code != 200:
                break
            soup = BeautifulSoup(res.text, "lxml")
            
            # 補助金カードを探す
            cards = soup.find_all("div", class_=re.compile(r"subsidy|card|item|list", re.I))
            if not cards:
                # リンクから探す
                links = soup.find_all("a", href=re.compile(r"/subsidy/\w+"))
                if not links:
                    logger.info(f"  Page {page}: 補助金情報なし、終了")
                    break
                    
                for a in links:
                    href = a.get("href", "")
                    sid = href.split("/")[-1] if href else ""
                    if not sid or sid in seen_ids or sid == "list":
                        continue
                    seen_ids.add(sid)
                    title = a.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    full_url = f"https://www.jgrants-portal.go.jp{href}" if href.startswith("/") else href
                    pref = get_pref(title)
                    items.append({
                        "id": sid,
                        "title": title[:120],
                        "org": "国・自治体",
                        "pref": pref,
                        "amount": "",
                        "deadline": "",
                        "target": "",
                        "category": classify(title),
                        "url": full_url,
                        "source": "自治体" if pref != "全国" else "国・省庁",
                        "date": str(date.today()),
                    })
            
            logger.info(f"  Page {page}: 累計{len(items)}件")
            time.sleep(1.5)
            
        except Exception as e:
            logger.warning(f"  Page {page} エラー: {e}")
            break
    
    return items

def scrape_mirasapo():
    """ミラサポplusから補助金情報を取得"""
    items = []
    seen_ids = set()
    
    for page in range(1, 10):
        url = f"https://mirasapo-plus.go.jp/subsidy/?page={page}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            logger.info(f"ミラサポ Page {page}: {res.status_code}")
            if res.status_code != 200:
                break
            soup = BeautifulSoup(res.text, "lxml")
            links = soup.find_all("a", href=re.compile(r"/subsidy/\d+"))
            if not links:
                break
            for a in links:
                href = a.get("href", "")
                sid = href.split("/")[-1]
                if not sid or sid in seen_ids:
                    continue
                seen_ids.add(sid)
                title = a.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                full_url = f"https://mirasapo-plus.go.jp{href}" if href.startswith("/") else href
                pref = get_pref(title)
                items.append({
                    "id": f"m{sid}",
                    "title": title[:120],
                    "org": "中小企業庁",
                    "pref": pref,
                    "amount": "",
                    "deadline": "",
                    "target": "",
                    "category": classify(title),
                    "url": full_url,
                    "source": "自治体" if pref != "全国" else "国・省庁",
                    "date": str(date.today()),
                })
            logger.info(f"  ミラサポ Page {page}: 累計{len(items)}件")
            time.sleep(1.5)
        except Exception as e:
            logger.warning(f"  ミラサポ Page {page} エラー: {e}")
            break
    
    return items

def scrape_hojyokin_portal():
    """補助金ポータルから取得"""
    items = []
    try:
        url = "https://hojyokin-portal.jp/search?category=1"
        res = requests.get(url, headers=HEADERS, timeout=20)
        logger.info(f"補助金ポータル: {res.status_code}")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "lxml")
            links = soup.find_all("a", href=re.compile(r"/subsidy/\d+|/columns/"))
            seen = set()
            for a in links:
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if not title or len(title) < 5 or href in seen:
                    continue
                seen.add(href)
                full_url = f"https://hojyokin-portal.jp{href}" if href.startswith("/") else href
                pref = get_pref(title)
                items.append({
                    "id": f"hp{abs(hash(href)) % 100000}",
                    "title": title[:120],
                    "org": "補助金ポータル",
                    "pref": pref,
                    "amount": "",
                    "deadline": "",
                    "target": "",
                    "category": classify(title),
                    "url": full_url,
                    "source": "自治体" if pref != "全国" else "国・省庁",
                    "date": str(date.today()),
                })
        logger.info(f"補助金ポータル: {len(items)}件")
    except Exception as e:
        logger.warning(f"補助金ポータルエラー: {e}")
    return items

def main():
    all_items = []
    seen_ids = set()

    logger.info("=== Jグランツ ウェブスクレイピング ===")
    jgrants = scrape_jgrants()
    for item in jgrants:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            all_items.append(item)
    logger.info(f"Jグランツ: {len(jgrants)}件")

    logger.info("=== ミラサポplus ===")
    mirasapo = scrape_mirasapo()
    for item in mirasapo:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            all_items.append(item)
    logger.info(f"ミラサポ: {len(mirasapo)}件")

    logger.info("=== 補助金ポータル ===")
    portal = scrape_hojyokin_portal()
    for item in portal:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            all_items.append(item)
    logger.info(f"補助金ポータル: {len(portal)}件")

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
