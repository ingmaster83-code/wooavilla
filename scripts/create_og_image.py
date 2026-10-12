"""
create_og_image.py — OG 이미지 생성 (1200x630)
링크 공유 시 카카오톡·디스코드·슬랙 등에서 보이는 미리보기 이미지
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).parent.parent / "assets"

# 색상 (우아빌라 테마 - 인디고)
BG        = (240, 253, 250)   # #F0FDFA
ACCENT    = (15, 118, 110)    # #0F766E
ACCENT2   = (20, 184, 166)    # #14B8A6
DARK      = (17,  24,  39)
GRAY      = (107, 114, 128)
WHITE     = (255, 255, 255)

W, H = 1200, 630


def load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/malgun.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def rrect(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def create_og_image():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.ellipse([820, -120, 1380, 440], fill=(153, 246, 228))
    draw.ellipse([900, 340, 1300, 740], fill=(94, 234, 212))

    rrect(draw, (60, 60, 72, 570), 6, ACCENT)

    badge_font = load_font(22, bold=True)
    badge_text = "국토교통부 실거래가 공공데이터"
    bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    bw = bbox[2] - bbox[0] + 32
    bh = bbox[3] - bbox[1] + 14
    rrect(draw, (100, 110, 100 + bw, 110 + bh), 8, ACCENT)
    draw.text((116, 117), badge_text, fill=WHITE, font=badge_font)

    draw.text((100, 178), "빌라·오피스텔 우아빌라", fill=DARK, font=load_font(72, bold=True))
    draw.text((100, 268), "실거래가·전세가율", fill=ACCENT2, font=load_font(50, bold=True))
    draw.text((100, 390), "건물별 매매·전월세 거래 내역을 한눈에", fill=GRAY, font=load_font(32))

    icon_font = load_font(26, bold=True)
    boxes = [("빌라·오피스텔", ACCENT2), ("매매·전월세", (21, 128, 61)), ("전세가율", (124, 58, 237))]
    cx, y = 100, 456
    for label, color in boxes:
        lbbox = draw.textbbox((0, 0), label, font=icon_font)
        bw = lbbox[2] - lbbox[0] + 36
        rrect(draw, (cx, y, cx + bw, y + 50), 10, color)
        draw.text((cx + 18, y + 11), label, fill=WHITE, font=icon_font)
        cx += bw + 14

    draw.text((100, 550), "wooavilla.wooahouse.com", fill=ACCENT, font=load_font(30, bold=True))

    ASSETS_DIR.mkdir(exist_ok=True)
    out = ASSETS_DIR / "og-image.png"
    img.save(str(out), "PNG", optimize=True)
    print(f"OG image created: {out} ({W}x{H})")


if __name__ == "__main__":
    create_og_image()
