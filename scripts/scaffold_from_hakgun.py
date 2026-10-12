#!/usr/bin/env python3
"""scaffold_from_hakgun.py - 우아학군 사이트의 공용 뼈대(CSS·JS·include·개인정보·robots·deploy)를 복사해 우아빌라용으로 치환한다(1회성)."""
import re, shutil, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SRC = Path(r"C:\개인\wooahouse\wooahakgun")
DST = Path(r"C:\개인\wooahouse\wooavilla")

COLORS = {            # 인디고 → 틸
    "#4F46E5": "#0D9488", "#4f46e5": "#0D9488",
    "#6366F1": "#14B8A6", "#6366f1": "#14B8A6",
    "#4338CA": "#0F766E", "#4338ca": "#0F766E",
    "#3730A3": "#115E59", "#3730a3": "#115E59",
    "#EEF2FF": "#F0FDFA", "#eef2ff": "#F0FDFA",
    "#E0E7FF": "#CCFBF1", "#e0e7ff": "#CCFBF1",
    "#C7D2FE": "#99F6E4", "#c7d2fe": "#99F6E4",
    "#A5B4FC": "#5EEAD4", "#a5b4fc": "#5EEAD4",
}
TEXT = [("wooahakgun", "wooavilla"), ("우아학군", "우아빌라")]


def conv(text):
    for a, b in COLORS.items():
        text = text.replace(a, b)
    for a, b in TEXT:
        text = text.replace(a, b)
    return text


def copy(rel, convert=True):
    s, d = SRC / rel, DST / rel
    d.parent.mkdir(parents=True, exist_ok=True)
    if convert:
        d.write_text(conv(s.read_text(encoding="utf-8")), encoding="utf-8")
    else:
        shutil.copyfile(s, d)
    print("복사:", rel)


for rel in ["assets/css/main.css", "assets/js/ad-dev-placeholder.js", "assets/js/wooa-sidebar.js", "assets/js/wooa-sites-bar.js",
            "_includes/ad.html", "_includes/faq.html", "privacy/index.html", "robots.txt", "CNAME", "Gemfile", ".gitignore", ".github/workflows/deploy.yml"]:
    copy(rel, convert=not rel.startswith("assets/js"))
