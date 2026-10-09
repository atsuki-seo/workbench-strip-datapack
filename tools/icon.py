#!/usr/bin/env python3
"""WorkbenchStrip のアイコン(pack.png)を、32x32 のドット絵として描いて PNG にする。

左上: 原木(樹皮つき)   右上: 樹皮を剥いだ原木
左下: 酸化した銅       右下: 銅ブロック
中央: 作業台(天面)と、その影

左の列が変換前、右の列が変換後を表す。乱数は座標から決まるハッシュを使うので、毎回同じ画像になる。
標準ライブラリだけを使う。単独で実行すると、引数のパスに PNG を書き出す。
"""

import struct
import sys
import zlib
from pathlib import Path

SIZE = 32
SCALE = 4  # 128x128 で出力する(ドット絵なので最近傍で拡大)

Color = tuple[int, int, int]


def hex_color(code: str) -> Color:
    return (int(code[0:2], 16), int(code[2:4], 16), int(code[4:6], 16))


def noise(x: int, y: int, salt: int) -> int:
    """座標から 0〜255 の値を返す決定的なハッシュ。"""
    h = (x * 374761393 + y * 668265263 + salt * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFF


def pick(palette: list[str], value: int) -> Color:
    return hex_color(palette[value * len(palette) // 256])


# 原木の樹皮: 縦方向の筋。列ごとに明るさを決め、ところどころ暗い溝を入れる
BARK = ["3f311c", "4c3b22", "5a4529", "6a5233", "7a6040"]


def bark(x: int, y: int) -> Color:
    column = noise(x, 0, 1)
    if column < 90 and noise(x, y // 5, 2) < 220:
        return hex_color(BARK[0])  # 溝
    shade = (column * 3 + noise(x, y, 3)) // 4
    return pick(BARK[1:], shade)


# 樹皮を剥いだ原木: 明るい木肌に、細い木目の線
STRIPPED = ["8e6e3f", "a07f4c", "b08d57", "bd9a62", "c9a86f"]


def stripped(x: int, y: int) -> Color:
    if noise(x, 0, 4) < 45 and noise(x, y // 4, 5) < 210:
        return hex_color(STRIPPED[0])  # 木目
    return pick(STRIPPED[1:], (noise(x, 0, 6) + noise(x, y, 7)) // 2)


def bevel(x: int, y: int, base: Color, light: Color, dark: Color) -> Color:
    """16x16 タイルの縁を、左上は明るく、右下は暗くする(銅ブロックの面取り)。"""
    lx, ly = x % 16, y % 16
    if lx == 0 or ly == 0:
        return light
    if lx == 15 or ly == 15:
        return dark
    return base


# 酸化した銅: 青緑のまだら
OXIDIZED = ["3e7a63", "4f9c80", "52a384", "5baf91", "6cbfa1"]


def oxidized(x: int, y: int) -> Color:
    base = pick(OXIDIZED, (noise(x // 2, y // 2, 8) + noise(x, y, 9)) // 2)
    return bevel(x, y, base, hex_color("7fd0b2"), hex_color("2f5f4d"))


# 銅ブロック: 赤みのある橙色
COPPER = ["a35a3e", "c06b4f", "cf7454", "e07a5a", "e98a66"]


def copper(x: int, y: int) -> Color:
    base = pick(COPPER, (noise(x // 2, y // 2, 10) + noise(x, y, 11)) // 2)
    return bevel(x, y, base, hex_color("f4a37e"), hex_color("7e4330"))


# 作業台の天面(12x12)。外枠と、3x3 のマス目
TABLE = [
    "############",
    "#ffffffffff#",
    "#fpp-pp-ppf#",
    "#fpp-pp-ppf#",
    "#f--------f#",
    "#fpp-pp-ppf#",
    "#fpp-pp-ppf#",
    "#f--------f#",
    "#fpp-pp-ppf#",
    "#fpp-pp-ppf#",
    "#ffffffffff#",
    "############",
]
TABLE_COLORS = {
    "#": "24180c",  # 輪郭
    "f": "6b4a2b",  # 外枠
    "-": "5a3d22",  # マス目の線
}
TABLE_PLANKS = ["b8945f", "c4a26c", "d0ae78"]
TABLE_SIZE = len(TABLE)
TABLE_ORIGIN = ((SIZE - TABLE_SIZE) // 2, (SIZE - TABLE_SIZE) // 2)


def table(lx: int, ly: int) -> Color:
    ch = TABLE[ly][lx]
    if ch == "p":
        return pick(TABLE_PLANKS, noise(lx, ly, 12))
    return hex_color(TABLE_COLORS[ch])


def darken(color: Color, ratio: float) -> Color:
    return tuple(int(c * ratio) for c in color)


def pixel(x: int, y: int) -> Color:
    ox, oy = TABLE_ORIGIN
    if ox <= x < ox + TABLE_SIZE and oy <= y < oy + TABLE_SIZE:
        return table(x - ox, y - oy)
    if y < 16:
        base = bark(x, y) if x < 16 else stripped(x, y)
    else:
        base = oxidized(x, y) if x < 16 else copper(x, y)
    # 作業台の右下に1マスずらした影を落とす
    if ox < x <= ox + TABLE_SIZE and oy < y <= oy + TABLE_SIZE:
        return darken(base, 0.55)
    return base


def render() -> list[list[Color]]:
    return [[pixel(x, y) for x in range(SIZE)] for y in range(SIZE)]


def encode_png(pixels: list[list[Color]], scale: int) -> bytes:
    width = len(pixels[0]) * scale
    height = len(pixels) * scale
    raw = bytearray()
    for row in pixels:
        line = b"\x00" + b"".join(bytes(c) * scale for c in row)  # フィルタ種別 0
        raw += line * scale

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def icon_png() -> bytes:
    return encode_png(render(), SCALE)


if __name__ == "__main__":
    Path(sys.argv[1]).write_bytes(icon_png())
