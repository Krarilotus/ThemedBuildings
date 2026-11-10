"""Build module/resources/tile_churches_themed.gm1 from the themed building PNGs.

The game draws a building tile by tile: every footprint tile has a 30x16 ground diamond, and
the tiles along the two front edges also carry a vertical strip of the building above them
(16 px wide, the front corner 30 px). This slices each PNG the same way, into a copy of the
base tile_churches.gm1 whose three buildings are replaced:

    group 0  cathedral (13x13)  <- grand_mosque.png   (414 px wide)
    group 1  church    (9x9)    <- church.png         (286 px wide)
    group 2  chapel    (6x6)    <- small_mosque.png   (190 px wide)

A PNG is 32*N-2 wide with the footprint's front corner on its bottom row.

    python tools/build_gm1.py [--png-dir DIR] [--base GM1] [--check]
--check draws every group back the way the game does and reports how many opaque PNG pixels
it could not place (they sit outside the building's tiles and strips); the drawings go to
check/.
"""
import os, struct, sys
from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = r'H:\steam\steamapps\common\Stronghold Crusader Extreme UCP3 new'
PLUGIN = os.path.join(GAME, 'ucp', 'plugins', 'Reconquista-1.0.0', 'resources')
PNG_DIR = os.path.join(PLUGIN, 'themed buildings')
BASES = [os.path.join(PLUGIN, 'gmx', 'tile_churches.gm1'), os.path.join(GAME, 'gm', 'tile_churches.gm1')]
OUT = os.path.join(HERE, 'module', 'resources', 'tile_churches_themed.gm1')
CHECK = os.path.join(HERE, 'check')
GROUPS = [(0, 13, 'grand_mosque.png'), (1, 9, 'church.png'), (2, 6, 'small_mosque.png')]
HEAD = '<4H2Bh4B'   # w, h, x, y, part, parts, tilePosY, direction, hoff, strip width, colour


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def load(path):
    f = open(path, 'rb').read()
    n = struct.unpack_from('<I', f, 12)[0]
    base = 88 + 5120
    offs = list(struct.unpack_from('<%dI' % n, f, base))
    sizes = list(struct.unpack_from('<%dI' % n, f, base + 4 * n))
    hdr = base + 8 * n
    data = hdr + 16 * n
    heads = [list(struct.unpack_from(HEAD, f, hdr + 16 * i)) for i in range(n)]
    blobs = [f[data + offs[i]:data + offs[i] + sizes[i]] for i in range(n)]
    return f, n, heads, blobs


def diamond_rows():
    """(row, x0, width) of the 30x16 ground diamond, in the order its 256 pixels are stored."""
    for i in range(16):
        w = 4 * i + 2 if i < 8 else 30 - 4 * (i - 8)
        yield i, (30 - w) // 2, w


def tiles(n):
    """Footprint tiles in part order: top-left of each tile's 30x16 box, footprint top-left 0,0."""
    out = []
    for r in range(2 * n - 1):
        k = r + 1 if r < n else 2 * n - 1 - r
        for j in range(k):
            out.append((16 * (n - k) + 32 * j, 8 * r))
    return out


def c555(p):
    r, g, b = p[:3]
    return ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)


