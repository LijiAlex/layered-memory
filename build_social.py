"""Generate the 1280x640 GitHub social-preview banner -> assets/social-preview.png.
Run from repo root: python3 build_social.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
BG = (13, 17, 23)        # GitHub dark
PANEL = (22, 27, 34)     # card
BORDER = (48, 54, 61)
WHITE = (230, 237, 243)
MUTED = (139, 148, 158)
ACCENT = (217, 119, 87)  # Claude orange
GREEN = (63, 185, 80)

SF = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"

def f(path, size):
    return ImageFont.truetype(path, size)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# subtle accent rule down the left edge
d.rectangle([0, 0, 10, H], fill=ACCENT)

PAD = 84

# pill: "CLAUDE CODE PLUGIN"
pill_font = f(SF, 22)
pill_txt = "CLAUDE CODE PLUGIN"
tb = d.textbbox((0, 0), pill_txt, font=pill_font)
pw, ph = tb[2] - tb[0], tb[3] - tb[1]
px, py = PAD, 86
d.rounded_rectangle([px, py, px + pw + 44, py + ph + 26], radius=18,
                    fill=(40, 26, 21), outline=ACCENT, width=2)
d.text((px + 22, py + 9), pill_txt, font=pill_font, fill=ACCENT)

# left column must stop short of the panel
COL_W = 792 - PAD - 40  # right edge of text column

# title (auto-fit width to the left column)
title = "layered-memory"
tsize = 104
while tsize > 40:
    title_font = f(SF, tsize)
    if d.textbbox((0, 0), title, font=title_font)[2] <= COL_W:
        break
    tsize -= 2
d.text((PAD - 4, 158), title, font=title_font, fill=WHITE)

# tagline (two lines, hand-wrapped)
tag_font = f(SF, 32)
d.text((PAD, 290), "Persistent memory for Claude Code —", font=tag_font, fill=MUTED)
d.text((PAD, 332), "markdown you can read, diff, and delete.", font=tag_font, fill=MUTED)

# feature chips: two rows, kept inside the left column
feat_font = f(SF, 25)
rows = [["no database", "no vector store"], ["auditable", "git-versionable"]]
fy = 408
for row in rows:
    fx = PAD
    for t in row:
        d.ellipse([fx, fy + 9, fx + 12, fy + 21], fill=GREEN)
        d.text((fx + 24, fy), t, font=feat_font, fill=WHITE)
        fx += d.textbbox((0, 0), t, font=feat_font)[2] + 24 + 56
    fy += 46

# footer
foot_font = f(SF, 24)
d.text((PAD, H - 70), "github.com/LijiAlex/layered-memory", font=foot_font, fill=MUTED)

# right-side file-tree panel
panel_x0, panel_y0, panel_x1, panel_y1 = 792, 150, W - 64, 470
d.rounded_rectangle([panel_x0, panel_y0, panel_x1, panel_y1], radius=16,
                    fill=PANEL, outline=BORDER, width=2)
# title bar dots
for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
    d.ellipse([panel_x0 + 22 + i * 26, panel_y0 + 22, panel_x0 + 34 + i * 26, panel_y0 + 34], fill=c)

mono = f(MONO, 22)
mono_dim = f(MONO, 22)
lines = [
    ("~/.claude/memory/", MUTED),
    ("├── index.md", WHITE),
    ("└── themes/", WHITE),
    ("    ├── govfoun-438.md", ACCENT),
    ("    ├── atlas-purge.md", ACCENT),
    ("    └── layered-memory.md", ACCENT),
]
ly = panel_y0 + 70
for txt, col in lines:
    d.text((panel_x0 + 28, ly), txt, font=mono, fill=col)
    ly += 38

os.makedirs("assets", exist_ok=True)
out = "assets/social-preview.png"
img.save(out)
print("wrote", out, img.size, os.path.getsize(out), "bytes")
