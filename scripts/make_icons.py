import struct
import zlib


def png(path, size, rgb, glyph_rgb=None):
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            inside = abs(x - size / 2) < size * 0.3 and abs(y - size / 2) < size * 0.08
            row += bytes(glyph_rgb if glyph_rgb and inside else rgb) + b"\xff"
        rows.append(b"\x00" + bytes(row))
    raw = b"".join(rows)

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", header))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


if __name__ == "__main__":
    png("icon.png", 256, (214, 93, 52))
    png("node.png", 256, (69, 112, 166), (255, 255, 255))
    png("add.png", 256, (80, 150, 90), (255, 255, 255))