def rgb(v):
    return (((v >> 10) & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, (v & 31) * 255 // 31, 255)


def tgx(rows):
    """rows: lists of 555 values or None (see-through) -> 16-bit TGX stream."""
    out = bytearray()
    for row in rows:
        x, w = 0, len(row)
        while x < w:
            if row[x] is None:
                n = 1
                while x + n < w and row[x + n] is None and n < 32:
                    n += 1
                out.append(0x20 | (n - 1))
                x += n
                continue
            n = 1
            while x + n < w and row[x + n] == row[x] and n < 32:
                n += 1
            if n >= 3:
                out.append(0x40 | (n - 1)); out += struct.pack('<H', row[x]); x += n
                continue
            n = 1
            while x + n < w and row[x + n] is not None and n < 32 and not (
                    x + n + 2 < w and row[x + n] == row[x + n + 1] == row[x + n + 2]):
                n += 1
            out.append(n - 1)
            for v in row[x:x + n]:
                out += struct.pack('<H', v)
            x += n
        out.append(0x80)
    return bytes(out)


def untgx(data, w, h):
    rows, p, y, x = [[None] * w for _ in range(h)], 0, 0, 0
    while p < len(data) and y < h:
        b = data[p]; p += 1; t, n = b >> 5, (b & 31) + 1
        if t == 4:
            y += 1; x = 0
        elif t == 1:
            x += n
        elif t == 2:
            v = struct.unpack_from('<H', data, p)[0]; p += 2
            for _ in range(n):
                if x < w: rows[y][x] = v
                x += 1
        elif t == 0:
            for _ in range(n):
                v = struct.unpack_from('<H', data, p)[0]; p += 2
                if x < w: rows[y][x] = v
                x += 1
    return rows


def slice_group(img, n, heads, blobs, first):
    W, H = img.size
    assert W == 32 * n - 2, 'PNG must be %d px wide for a %dx%d building, is %d' % (32 * n - 2, n, n, W)
    y0 = H - 16 * n
    px = img.load()

    def at(x, y):
        if 0 <= x < W and 0 <= y < H and px[x, y][3] >= 128:
            return c555(px[x, y])
        return None

    top = [next((y for y in range(H) if px[x, y][3] >= 128), H) for x in range(W)]
    new_heads, new_blobs = [], []
    for part, (tx, ty) in enumerate(tiles(n)):
        i = first + part
        h = list(heads[i]); old = blobs[i]
        ty += y0
        dia = bytearray()
        k = 0
        for row, x0, w in diamond_rows():
            for x in range(x0, x0 + w):
                v = at(tx + x, ty + row)
                if v is None:                      # keep the old ground where the PNG is see-through
                    v = struct.unpack_from('<H', old, 2 * k)[0]
                dia += struct.pack('<H', v); k += 1
        direction, hoff, bw = h[7], h[8], h[9]
        if direction:
            cols = range(tx + hoff, tx + hoff + bw)
            t = min([top[x] for x in cols if 0 <= x < W] + [ty])
            tpy = ty - t
            rows = [[at(x, y) for x in cols] for y in range(ty - tpy, ty + 7)]
            h[6] = tpy
            h[1] = tpy + 16
            new_blobs.append(bytes(dia) + tgx(rows))
        else:
            h[6] = 0
            h[1] = 16
            new_blobs.append(bytes(dia))
        new_heads.append(h)
    return new_heads, new_blobs


def render(n, heads, blobs, first):
    """Draw a group the way renderMap does: every ground diamond, then the strips, back to front."""
    tall = max(h[6] for h in heads[first:first + n * n])
    W, H = 32 * n - 2, 16 * n + tall
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); px = img.load()
    y0 = H - 16 * n
    for part, (tx, ty) in enumerate(tiles(n)):
        k = 0
        for row, x0, w in diamond_rows():
            for x in range(x0, x0 + w):
                px[tx + x, y0 + ty + row] = rgb(struct.unpack_from('<H', blobs[first + part], 2 * k)[0]); k += 1
    for part, (tx, ty) in enumerate(tiles(n)):
        h = heads[first + part]
        if not h[7]:
            continue
        tpy, hoff, bw = h[6], h[8], h[9]
        for yy, row in enumerate(untgx(blobs[first + part][512:], bw, tpy + 7)):
            for xx, v in enumerate(row):
                if v is not None:
                    px[tx + hoff + xx, y0 + ty - tpy + yy] = rgb(v)
    return img


def main():
    png_dir = arg('--png-dir', PNG_DIR)
    base = arg('--base', next(p for p in BASES if os.path.isfile(p)))
    f, n, heads, blobs = load(base)
    starts = [i for i, h in enumerate(heads) if h[4] == 0]
    print('base', base, n, 'images, buildings start at', starts)
    if '--check' in sys.argv:
        os.makedirs(CHECK, exist_ok=True)
        for g, size, name in GROUPS:
            render(size, heads, blobs, starts[g]).save(os.path.join(CHECK, 'original_%d.png' % g))
    for g, size, name in GROUPS:
        first = starts[g]
        assert heads[first][5] == size * size, 'building %d is not %dx%d' % (g, size, size)
        img = Image.open(os.path.join(png_dir, name)).convert('RGBA')
        nh, nb = slice_group(img, size, heads, blobs, first)
        heads[first:first + size * size] = nh
        blobs[first:first + size * size] = nb
        if '--check' in sys.argv:
            back = render(size, heads, blobs, first)
            back.save(os.path.join(CHECK, 'themed_' + name))
            W, H = img.size; bh = back.size[1]
            src, out = img.load(), back.load()
            lost = 0
            for y in range(H):
                for x in range(W):
                    yy = y - (H - bh)
                    if src[x, y][3] >= 128 and (yy < 0 or out[x, yy][3] == 0 or c555(out[x, yy]) != c555(src[x, y])):
                        lost += 1
            print('%-17s %4d tall pieces, %d opaque pixels not placed' % (
                name, sum(1 for h in nh if h[7]), lost))
    offs, data = [], bytearray()
    for b in blobs:
        offs.append(len(data)); data += b
    out = bytearray(f[:88 + 5120])
    struct.pack_into('<I', out, 12, n)
    struct.pack_into('<I', out, 80, len(data))
    out += struct.pack('<%dI' % n, *offs)
    out += struct.pack('<%dI' % n, *[len(b) for b in blobs])
    for h in heads:
        out += struct.pack(HEAD, *h)
    out += data
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'wb').write(out)
    print('wrote', OUT, len(out), 'bytes')


if __name__ == '__main__':
    main()
