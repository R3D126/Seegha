"""Draw Seegha's icon (two arrows = conversion) and save seegha.ico. Run once: python tools/make_icon.py"""
from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# rounded square with a vertical blue gradient
grad = Image.new("RGBA", (S, S))
gp = grad.load()
for y in range(S):
    t = y / (S - 1)
    c = (int(37 + (20 - 37) * t), int(99 + (58 - 99) * t), int(235 + (150 - 235) * t), 255)
    for x in range(S):
        gp[x, y] = c
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=230, fill=255)
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)
W = (255, 255, 255, 255)
# arrow pointing right (top) and arrow pointing left (bottom)
d.rectangle((210, 320, 600, 410), fill=W)
d.polygon([(590, 230), (590, 500), (820, 365)], fill=W)
d.rectangle((420, 610, 810, 700), fill=W)
d.polygon([(430, 520), (430, 790), (200, 655)], fill=W)
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
img.resize((256, 256), Image.LANCZOS).save("seegha.ico", sizes=sizes)
print("wrote seegha.ico", sizes)
