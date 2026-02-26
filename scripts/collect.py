#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import json
import time
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HISTORY_FILE = Path("docs/data.json")
BASE_URL = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies"
HEADERS = {"Accept": "application/json"}

KANTO_PREFS = ["東京都", "神奈川県", "埼玉県", "千葉県"]

KEYWORDS = [
    "補助金", "助成金", "支援金",
    "IT導入", "DX", "ものづくり", "創業", "雇用",
    "省エネ", "事業再構築", "販路", "設備",
    "東京", "神奈川", "埼玉", "千葉",
]

def fetch_subsidies(keyword, limit=100, offset=0):
    params = {
        "keyword": keyword,
        "sort": "id",
        "order": "DESC",
        "limit": limit,
        "offset": offset,
    }
    try:
        res = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        logger.info(f"  URL: {res.url}")
        logger.info(f"  Status: {res.status_code}")
        if res.status_code != 200:
            logger.warning(f"  Response: {res.text[:200]}")
            return None
        return res.json()
    except Exception as e:
        logger.warning(f"API取得失敗 (keyword={keyword}): {e}")
        return None

def get_pref(target_area):
    if not target_area:
        return "全国"
    parts = [p.strip() for p in str(target_area).replace("　", " ").split("/")]
    for p in parts:
        p = p.strip()
        for kanto in KANTO_PREFS:
            if kanto in p:
                return kanto
        for suffix in ["都", "道", "府", "県"]:
            if p.endswith(suffix) and len(p) >= 3:
                return p
    return "全国"

def classify(title, use_purpose=""):
    text = title + " " + (use_purpose or "")
    mapping = {
        "IT・デジタル":     ["IT","DX","デジタル","AI","クラウド","ICT","システム","電子"],
        "雇用・人材":       ["雇用","人材","採用","訓練","賃上げ","賃金","労働","働き方","両立"],
        "設備・機械":       ["設備","機械","装置","工場","製造","ものづくり"],
        "創業・起業":       ["創業","起業","スタートアップ","開業","新規"],
        "販路拡大":         ["販路","輸出","海外","EC","展示会","マーケティング"],
        "省エネ・環境":     ["省エネ","環境","脱炭素","再生可能","GX","太陽光","蓄電"],
        "研究開発":         ["研究","開発","技術","イノベーション"],
        "融資・貸付":       ["融資","貸付","ローン","資金","金融"],
        "事業再構築":       ["再構築","転換","新事業","多角化","業態"],
        "物価・光熱費対策": ["物価","光熱費","エネルギー","電気代","燃料","高騰"],
        "医療・福祉":       ["医療","診療","病院","薬局","介護","福祉","保険"],
        "農業・水産":       ["農業","水産","漁業","林業","農林"],
        "観光・飲食":       ["観光","飲食","宿泊","ホテル","旅館"],
        "防災・安全":       ["防災","耐震","BCP","安全"],
    }
    for cat, kws in mapping.items():
        if any(kw in text for kw in kws):
            return cat
    return "補助金・助成金（一般）"

def convert_item(item):
    title = item.get("title", "")
    subsidy_id = item.get("id", "")
    url = item.get("front_subsidy_detail_page_url", "") or \
          f"https://www.jgrants-portal.go.jp/subsidy/{subsidy_id}"

    amount = ""
    upper = item.get("subsidy_max_limit")
    if upper:
        try:
            amount = f"上限 {int(float(upper)):,}円"
        except Exception:
            amount = str(upper)

    deadline = ""
    end_date = item.get("acceptance_end_datetime", "") or ""
    if end_date and len(end_date) >= 10:
        try:
            d = datetime.strptime(end_date[:10], "%Y-%m-%d")
            y = d.year - 2018
            deadline = f"令和{y}年{d.month}月{d.day}日締切"
        except Exception:
            deadline = end_date[:10]

    target_area = item.get("target_area_search", "") or ""
    pref = get_pref(target_area)
    org = item.get("government_name", "") or "国・自治体"

    if pref in KANTO_PREFS:
        source = "自治体"
    elif pref != "全国" and pref:
        source = "自治体"
    else:
        source = "国・省庁"

    target = item.get("target_number_of_employees", "") or ""
    use_purpose = item.get("use_purpose", "") or ""

    return {
        "id": str(subsidy_id),
        "title": title[:120],
        "org": org[:40],
        "pref": pref,
        "amount": amount[:60],
        "deadline": deadline[:60],
        "target": target[:80],
        "category": classify(title, use_purpose),
        "url": url,
        "source": source,
        "date": str(date.today()),
    }

def main():
    all_items = []
    seen_ids = set()

    for kw in KEYWORDS:
        logger.info(f"キーワード検索: {kw}")
        offset = 0
        while True:
            data = fetch_subsidies(keyword=kw, limit=100, offset=offset)
            if not data:
                break
            result = data.get("result", []) or []
            if not result:
                break
            added = 0
            for item in result:
                sid = str(item.get("id", ""))
                if sid and sid not in seen_ids:
                    seen_ids.add(sid)
                    all_items.append(convert_item(item))
                    added += 1
            total = int((data.get("metadata", {}) or {}).get("resultset", {}).get("count", 0) or 0)
            logger.info(f"  {kw}: +{added}件 (計{len(all_items)}件, total={total})")
            if total == 0 or offset + 100 >= total:
                break
            offset += 100
            time.sleep(0.5)
        time.sleep(0.8)

    kanto = [x for x in all_items if x["pref"] in KANTO_PREFS]
    others = [x for x in all_items if x["pref"] not in KANTO_PREFS]
    all_items = kanto + others

    logger.info(f"収集完了: {len(all_items)}件（うち1都3県: {len(kanto)}件）")

    existing = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            try:
                existing = json.load(f).get("items", [])
            except Exception:
                existing = []

    today_str = str(date.today())
    old_data = [r for r in existing if r.get("date") != today_str]
    combined = all_items + old_data
    cutoff = str(date.today() - timedelta(days=90))
    combined = [r for r in combined if r.get("date", "") >= cutoff]

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
