#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
補助金・助成金 収集スクリプト - Jグランツ API版
デジタル庁のJグランツAPIから補助金情報を取得
"""

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

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# 都道府県コード（01=北海道 〜 47=沖縄）
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
    "46":"鹿児島県","47":"沖縄県","99":"全国"
}

def fetch_subsidies(keyword="", acceptance="1", limit=100, offset=0):
    """Jグランツ APIから補助金一覧を取得"""
    params = {
        "sort": "created_date",
        "order": "DESC",
        "acceptance": acceptance,  # 1=受付中, 0=全件
        "limit": limit,
        "offset": offset,
    }
    if keyword:
        params["keyword"] = keyword

    try:
        res = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.warning(f"API取得失敗: {e}")
        return None

def get_pref_name(area_code):
    """都道府県コードを名前に変換"""
    if not area_code:
        return "全国"
    code = str(area_code).zfill(2)
    return PREF_NAMES.get(code, "全国")

def classify(title, use_purpose=""):
    """カテゴリ分類"""
    text = title + " " + (use_purpose or "")
    mapping = {
        "IT・デジタル":     ["IT", "DX", "デジタル", "AI", "クラウド", "ICT", "システム", "電子"],
        "雇用・人材":       ["雇用", "人材", "採用", "訓練", "賃上げ", "賃金", "労働", "働き方", "両立"],
        "設備・機械":       ["設備", "機械", "装置", "工場", "製造", "ものづくり"],
        "創業・起業":       ["創業", "起業", "スタートアップ", "開業", "新規"],
        "販路拡大":         ["販路", "輸出", "海外", "EC", "展示会", "マーケティング"],
        "省エネ・環境":     ["省エネ", "環境", "脱炭素", "再生可能", "GX", "太陽光", "蓄電"],
        "研究開発":         ["研究", "開発", "技術", "イノベーション", "R&D"],
        "融資・貸付":       ["融資", "貸付", "ローン", "資金", "金融"],
        "事業再構築":       ["再構築", "転換", "新事業", "多角化", "業態"],
        "物価・光熱費対策": ["物価", "光熱費", "エネルギー", "電気代", "燃料", "高騰"],
        "医療・福祉":       ["医療", "診療", "病院", "薬局", "介護", "福祉", "保険"],
        "農業・水産":       ["農業", "水産", "漁業", "林業", "農林"],
        "観光・飲食":       ["観光", "飲食", "宿泊", "ホテル", "旅館"],
        "防災・安全":       ["防災", "耐震", "BCP", "安全"],
    }
    for cat, kws in mapping.items():
        if any(kw in text for kw in kws):
            return cat
    return "補助金・助成金（一般）"

def get_source_type(pref):
    """国か自治体かを判定"""
    if pref in ("全国", ""):
        return "国・省庁"
    return "自治体"

def convert_item(item):
    """APIレスポンスをダッシュボード用に変換"""
    title = item.get("title", "")
    subsidy_id = item.get("id", "")
    url = f"https://www.jgrants-portal.go.jp/subsidy/{subsidy_id}" if subsidy_id else ""

    # 補助金額
    amount = ""
    upper = item.get("subsidy_max_limit")
    lower = item.get("subsidy_min_limit")
    rate = item.get("補助率") or item.get("subsidy_rate", "")
    if upper:
        amount = f"上限 {int(upper):,}円"
    elif lower:
        amount = f"{int(lower):,}円〜"
    if rate:
        amount = f"{rate} / {amount}" if amount else str(rate)

    # 申請期限
    deadline = ""
    end_date = item.get("acceptance_end_datetime", "") or item.get("end_date", "")
    if end_date:
        try:
            d = datetime.strptime(end_date[:10], "%Y-%m-%d")
            deadline = d.strftime("令和%Y年%m月%d日締切").replace(
                "令和2019", "令和元").replace("令和2020", "令和2").replace(
                "令和2021", "令和3").replace("令和2022", "令和4").replace(
                "令和2023", "令和5").replace("令和2024", "令和6").replace(
                "令和2025", "令和7").replace("令和2026", "令和8")
        except Exception:
            deadline = end_date[:10]

    # 対象・都道府県
    target = item.get("target_detail", "") or item.get("target", "") or ""
    area_code = item.get("target_area_search", "") or item.get("prefecture_code", "")
    pref = get_pref_name(area_code)

    # 実施機関
    org = item.get("government_name", "") or item.get("acceptance_agency", "") or "国・自治体"

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
        "source": get_source_type(pref),
        "date": str(date.today()),
    }

def main():
    all_items = []
    seen_ids = set()

    # 1. 受付中の補助金を全件取得
    logger.info("=== 受付中の補助金を取得 ===")
    offset = 0
    while True:
        logger.info(f"  取得中... offset={offset}")
        data = fetch_subsidies(acceptance="1", limit=100, offset=offset)
        if not data:
            break
        items = data.get("result", []) or data.get("subsidies", []) or []
        if not items:
            break
        for item in items:
            sid = str(item.get("id", ""))
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                all_items.append(convert_item(item))
        total = data.get("metadata", {}).get("totalCount", 0) or len(all_items)
        logger.info(f"  → {len(all_items)}件取得済 / 全{total}件")
        if offset + 100 >= int(total):
            break
        offset += 100
        time.sleep(0.5)

    # 2. キーワード別追加取得（受付中以外も含む）
    keywords = ["補助金", "助成金", "支援金", "給付金"]
    logger.info("=== キーワード検索で追加取得 ===")
    for kw in keywords:
        data = fetch_subsidies(keyword=kw, acceptance="0", limit=100, offset=0)
        if not data:
            continue
        items = data.get("result", []) or data.get("subsidies", []) or []
        added = 0
        for item in items:
            sid = str(item.get("id", ""))
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                all_items.append(convert_item(item))
                added += 1
        logger.info(f"  '{kw}' → {added}件追加")
        time.sleep(0.5)

    logger.info(f"収集完了: {len(all_items)}件")

    # 既存データと統合（90日分保持）
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

    # 出力
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

    logger.info(f"保存完了: docs/data.json（合計{len(combined)}件）")

if __name__ == "__main__":
    main()
