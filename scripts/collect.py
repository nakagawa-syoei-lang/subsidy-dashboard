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

PREF_NAMES = {
    "01":"北海道","02":"青森県","03":"岩手県","04":"宮城県","05":"秋田県",
    "06":"山形県","07":"福島県","08":"茨城県","09":"栃木県","10":"群馬県",
    "11":"埼玉県","12":"千葉県","13":"東京都","14":"神奈川県","15":"新潟県",
    "16":"富山県","17":"石川県","18":"福井県","19":"山梨県","20":"長野県",
    "21":"岐阜県","22":"静岡県","23":"愛知県","24":"三重県","25":"滋賀県",
    "26":"京都府","27":"大阪府","28":"兵庫県","29":"奈良県","30":"和歌山県",
    "31":"鳥取県","32":"島根県","33":"岡山県","34":"広島県","35":"山口県",
    "36":"徳島県","37":"香川県","38":"愛媛県","39":"高知県","40":"福岡県",
    "41":"佐賀県","42":"長崎県","43":"熊本県","44":"大分県","45":"宮崎県",
    "46":"鹿児島県","47":"沖縄県",
}

# 1都3県コード
KANTO_CODES = {"11", "12", "13", "14"}  # 埼玉・千葉・東京・神奈川

# 国の主要実施機関キーワード
NATIONAL_ORGS = [
    "経済産業省","厚生労働省","農林水産省","国土交通省","環境省","総務省",
    "文部科学省","内閣府","デジタル庁","中小企業庁","観光庁","消防庁",
    "中小企業基盤整備機構","日本政策金融公庫","独立行政法人","国立研究開発",
]

def fetch_subsidies(keyword="", acceptance="1", limit=100, offset=0, area=""):
    params = {
        "sort": "created_date",
        "order": "DESC",
        "acceptance": acceptance,
        "limit": limit,
        "offset": offset,
    }
    if keyword:
        params["keyword"] = keyword
    if area:
        params["target_area_search"] = area
    try:
        res = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.warning(f"API取得失敗: {e}")
        return None

def get_pref_name(code):
    if not code:
        return "全国"
    c = str(code).zfill(2)
    return PREF_NAMES.get(c, "全国")

def detect_source(org, pref_code):
    """国か自治体かを判定"""
    if pref_code and str(pref_code).zfill(2) in PREF_NAMES:
        return "自治体"
    if any(kw in (org or "") for kw in NATIONAL_ORGS):
        return "国・省庁"
    return "国・省庁"

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
    url = f"https://www.jgrants-portal.go.jp/subsidy/{subsidy_id}" if subsidy_id else ""

    # 補助金額
    amount = ""
    upper = item.get("subsidy_max_limit")
    if upper:
        try:
            amount = f"上限 {int(float(upper)):,}円"
        except Exception:
            amount = str(upper)

    # 申請期限
    deadline = ""
    end_date = item.get("acceptance_end_datetime", "") or ""
    if end_date and len(end_date) >= 10:
        try:
            d = datetime.strptime(end_date[:10], "%Y-%m-%d")
            y = d.year - 2018  # 令和換算
            deadline = f"令和{y}年{d.month}月{d.day}日締切"
        except Exception:
            deadline = end_date[:10]

    # 都道府県
    pref_code = item.get("target_area_search", "") or ""
    pref = get_pref_name(pref_code) if pref_code else "全国"

    # 実施機関
    org = item.get("government_name", "") or item.get("acceptance_agency", "") or "国・自治体"

    # ソース種別
    source = detect_source(org, pref_code)

    # 対象
    target = item.get("target_detail", "") or ""

    use_purpose = item.get("use_purpose", "") or ""

    # 1都3県フラグ
    is_kanto = str(pref_code).zfill(2) in KANTO_CODES if pref_code else False

    return {
        "id": str(subsidy_id),
        "title": title[:120],
        "org": org[:40],
        "pref": pref,
        "pref_code": str(pref_code),
        "amount": amount[:60],
        "deadline": deadline[:60],
        "target": target[:80],
        "category": classify(title, use_purpose),
        "url": url,
        "source": source,
        "is_kanto": is_kanto,
        "date": str(date.today()),
    }

def fetch_all(acceptance="1"):
    """全件取得"""
    all_items = []
    seen_ids = set()
    offset = 0
    while True:
        logger.info(f"  全国取得中... offset={offset}")
        data = fetch_subsidies(acceptance=acceptance, limit=100, offset=offset)
        if not data:
            break
        items = data.get("result", []) or []
        if not items:
            break
        for item in items:
            sid = str(item.get("id", ""))
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                all_items.append(convert_item(item))
        total = int(data.get("metadata", {}).get("totalCount", 0) or 0)
        logger.info(f"  → {len(all_items)}件取得済 / 全{total}件")
        if total == 0 or offset + 100 >= total:
            break
        offset += 100
        time.sleep(0.5)
    return all_items, seen_ids

def fetch_kanto(seen_ids):
    """1都3県を個別取得"""
    kanto_items = []
    for code in sorted(KANTO_CODES):
        pref_name = PREF_NAMES[code]
        logger.info(f"  {pref_name}を取得中...")
        for acc in ["1", "0"]:
            data = fetch_subsidies(acceptance=acc, limit=100, offset=0, area=code)
            if not data:
                continue
            items = data.get("result", []) or []
            added = 0
            for item in items:
                sid = str(item.get("id", ""))
                if sid and sid not in seen_ids:
                    seen_ids.add(sid)
                    converted = convert_item(item)
                    converted["is_kanto"] = True
                    kanto_items.append(converted)
                    added += 1
            logger.info(f"    受付{acc}: {added}件追加")
            time.sleep(0.5)
    return kanto_items

def main():
    logger.info("=== 受付中の補助金を全件取得 ===")
    all_items, seen_ids = fetch_all(acceptance="1")

    logger.info("=== 1都3県の補助金を個別取得 ===")
    kanto_items = fetch_kanto(seen_ids)
    all_items = kanto_items + all_items  # 1都3県を先頭に

    logger.info(f"収集完了: {len(all_items)}件")

    # 既存データと統合
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
