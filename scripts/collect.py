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

def test_patterns():
    """どのパラメータが動くか確認"""
    patterns = [
        {"keyword": "補助金"},
        {"keyword": "subsidy"},
        {"keyword": "補助金", "sort": "created_date", "order": "DESC"},
        {"sort": "created_date", "order": "DESC", "limit": 10},
        {"limit": 10, "offset": 0},
        {"keyword": "補助金", "limit": 10},
    ]
    for p in patterns:
        try:
            res = requests.get(BASE_URL, headers=HEADERS, params=p, timeout=15)
            body = res.text[:150]
            logger.info(f"Pattern {p} → {res.status_code}: {body}")
        except Exception as e:
            logger.warning(f"Pattern {p} → Error: {e}")
        time.sleep(1)

def main():
    logger.info("=== APIパラメータテスト ===")
    test_patterns()

    # 既存データを保持
    existing = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            try: existing = json.load(f).get("items", [])
            except: existing = []

    logger.info(f"既存データ: {len(existing)}件")

if __name__ == "__main__":
    main()
