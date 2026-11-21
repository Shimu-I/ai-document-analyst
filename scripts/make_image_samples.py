import sys, json, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
out = sys.argv[1]
fonts = [f for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"] if __import__('os').path.exists(f)]
print("fonts:", fonts)
F = fonts[0]
TEXT = ["Meeting notes - Project Atlas", "Date: 12 March 2026", "Attendees: Ada, Grace, Linus",
        "1. Budget approved: $12,400", "2. Launch moved to April 9", "3. Owner of risks: Grace"]
def render(size, w, h, name, noise=0, blur=0, rot=0, fmt="PNG"):
    img = Image.new("RGB", (w, h), "white"); d = ImageDraw.Draw(img)
    f = ImageFont.truetype(F, size); y = 10
    for line in TEXT: d.text((10, y), line, fill="black", font=f); y += int(size*1.6)
    if rot: img = img.rotate(rot, expand=True, fillcolor="white")
    if blur: img = img.filter(ImageFilter.GaussianBlur(blur))
    if noise:
        px = img.load(); r = random.Random(1)
        for _ in range(int(w*h*noise)): px[r.randrange(img.width), r.randrange(img.height)] = (r.randint(80,200),)*3
    img.save(f"{out}/{name}", fmt, **({"quality": 60} if fmt == "JPEG" else {}))
render(28, 700, 330, "clean.png")
render(28, 700, 330, "photo.jpg", noise=0.01, blur=0.8, rot=2, fmt="JPEG")
render(12, 330, 160, "small.png")                    # small screenshot text
render(28, 700, 330, "clean.webp", fmt="WEBP")

# --- harder cases
def dark(name):
    img = Image.new("RGB", (700, 330), (30, 30, 34)); d = ImageDraw.Draw(img); f = ImageFont.truetype(F, 28); y = 10
    for line in TEXT: d.text((10, y), line, fill=(230, 230, 230), font=f); y += 44
    img.save(f"{out}/{name}")
def transparent(name):
    img = Image.new("RGBA", (700, 330), (0, 0, 0, 0)); d = ImageDraw.Draw(img); f = ImageFont.truetype(F, 28); y = 10
    for line in TEXT: d.text((10, y), line, fill=(0, 0, 0, 255), font=f); y += 44
    img.save(f"{out}/{name}")
def article(name):
    img = Image.new("RGB", (900, 520), "white"); d = ImageDraw.Draw(img)
    d.text((20, 15), "Quarterly Update", fill="black", font=ImageFont.truetype(F, 44))
    f = ImageFont.truetype(F, 22); y = 85
    para = ["Revenue grew in every region this quarter and the support", "backlog fell by a third. Two vendors were replaced and the", "remaining contracts were renegotiated."]
    for l in para: d.text((20, y), l, fill="black", font=f); y += 30
    y += 28
    for l in ["- Throughput rose in every region", "- Support backlog fell by a third", "- Two vendors were replaced"]:
        d.text((20, y), l, fill="black", font=f); y += 30
    img.save(f"{out}/article.png")
dark("dark.png"); transparent("transparent.png"); article("article.png")
