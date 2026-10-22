# Writes DXF files shaped the way other CAD programs write them, for testing
# Jw_cad's DXF reader in the emulator (tests/io/ext_*.dxf):
#
#   ext_r12.dxf     AutoCAD R12 (AC1009), ENTITIES section only, Shift-JIS text,
#                   LINE/CIRCLE/ARC/POINT/TEXT/POLYLINE, several layers and colours
#   ext_r2000.dxf   AC1015 with HEADER/TABLES/BLOCKS: LWPOLYLINE with bulges,
#                   ELLIPSE, SPLINE, MTEXT, INSERT of a block, Shift-JIS text
#   ext_r2007.dxf   AC1021, where text is UTF-8
#
#   python tools/gen_dxf.py
import math
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tests', 'io')


def pairs(*kv):
    out = []
    for i in range(0, len(kv), 2):
        out.append(f'{kv[i]:>3}\n{kv[i + 1]}\n')
    return ''.join(out)


def common_entities(jp):
    e = ''
    # A 6000 x 4000 room outline on layer WALL, red.
    pts = [(0, 0), (6000, 0), (6000, 4000), (0, 4000)]
    for i in range(4):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 4]
        e += pairs(0, 'LINE', 8, 'WALL', 62, 1, 10, x0, 20, y0, 30, 0, 11, x1, 21, y1, 31, 0)
    e += pairs(0, 'CIRCLE', 8, 'EQUIP', 62, 3, 10, 1500, 20, 2000, 30, 0, 40, 500)
    e += pairs(0, 'ARC', 8, 'EQUIP', 62, 5, 10, 4500, 20, 2000, 30, 0, 40, 700, 50, 0, 51, 180)
    e += pairs(0, 'POINT', 8, '0', 10, 3000, 20, 3500, 30, 0)
    e += pairs(0, 'TEXT', 8, 'TEXT', 62, 7, 10, 500, 20, 4300, 30, 0, 40, 250, 1, 'ROOM A-101')
    e += pairs(0, 'TEXT', 8, 'TEXT', 62, 2, 10, 500, 20, -600, 30, 0, 40, 300, 50, 0, 1, jp)
    return e


def write(name, text, encoding):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), 'w', encoding=encoding, newline='\r\n') as f:
        f.write(text)


def r12():
    e = common_entities('居間（ＬＤＫ）１２畳')
    e += pairs(0, 'POLYLINE', 8, 'WALL', 66, 1, 70, 1, 10, 0, 20, 0, 30, 0)
    for x, y in [(2500, 500), (3500, 500), (3500, 1500), (2500, 1500)]:
        e += pairs(0, 'VERTEX', 8, 'WALL', 10, x, 20, y, 30, 0)
    e += pairs(0, 'SEQEND', 8, 'WALL')
    write('ext_r12.dxf', pairs(0, 'SECTION', 2, 'ENTITIES') + e + pairs(0, 'ENDSEC', 0, 'EOF'), 'cp932')


def header(ver, codepage):
    return (pairs(0, 'SECTION', 2, 'HEADER', 9, '$ACADVER', 1, ver, 9, '$DWGCODEPAGE', 3, codepage,
                  9, '$INSUNITS', 70, 4, 9, '$EXTMIN', 10, -1000, 20, -1000, 30, 0,
                  9, '$EXTMAX', 10, 9000, 20, 6000, 30, 0, 0, 'ENDSEC'))


def tables():
    t = pairs(0, 'SECTION', 2, 'TABLES', 0, 'TABLE', 2, 'LTYPE', 70, 2)
    t += pairs(0, 'LTYPE', 2, 'CONTINUOUS', 70, 0, 3, 'Solid line', 72, 65, 73, 0, 40, 0.0)
    t += pairs(0, 'LTYPE', 2, 'DASHED', 70, 0, 3, '__ __ __', 72, 65, 73, 2, 40, 600.0, 49, 400.0, 49, -200.0)
    t += pairs(0, 'ENDTAB', 0, 'TABLE', 2, 'LAYER', 70, 5)
    for name, col, lt in [('0', 7, 'CONTINUOUS'), ('WALL', 1, 'CONTINUOUS'), ('EQUIP', 3, 'CONTINUOUS'),
                          ('TEXT', 7, 'CONTINUOUS'), ('CENTER', 4, 'DASHED')]:
        t += pairs(0, 'LAYER', 2, name, 70, 0, 62, col, 6, lt)
    t += pairs(0, 'ENDTAB', 0, 'ENDSEC')
    return t


