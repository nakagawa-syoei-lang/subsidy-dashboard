#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import json, time, logging
from datetime import date, datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HISTORY_FILE = Path("docs/data.json")
BASE_URL = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies"
HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
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

def get_pref_from_text(text):
    """タイトル・説明文から都道府県を抽出"""
    for kanto in KANTO_PREFS:
        if kanto in text:
            return kanto
    for pref in ALL_PREFS:
        if pref in text:
            return pref
    return "全国"

def classify(title, use_purpose=""):
    text = title + " " + (use_purpose or "")
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
        if any(kw in text for kw in kws):
            return cat
    return "補助金・助成金（一般）"

def try_fetch_api():
    """JグランツAPIを試みる"""
    items = []
    seen_ids = set()
    
    # パラメータなしで試す
    test_params = [
        {"keyword": "補助金", "sort": "created_date", "order": "DESC", "limit": 100},
        {"keyword": "補助金", "limit": 100},
        {"sort": "created_date", "order": "DESC", "limit": 100, "offset": 0},
    ]
    
    for params in test_params:
        try:
            res = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
            logger.info(f"API試行 {params}: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                result = data.get("result", []) or []
                if result:
                    logger.info(f"API成功! {len(result)}件取得")
                    for item in result:
                        sid = str(item.get("id",""))
                        if sid and sid not in seen_ids:
                            seen_ids.add(sid)
                            title = item.get("title","")
                            subsidy_id = item.get("id","")
                            url = f"https://www.jgrants-portal.go.jp/subsidy/{subsidy_id}"
                            amount = ""
                            upper = item.get("subsidy_max_limit")
                            if upper:
                                try: amount = f"上限 {int(float(upper)):,}円"
                                except: pass
                            deadline = ""
                            end_date = item.get("acceptance_end_datetime","") or ""
                            if end_date and len(end_date) >= 10:
                                try:
                                    d = datetime.strptime(end_date[:10],"%Y-%m-%d")
                                    deadline = f"令和{d.year-2018}年{d.month}月{d.day}日締切"
                                except: pass
                            target_area = item.get("target_area_search","") or ""
                            pref = get_pref_from_text(target_area + title)
                            org = item.get("government_name","") or "国・自治体"
                            items.append({
                                "id": str(subsidy_id),
                                "title": title[:120],
                                "org": org[:40],
                                "pref": pref,
                                "amount": amount,
                                "deadline": deadline,
                                "target": item.get("target_number_of_employees","") or "",
                                "category": classify(title),
                                "url": url,
                                "source": "自治体" if pref != "全国" else "国・省庁",
                                "date": str(date.today()),
                            })
                    return items, True  # 成功
        except Exception as e:
            logger.warning(f"API試行エラー: {e}")
        time.sleep(1)
    
    return [], False  # 失敗

def fix_existing_prefs(items):
    """既存データのprefをタイトルから修正"""
    fixed = 0
    for item in items:
        if item.get("pref") == "全国":
            new_pref = get_pref_from_text(item.get("title","") + item.get("org",""))
            if new_pref != "全国":
                item["pref"] = new_pref
                item["source"] = "自治体"
                fixed += 1
    logger.info(f"pref修正: {fixed}件を全国→都道府県に更新")
    return items

def main():
    # 既存データ読み込み
    existing = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            try: existing = json.load(f).get("items", [])
            except: existing = []
    logger.info(f"既存データ: {len(existing)}件")

    # APIを試みる
    logger.info("=== JグランツAPI試行 ===")
    new_items, api_success = try_fetch_api()
    
    today_str = str(date.today())
    
    if api_success and new_items:
        logger.info(f"API成功: {len(new_items)}件取得")
        old_data = [r for r in existing if r.get("date") != today_str]
        combined = new_items + old_data
    else:
        logger.info("API失敗 → 既存データのprefを修正して使用")
        # 既存データのprefを修正
        existing = fix_existing_prefs(existing)
        # 今日のデータとして再登録
        for item in existing:
            item["date"] = today_str
        combined = existing

    cutoff = str(date.today() - timedelta(days=90))
    combined = [r for r in combined if r.get("date","") >= cutoff]

    # 1都3県を先頭に
    kanto = [x for x in combined if x.get("pref") in KANTO_PREFS]
    others = [x for x in combined if x.get("pref") not in KANTO_PREFS]
    combined = kanto + others

    kanto_count = len(kanto)
    logger.info(f"1都3県: {kanto_count}件 / 全{len(combined)}件")

    Path("docs").mkdir(exist_ok=True)
    output = {
        "updated": datetime.now().strftime("%Y年%m月%d日 %H:%M"),
        "count": len(new_items) if api_success else len(combined),
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
