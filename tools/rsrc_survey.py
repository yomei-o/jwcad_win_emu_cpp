# Lists a PE's resources: counts per type, and for dialogs the control classes used.
import struct, sys, collections
data = open(sys.argv[1], 'rb').read()
pe = struct.unpack_from('<I', data, 0x3c)[0]
nsec = struct.unpack_from('<H', data, pe + 6)[0]
optsz = struct.unpack_from('<H', data, pe + 20)[0]
opt = pe + 24
rsrc_rva = struct.unpack_from('<I', data, opt + 96 + 2 * 8)[0]
secs = []
for i in range(nsec):
    o = opt + optsz + i * 40
    va, vs, raw, rs = struct.unpack_from('<IIII', data, o + 8)[0:1] + struct.unpack_from('<III', data, o + 12)
    vsz, va2, rsz, rp = struct.unpack_from('<IIII', data, o + 8)
    secs.append((va2, max(vsz, rsz), rp))
def off(rva):
    for va, sz, rp in secs:
        if va <= rva < va + sz: return rva - va + rp
    raise ValueError(hex(rva))
base = off(rsrc_rva)
def name_of(e):
    if e & 0x80000000:
        o = base + (e & 0x7fffffff); n = struct.unpack_from('<H', data, o)[0]
        return data[o + 2:o + 2 + 2 * n].decode('utf-16le')
    return e
def walk(o, depth, path, out):
    nn, ni = struct.unpack_from('<HH', data, o + 12)
    for i in range(nn + ni):
        nm, ptr = struct.unpack_from('<II', data, o + 16 + 8 * i)
        p = path + [name_of(nm)]
        if ptr & 0x80000000: walk(base + (ptr & 0x7fffffff), depth + 1, p, out)
        else:
            rva, sz = struct.unpack_from('<II', data, base + ptr)
            out.append((p, data[off(rva):off(rva) + sz]))
res = []; walk(base, 0, [], res)
types = collections.Counter(str(p[0]) for p, _ in res)
print(types)
cls = collections.Counter(); styles = collections.defaultdict(set)
def sz_or_ord(b, o):
    w = struct.unpack_from('<H', b, o)[0]
    if w == 0: return '', o + 2
    if w == 0xffff: return struct.unpack_from('<H', b, o + 2)[0], o + 4
    e = o
    while struct.unpack_from('<H', b, e)[0]: e += 2
    return b[o:e].decode('utf-16le'), e + 2
for p, b in res:
    if p[0] != 5: continue
    ex = struct.unpack_from('<HH', b, 0) == (1, 0xffff)
    if ex:
        style = struct.unpack_from('<I', b, 12)[0]; n = struct.unpack_from('<H', b, 16)[0]; o = 26
    else:
        style = struct.unpack_from('<I', b, 0)[0]; n = struct.unpack_from('<H', b, 8)[0]; o = 18
    menu, o = sz_or_ord(b, o); wcls, o = sz_or_ord(b, o); title, o = sz_or_ord(b, o)
    if style & 0x40:
        o += 2 + (4 if ex else 0); _, o = sz_or_ord(b, o)
    if wcls: cls['DLGCLASS:' + str(wcls)] += 1
    for i in range(n):
        o = (o + 3) & ~3
        if ex:
            hid, exs, st = struct.unpack_from('<III', b, o); o += 12 + 8; o += 4
        else:
            st, exs = struct.unpack_from('<II', b, o); o += 8 + 8; o += 2
        c, o = sz_or_ord(b, o); t, o = sz_or_ord(b, o)
        ln = struct.unpack_from('<H', b, o)[0]; o += 2 + ln
        nm = {0x80: 'Button', 0x81: 'Edit', 0x82: 'Static', 0x83: 'ListBox', 0x84: 'ScrollBar', 0x85: 'ComboBox'}.get(c, c)
        cls[nm] += 1
        styles[nm].add(st & 0xffff)
print(len([1 for p, _ in res if p[0] == 5]), 'dialogs')
for k, v in cls.most_common(): print(v, k, sorted(hex(s) for s in styles[k])[:20])