def modern_entities(jp, mtext):
    e = common_entities(jp)
    # A closed LWPOLYLINE with one rounded corner (bulge 0.414 = 45 degrees arc).
    e += pairs(0, 'LWPOLYLINE', 8, 'WALL', 90, 4, 70, 1,
               10, 2500, 20, 500, 10, 3500, 20, 500, 42, math.tan(math.radians(90) / 4),
               10, 3800, 20, 800, 10, 2500, 20, 1500)
    e += pairs(0, 'ELLIPSE', 8, 'EQUIP', 62, 6, 10, 3000, 20, 3000, 30, 0, 11, 800, 21, 0, 31, 0,
               210, 0, 220, 0, 230, 1, 40, 0.5, 41, 0, 42, 2 * math.pi)
    e += pairs(0, 'SPLINE', 8, 'EQUIP', 62, 4, 210, 0, 220, 0, 230, 1, 70, 8, 71, 3, 72, 8, 73, 4, 74, 0,
               40, 0, 40, 0, 40, 0, 40, 0, 40, 1, 40, 1, 40, 1, 40, 1,
               10, 4000, 20, 3000, 30, 0, 10, 4600, 20, 3800, 30, 0, 10, 5200, 20, 2600, 30, 0, 10, 5800, 20, 3400, 30, 0)
    e += pairs(0, 'LINE', 8, 'CENTER', 10, 3000, 20, -300, 30, 0, 11, 3000, 21, 4300, 31, 0)
    e += pairs(0, 'MTEXT', 8, 'TEXT', 62, 1, 10, 6300, 20, 3800, 30, 0, 40, 200, 41, 2000, 71, 1, 1, mtext)
    e += pairs(0, 'INSERT', 8, '0', 2, 'MARK', 10, 5500, 20, 500, 30, 0, 41, 1, 42, 1, 50, 30)
    return e


def blocks():
    b = pairs(0, 'SECTION', 2, 'BLOCKS', 0, 'BLOCK', 8, '0', 2, 'MARK', 70, 0, 10, 0, 20, 0, 30, 0, 3, 'MARK')
    b += pairs(0, 'CIRCLE', 8, '0', 10, 0, 20, 0, 30, 0, 40, 200)
    b += pairs(0, 'LINE', 8, '0', 10, -300, 20, 0, 30, 0, 11, 300, 21, 0, 31, 0)
    b += pairs(0, 'LINE', 8, '0', 10, 0, 20, -300, 30, 0, 11, 0, 21, 300, 31, 0)
    b += pairs(0, 'ENDBLK', 8, '0', 0, 'ENDSEC')
    return b


def modern(name, ver, codepage, encoding, jp, mtext):
    text = (header(ver, codepage) + tables() + blocks() + pairs(0, 'SECTION', 2, 'ENTITIES') +
            modern_entities(jp, mtext) + pairs(0, 'ENDSEC', 0, 'EOF'))
    write(name, text, encoding)


