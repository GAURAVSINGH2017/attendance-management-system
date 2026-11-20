from pathlib import Path
from PIL import Image, ImageDraw

directory = Path(__file__).resolve().parent / "screens"
files = sorted(directory.glob("*.png"))
items = []
for file in files:
    image = Image.open(file).convert("RGB")
    image.thumbnail((480, 320))
    items.append((file.stem, image.copy()))
sheet = Image.new("RGB", (1500, ((len(items) + 2) // 3) * 360), "#e7e8ee")
draw = ImageDraw.Draw(sheet)
for index, (name, image) in enumerate(items):
    x, y = (index % 3) * 500 + 10, (index // 3) * 360 + 28
    draw.text((x, y - 20), name, fill="#20243b")
    sheet.paste(image, (x, y))
sheet.save(directory / "contact.png")
