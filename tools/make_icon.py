"""生成卷宗应用图标：深蓝圆角底 + 蓝色书脊 + 白色「卷」字。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "assets" / "juanzong.ico"
S = 256

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 深蓝圆角底（与 PPT 视觉系统 #0F172A 一致）
d.rounded_rectangle([8, 8, S - 8, S - 8], radius=52, fill=(15, 23, 42, 255))
# 左侧蓝色书脊（#3B82F6）
d.rounded_rectangle([16, 16, 52, S - 16], radius=18, fill=(59, 130, 246, 255))
# 顶部青色书签（#06B6D4）
d.rounded_rectangle([196, 24, 228, 96], radius=8, fill=(6, 182, 212, 255))

font = None
for name in ("msyhbd.ttc", "msyh.ttc", "simhei.ttf"):
    try:
        font = ImageFont.truetype(f"C:/Windows/Fonts/{name}", 150)
        break
    except OSError:
        continue
assert font, "no CJK font found"

# 单字居中（视觉中心略偏右避开书脊）
d.text((S / 2 + 16, S / 2), "卷", font=font, fill=(241, 245, 249, 255), anchor="mm")

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("icon ->", OUT)