def misc():
    # Entities beyond lines and arcs: SOLID, HATCH (solid fill and a pattern),
    # a linear DIMENSION with its block, TEXT with alignment, POINT, 3DFACE,
    # and a LWPOLYLINE with width.  R2000.
    e = ''
    e += pairs(0, 'SOLID', 8, 'FILL', 62, 1, 10, 0, 20, 0, 30, 0, 11, 1000, 21, 0, 31, 0, 12, 0, 22, 1000, 32, 0,
               13, 1000, 23, 1000, 33, 0)
    e += pairs(0, 'HATCH', 8, 'FILL', 62, 3, 10, 0, 20, 0, 30, 0, 210, 0, 220, 0, 230, 1, 2, 'SOLID', 70, 1, 71, 0,
               91, 1, 92, 1, 93, 4,
               72, 1, 10, 1500, 20, 0, 11, 2500, 21, 0,
               72, 1, 10, 2500, 20, 0, 11, 2500, 21, 1000,
               72, 1, 10, 2500, 20, 1000, 11, 1500, 21, 1000,
               72, 1, 10, 1500, 20, 1000, 11, 1500, 21, 0,
               97, 0, 75, 0, 76, 1, 98, 0)
    e += pairs(0, 'HATCH', 8, 'FILL', 62, 5, 10, 0, 20, 0, 30, 0, 210, 0, 220, 0, 230, 1, 2, 'ANSI31', 70, 0, 71, 0,
               91, 1, 92, 2, 72, 0, 73, 1, 93, 4,
               10, 3000, 20, 0, 10, 4000, 20, 0, 10, 4000, 20, 1000, 10, 3000, 20, 1000,
               97, 0, 75, 0, 76, 1, 52, 0, 41, 100, 77, 0, 78, 1,
               53, 45, 43, 0, 44, 0, 45, -70.71, 46, 70.71, 79, 0, 98, 0)
    # The dimension's look is its block *D1; the entity carries the measurement.
    e += pairs(0, 'DIMENSION', 8, 'DIM', 2, '*D1', 10, 0, 20, 2000, 30, 0, 11, 2000, 21, 2100, 31, 0, 70, 32,
               1, '', 13, 0, 23, 1500, 33, 0, 14, 4000, 24, 1500, 34, 0)
    e += pairs(0, 'TEXT', 8, 'TEXT', 10, 2000, 20, 2600, 30, 0, 40, 200, 1, '中央揃え', 72, 1, 11, 2000, 21, 2600, 31, 0)
    e += pairs(0, 'TEXT', 8, 'TEXT', 10, 4000, 20, 2600, 30, 0, 40, 200, 1, '右揃え', 72, 2, 11, 4000, 21, 2600, 31, 0)
    e += pairs(0, 'TEXT', 8, 'TEXT', 10, 0, 20, 2600, 30, 0, 40, 200, 50, 30, 1, '30度回転')
    e += pairs(0, 'POINT', 8, '0', 10, 4500, 20, 500, 30, 0)
    e += pairs(0, '3DFACE', 8, 'FACE', 62, 4, 10, 4500, 20, 1000, 30, 0, 11, 5500, 21, 1000, 31, 0,
               12, 5500, 22, 2000, 32, 0, 13, 4500, 23, 2000, 33, 0)
    e += pairs(0, 'LWPOLYLINE', 8, 'WIDE', 62, 6, 90, 3, 70, 0, 43, 50,
               10, 0, 20, 3200, 10, 2000, 20, 3200, 10, 4000, 20, 3600)
    b = pairs(0, 'SECTION', 2, 'BLOCKS', 0, 'BLOCK', 8, 'DIM', 2, '*D1', 70, 1, 10, 0, 20, 0, 30, 0, 3, '*D1')
    b += pairs(0, 'LINE', 8, 'DIM', 10, 0, 20, 2000, 30, 0, 11, 4000, 21, 2000, 31, 0)
    b += pairs(0, 'LINE', 8, 'DIM', 10, 0, 20, 1500, 30, 0, 11, 0, 21, 2100, 31, 0)
    b += pairs(0, 'LINE', 8, 'DIM', 10, 4000, 20, 1500, 30, 0, 11, 4000, 21, 2100, 31, 0)
    b += pairs(0, 'TEXT', 8, 'DIM', 10, 2000, 20, 2050, 30, 0, 40, 150, 1, '4000', 72, 1, 11, 2000, 21, 2050, 31, 0)
    b += pairs(0, 'ENDBLK', 8, 'DIM', 0, 'ENDSEC')
    text = header('AC1015', 'ANSI_932') + b + pairs(0, 'SECTION', 2, 'ENTITIES') + e + pairs(0, 'ENDSEC', 0, 'EOF')
    write('ext_misc.dxf', text, 'cp932')


def ellipses():
    # Tilted ellipses and an elliptical arc (Jw_cad keeps them as its own
    # rotated ellipses).
    e = ''
    c, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))
    e += pairs(0, 'ELLIPSE', 8, '0', 62, 1, 10, 0, 20, 0, 30, 0, 11, 1000 * c, 21, 1000 * s30, 31, 0,
               210, 0, 220, 0, 230, 1, 40, 0.4, 41, 0, 42, 2 * math.pi)
    e += pairs(0, 'ELLIPSE', 8, '0', 62, 5, 10, 2500, 20, 0, 30, 0, 11, 0, 21, 800, 31, 0,
               210, 0, 220, 0, 230, 1, 40, 0.5, 41, 0, 42, math.pi)
    e += pairs(0, 'LINE', 8, '0', 10, -1200, 20, 0, 30, 0, 11, 3500, 21, 0, 31, 0)
    write('ext_ellipse.dxf', header('AC1015', 'ANSI_932') + pairs(0, 'SECTION', 2, 'ENTITIES') + e +
          pairs(0, 'ENDSEC', 0, 'EOF'), 'cp932')


if __name__ == '__main__':
    ellipses()
    misc()
    r12()
    modern('ext_r2000.dxf', 'AC1015', 'ANSI_932', 'cp932', '寝室　６畳', '設計メモ\\P２行目')
    modern('ext_r2007.dxf', 'AC1021', 'ANSI_932', 'utf-8', '浴室（UTF-8）', 'UTF-8 文字\\P改行テスト')
    print('wrote', sorted(f for f in os.listdir(OUT) if f.startswith('ext_')))
