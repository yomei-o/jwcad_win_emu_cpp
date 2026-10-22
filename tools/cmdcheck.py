# Runs Jw_cad commands one at a time in the emulator and records what each
# did: screenshots after each step, a contact sheet to look at, and anything
# that went wrong (a crash, an unimplemented import, an error message box).
#
#   python tools/cmdcheck.py               every test
#   python tools/cmdcheck.py line circle   just those
#   python tools/cmdcheck.py -l            list the tests
#
# Each test starts from the same state: a fresh copy of orig/ as C:\jww, an
# empty registry, and 木造平面例.jww opened from the command line.
# A message box counts as a failure unless the test has ('allow_msgbox',).  Results
# go to tmp/cmd/<test>/ and a summary to tmp/cmd/summary.txt.
#
# Steps are written in screen coordinates for the main window as a fresh
# start places it (20,20; the drawing's walls run from about (377,385) to
# (626,560)).
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'tmp', 'cmd')
EXE = os.path.join(ROOT, 'jwemu.exe')

# Toolbar buttons, by their label.
B = {
    '点': (46, 121), '接線': (46, 143), '接円': (46, 165), 'ハッチ': (46, 192), '建平': (46, 219), '建断': (46, 241),
    '建立': (46, 263), '多角形': (46, 290), '曲線': (46, 312), '包絡': (46, 348), '分割': (46, 370), '整理': (46, 392),
    '属変': (46, 414), '図形': (46, 575), '図登': (46, 597), '記変': (46, 619), '座標': (46, 641), '外変': (46, 667),
    '／': (85, 121), '□': (85, 143), '○': (85, 165), '文字': (85, 192), '寸法': (85, 214), '2線': (85, 241),
    '中心線': (85, 263), '連線': (85, 285), 'AUTO': (85, 312), '範囲': (85, 348), '複線': (85, 375),
    'コーナー': (85, 397), '伸縮': (85, 419), '面取': (85, 441), '消去': (85, 463), '複写': (85, 490),
    '移動': (85, 512), '戻る': (85, 539), '2.5D': (85, 620), '日影': (85, 642), '天空': (85, 664),
    '新規': (940, 121), '開く': (940, 143), '上書': (940, 165), '保存': (940, 187), '印刷': (940, 214),
    '切取': (940, 241), 'コピー': (940, 263), '貼付': (940, 285), '線属性': (940, 312), '寸化': (940, 348),
    '寸解': (940, 370), '選図': (940, 392),
    '属取': (981, 121), '線角': (981, 148), '鉛直': (981, 170), 'X軸': (981, 192), '2点角': (981, 214),
    '線長': (981, 241), '2点長': (981, 263), '間隔': (981, 285), '基設': (981, 312), '測定': (981, 348),
    '表計': (981, 370), '距離': (981, 392), '式計': (981, 419), 'パラメ': (981, 441),
}
# Menu bar titles.
M = {'ファイル': (66, 60), '編集': (140, 60), '表示': (203, 60), '作図': (267, 60), '設定': (330, 60),
     'その他': (395, 60), 'ヘルプ': (468, 60)}

# Points on the drawing: wall ends and an empty spot.
P = {
    'empty1': (200, 200), 'empty2': (320, 260), 'empty3': (260, 300),
    'wall_bl': (378, 558), 'wall_br': (625, 558), 'wall_bottom': (500, 558), 'wall_left': (378, 510),
    'wall_tl': (378, 460), 'room': (500, 510),
}


def pt(p):
    return P[p] if isinstance(p, str) else p


# A test is a list of steps:
#   ('btn', label)          click a toolbar button
#   ('menu', title)         open a menu
#   ('L', p) / ('R', p)     left / right click (p: a name from P or (x, y))
#   ('LL', p)               double click
#   ('drag', p, q, button)  press at p, move, release at q (button 0 left, 1 right)
#   ('key', vk) / ('text', s)
#   ('wait', ms)
#   ('shot', label)         a screenshot, as <test>/<n>_<label>.png
T = {
    # ---- drawing ----
    'point': [('btn', '点'), ('L', 'empty1'), ('L', 'empty2'), ('shot', 'done')],
    'line': [('btn', '／'), ('shot', 'mode'), ('L', 'empty1'), ('L', 'empty2'), ('R', 'wall_bl'), ('R', 'wall_tl'), ('shot', 'done')],
    'rect': [('btn', '□'), ('L', 'empty1'), ('L', 'empty2'), ('shot', 'done')],
    'circle': [('btn', '○'), ('L', 'empty3'), ('L', (300, 300)), ('shot', 'done')],
    'text': [('btn', '文字'), ('shot', 'mode'), ('text', 'ABC123'), ('L', 'empty1'), ('shot', 'done')],
    'text_typed': [('btn', '文字'), ('text', 'ABCあいう123'), ('shot', 'typed')],
    'text_font': [('btn', '文字'), ('shot', 'box'), ('L', (700, 154)), ('wait', 800), ('shot', 'font_list'), ('key', 27),
                  ('L', (95, 88)), ('wait', 1500), ('shot', 'dialog'), ('L', (547, 244)), ('wait', 800), ('shot', 'dialog_font_list')],
    'dimension': [('btn', '寸法'), ('shot', 'mode'), ('L', (500, 620)), ('R', 'wall_bl'), ('R', 'wall_br'), ('shot', 'done')],
    'dimension2': [('btn', '寸法'), ('L', (500, 620)), ('R', 'wall_bl'), ('shot', 'start'), ('R', (626, 557)), ('shot', 'r2'),
                   ('R', (624, 559)), ('shot', 'r3'), ('L', (700, 600)), ('shot', 'free')],
    'double_line': [('btn', '2線'), ('shot', 'mode'), ('L', 'wall_bottom'), ('L', (500, 600)), ('shot', 'done')],
    'center_line': [('btn', '中心線'), ('L', 'wall_left'), ('L', (625, 510)), ('shot', 'done')],
    'chain_line': [('btn', '連線'), ('L', 'empty1'), ('L', 'empty2'), ('L', 'empty3'), ('R', 'empty3'), ('shot', 'done')],
    'auto': [('btn', 'AUTO'), ('shot', 'mode'), ('L', 'empty1'), ('L', 'empty2'), ('shot', 'done')],
    'tangent': [('btn', '接線'), ('shot', 'mode')],
    'tangent_circle': [('btn', '接円'), ('shot', 'mode')],
    'hatch': [('btn', 'ハッチ'), ('shot', 'mode'), ('L', 'wall_bottom'), ('L', (625, 500)), ('L', (500, 460)), ('L', 'wall_left'),
              ('shot', 'picked')],
    'arch_plan': [('btn', '建平'), ('shot', 'mode')],
    'arch_section': [('btn', '建断'), ('shot', 'mode')],
    'arch_elevation': [('btn', '建立'), ('shot', 'mode')],
    'polygon': [('btn', '多角形'), ('shot', 'mode'), ('L', 'empty3'), ('shot', 'done')],
    'curve': [('btn', '曲線'), ('shot', 'mode')],
    # ---- editing ----
    'range_copy': [('btn', '範囲'), ('L', (360, 370)), ('L', (640, 575)), ('shot', 'selected'), ('btn', '複写'),
                   ('shot', 'copy_mode'), ('L', (250, 250)), ('shot', 'done')],
    'range_move': [('btn', '範囲'), ('L', (360, 370)), ('L', (640, 575)), ('btn', '移動'), ('L', (250, 250)), ('shot', 'done')],
    'offset': [('btn', '複線'), ('shot', 'mode'), ('L', 'wall_bottom'), ('L', (500, 600)), ('shot', 'done')],
    'corner': [('btn', 'コーナー'), ('L', 'wall_bottom'), ('L', 'wall_left'), ('shot', 'done')],
    'trim': [('btn', '伸縮'), ('shot', 'mode'), ('L', 'wall_bottom'), ('L', (700, 558)), ('shot', 'done')],
    'chamfer': [('btn', '面取'), ('shot', 'mode')],
    'erase_undo': [('btn', '消去'), ('R', 'wall_bottom'), ('shot', 'erased'), ('btn', '戻る'), ('shot', 'undone')],
    'envelope': [('btn', '包絡'), ('shot', 'mode')],
    'divide': [('btn', '分割'), ('shot', 'mode')],
    'tidy': [('btn', '整理'), ('shot', 'mode')],
    'attr_change': [('btn', '属変'), ('shot', 'mode')],
    'cut_paste': [('btn', '範囲'), ('L', (360, 370)), ('L', (640, 575)), ('btn', 'コピー'), ('btn', '貼付'), ('shot', 'paste_mode'),
                  ('L', (250, 250)), ('shot', 'done')],
    # ---- modes and dialogs ----
    'shape': [('btn', '図形'), ('wait', 2000), ('shot', 'open')],
    'shape_register': [('btn', '図登'), ('shot', 'mode')],
    'symbol_change': [('btn', '記変'), ('wait', 2000), ('shot', 'open')],
    'coordinates': [('btn', '座標'), ('wait', 1500), ('shot', 'open')],
    'external': [('btn', '外変'), ('wait', 2000), ('shot', 'open')],
    'view25d': [('btn', '2.5D'), ('wait', 2000), ('shot', 'open')],
    'shadow': [('btn', '日影'), ('wait', 1500), ('shot', 'open')],
    'sky': [('btn', '天空'), ('wait', 1500), ('shot', 'open')],
    'open_dlg': [('btn', '開く'), ('wait', 2500), ('shot', 'open')],
    'dxf_save': [('menu', 'ファイル'), ('L', (95, 255)), ('wait', 3000), ('shot', 'dlg')],
    'dxf_open': [('menu', 'ファイル'), ('L', (95, 233)), ('wait', 3000), ('shot', 'dlg')],
    'jwc_save': [('menu', 'ファイル'), ('L', (95, 202)), ('wait', 3000), ('shot', 'dlg')],
    'jwc_open': [('menu', 'ファイル'), ('L', (95, 180)), ('wait', 3000), ('shot', 'dlg')],
    'sfc_save': [('menu', 'ファイル'), ('L', (95, 308)), ('wait', 3000), ('shot', 'dlg')],
    'sfc_open': [('menu', 'ファイル'), ('L', (95, 286)), ('wait', 3000), ('shot', 'dlg')],
    'dxf_save2': [('menu', 'ファイル'), ('L', (95, 255)), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('shot', 'new'),
                  ('L', (295, 290)), ('wait', 5000), ('shot', 'saved')],
    'jww_saveas': [('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('shot', 'new'),
                   ('text', 'ABC'), ('L', (295, 290)), ('wait', 5000), ('shot', 'saved')],
    'save_jww': [('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('text', 'T_jww'), ('L', (562, 310)),
                 ('wait', 300), ('shot', 'dialog'), ('L', (295, 290)), ('wait', 6000), ('shot', 'saved')],
    'save_jwc': [('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('text', 'T_jwc'), ('L', (562, 331)),
                 ('wait', 300), ('shot', 'dialog'), ('L', (295, 290)), ('wait', 6000), ('shot', 'saved')],
    'save_dxf': [('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('text', 'T_dxf'), ('L', (562, 352)),
                 ('wait', 300), ('shot', 'dialog'), ('L', (295, 290)), ('wait', 6000), ('shot', 'saved')],
    'save_sfc': [('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('text', 'T_sfc'), ('L', (562, 372)),
                 ('wait', 300), ('shot', 'dialog'), ('L', (295, 290)), ('wait', 6000), ('shot', 'saved')],
    'save_p21': [('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('text', 'T_p21'), ('L', (562, 393)),
                 ('wait', 300), ('shot', 'dialog'), ('L', (295, 290)), ('wait', 6000), ('shot', 'saved')],
    'radio_try': [('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('L', (585, 352)), ('wait', 500), ('shot', 'label'),
                  ('L', (562, 372)), ('wait', 500), ('shot', 'circle')],
    'open_jwc': [('put', 'tests/io/T_jwc.jwc', 'T_jwc.jwc'), ('btn', '開く'), ('wait', 3000), ('L', (302, 131)), ('wait', 800),
                 ('L', (293, 161)), ('wait', 2500), ('shot', 'list'), ('LL', (410, 205)), ('wait', 8000), ('shot', 'opened')],
    'open_dxf': [('put', 'tests/io/T_dxf.dxf', 'T_dxf.dxf'), ('btn', '開く'), ('wait', 3000), ('L', (302, 131)), ('wait', 800),
                 ('L', (293, 175)), ('wait', 2500), ('shot', 'list'), ('LL', (410, 205)), ('wait', 8000), ('shot', 'opened')],
    'open_sfc': [('put', 'tests/io/T_sfc.sfc', 'T_sfc.sfc'), ('btn', '開く'), ('wait', 3000), ('L', (302, 131)), ('wait', 800),
                 ('L', (293, 189)), ('wait', 2500), ('shot', 'list'), ('LL', (410, 205)), ('wait', 8000), ('shot', 'opened')],
    'open_p21': [('put', 'tests/io/T_p21.p21', 'T_p21.p21'), ('btn', '開く'), ('wait', 3000), ('L', (302, 131)), ('wait', 800),
                 ('L', (293, 203)), ('wait', 2500), ('shot', 'list'), ('LL', (410, 205)), ('wait', 8000), ('shot', 'opened')],
    'open_dxf_menu': [('put', 'tests/io/T_dxf.dxf', 'T_dxf.dxf'), ('menu', 'ファイル'), ('L', (95, 233)), ('wait', 3000), ('shot', 'dlg'),
                      ('LL', (410, 205)), ('wait', 6000), ('shot', 'opened')],
    'open_sfc_menu': [('put', 'tests/io/T_sfc.sfc', 'T_sfc.sfc'), ('menu', 'ファイル'), ('L', (95, 286)), ('wait', 3000), ('shot', 'dlg'),
                      ('LL', (410, 205)), ('wait', 8000), ('shot', 'opened')],
    'open_jwc_menu': [('put', 'tests/io/T_jwc.jwc', 'T_jwc.jwc'), ('menu', 'ファイル'), ('L', (95, 180)), ('wait', 3000), ('shot', 'dlg'),
                      ('LL', (410, 205)), ('wait', 6000), ('shot', 'opened')],
    'dxf_ext_r12': [('put', 'tests/io/ext_r12.dxf', 'ext_r12.dxf'), ('menu', 'ファイル'), ('L', (95, 233)), ('wait', 3000),
                 ('LL', (410, 205)), ('wait', 6000), ('shot', 'opened')],
    'dxf_ext_r2000': [('put', 'tests/io/ext_r2000.dxf', 'ext_r2000.dxf'), ('menu', 'ファイル'), ('L', (95, 233)), ('wait', 3000),
                 ('LL', (410, 205)), ('wait', 6000), ('shot', 'opened')],
    'dxf_ext_r2007': [('put', 'tests/io/ext_r2007.dxf', 'ext_r2007.dxf'), ('menu', 'ファイル'), ('L', (95, 233)), ('wait', 3000),
                 ('LL', (410, 205)), ('wait', 6000), ('shot', 'opened')],
    'image_mode': [('menu', '編集'), ('L', (170, 414)), ('wait', 1500), ('shot', 'mode')],
    'image_insert_bmp': [('put', 'tests/io/pic.bmp', 'pic.bmp'), ('env', 'JWEMU_OPEN', r'C:\jww\pic.bmp'), ('menu', '編集'),
                         ('L', (170, 414)), ('wait', 1500), ('L', (68, 88)), ('wait', 2500), ('shot', 'chosen'),
                         ('L', (300, 250)), ('wait', 2000), ('shot', 'placed')],
    'image_embed': [('allow_msgbox',), ('put', 'tests/io/pic.bmp', 'pic.bmp'), ('env', 'JWEMU_OPEN', r'C:\jww\pic.bmp'), ('menu', '編集'),
                    ('L', (170, 414)), ('wait', 1500), ('L', (68, 88)), ('wait', 2500), ('L', (300, 250)), ('wait', 2000),
                    ('L', (577, 88)), ('wait', 2500), ('shot', 'embed'), ('key', 13), ('wait', 1500), ('shot', 'embed2'),
                    ('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('text', 'EMB'), ('L', (295, 290)),
                    ('wait', 5000), ('shot', 'saved')],
    'image_embedded_open': [('put', 'tests/io/embedded_bmp.jww', 'EMB.jww'), ('arg', 'EMB.jww'), ('wait', 2000), ('shot', 'opened')],
    'new': [('btn', '新規'), ('wait', 1500), ('shot', 'open')],
    'save_as': [('btn', '保存'), ('wait', 2000), ('shot', 'open')],
    'line_attr': [('btn', '線属性'), ('wait', 1500), ('shot', 'open')],
    'dim_make': [('btn', '寸化'), ('shot', 'mode')],
    'dim_break': [('btn', '寸解'), ('shot', 'mode')],
    'attr_pick': [('btn', '属取'), ('shot', 'mode'), ('L', 'wall_bottom'), ('shot', 'done')],
    'line_angle': [('btn', '線角'), ('shot', 'mode'), ('L', 'wall_bottom'), ('shot', 'done')],
    'vertical': [('btn', '鉛直'), ('shot', 'mode')],
    'x_axis': [('btn', 'X軸'), ('shot', 'mode')],
    'angle2': [('btn', '2点角'), ('shot', 'mode')],
    'line_length': [('btn', '線長'), ('shot', 'mode'), ('L', 'wall_bottom'), ('shot', 'done')],
    'length2': [('btn', '2点長'), ('shot', 'mode')],
    'spacing': [('btn', '間隔'), ('shot', 'mode')],
    'settings': [('btn', '基設'), ('wait', 2000), ('shot', 'open')],
    'measure': [('btn', '測定'), ('shot', 'mode'), ('R', 'wall_bl'), ('R', 'wall_br'), ('shot', 'done')],
    'table_calc': [('btn', '表計'), ('wait', 1500), ('shot', 'open')],
    'distance': [('btn', '距離'), ('shot', 'mode')],
    'formula': [('btn', '式計'), ('wait', 1500), ('shot', 'open')],
    'parametric': [('btn', 'パラメ'), ('shot', 'mode')],
    # ---- menus ----
    'menu_file': [('menu', 'ファイル'), ('shot', 'open')],
    'menu_edit': [('menu', '編集'), ('shot', 'open')],
    'menu_view': [('menu', '表示'), ('shot', 'open')],
    'menu_draw': [('menu', '作図'), ('shot', 'open')],
    'menu_settings': [('menu', '設定'), ('shot', 'open')],
    'menu_other': [('menu', 'その他'), ('shot', 'open')],
    'menu_help': [('menu', 'ヘルプ'), ('shot', 'open')],
    # ---- view ----
    'zoom_wheel': [('wheel', 'room', 120), ('wheel', 'room', 120), ('shot', 'in'), ('wheel', 'room', -120), ('shot', 'out')],
    'zoom_drag': [('drag', (380, 380), (630, 565), 2), ('shot', 'zoomed')],
}


def script_for(name, steps, outdir):
    lines = []
    t = 1500  # on the program's clock (see HeadlessHost), so the drawing is open by then
    n = 0

    def add(s, dt=150):
        nonlocal t
        lines.append(f'{t} {s}')
        t += dt

    def click(p, button=0, count=1):
        x, y = pt(p)
        add(f'move {x} {y}', 60)
        for _ in range(count):
            add(f'down {x} {y} {button}', 40)
            add(f'up {x} {y} {button}', 120)
        nonlocal t
        t += 350

    for st in steps:
        kind = st[0]
        if kind == 'btn':
            click(B[st[1]])
            t += 300
        elif kind == 'menu':
            click(M[st[1]])
            t += 500
        elif kind == 'L':
            click(st[1])
        elif kind == 'R':
            click(st[1], 1)
        elif kind == 'LL':
            click(st[1], 0, 2)
        elif kind == 'drag':
            (x0, y0), (x1, y1) = pt(st[1]), pt(st[2])
            b = st[3] if len(st) > 3 else 0
            buttons = [0, 1] if b == 2 else [b]  # 2: both buttons, Jw_cad's zoom
            add(f'move {x0} {y0}', 60)
            for bb in buttons:
                add(f'down {x0} {y0} {bb}', 30)
            for k in range(1, 6):
                add(f'move {x0 + (x1 - x0) * k // 5} {y0 + (y1 - y0) * k // 5}', 60)
            for bb in buttons:
                add(f'up {x1} {y1} {bb}', 30)
            t += 600
        elif kind == 'wheel':
            x, y = pt(st[1])
            add(f'move {x} {y}', 60)
            add(f'wheel {x} {y} {st[2]}', 500)
        elif kind == 'key':
            add(f'key {st[1]}', 200)
        elif kind == 'text':
            for ch in st[1]:
                add(f'char {ch}', 80)
            t += 300
        elif kind == 'wait':
            t += st[1]
        elif kind == 'shot':
            t += 700
            n += 1
            add(f'shot {os.path.join(outdir, f"{n}_{st[1]}.png")}', 100)
    add('dump', 100)
    return '\n'.join(lines) + '\n', t + 500


def run_test(name, drive):
    outdir = os.path.join(OUT, name)
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir)
    script, end = script_for(name, T[name], outdir)
    sp = os.path.join(outdir, 'script.txt')
    with open(sp, 'w', encoding='utf-8') as f:
        f.write(script)
    reg = os.path.join(outdir, 'reg.txt')
    env = dict(os.environ, JWEMU_REGISTRY=reg)
    # Each test gets its own C: so saves cannot leak into the next one.
    c = os.path.join(outdir, 'c')
    shutil.copytree(drive, c)
    # ('put', src, name): a file (path relative to the repo) copied into C:\jww first.
    # ('arg', name): open C:\jww\<name> at start instead of 木造平面例.jww.
    drawing = '木造平面例.jww'
    # ('env', name, value): an environment variable for the run (JWEMU_OPEN...).
    for st in T[name]:
        if st[0] == 'env':
            env[st[1]] = st[2]
    for st in T[name]:
        if st[0] == 'put':
            shutil.copy(os.path.join(ROOT, st[1]), os.path.join(c, 'jww', st[2]))
        elif st[0] == 'arg':
            drawing = st[1]
    cmd = [EXE, '--headless', '--drive-c', c, '--time', str(end), '--fonts', os.path.join(ROOT, 'fonts'),
           '--dlls', os.path.join(ROOT, 'dlls'), '--script', sp, '--shot', os.path.join(outdir, 'final.png'),
           'C:\\jww\\Jw_win.exe', 'C:\\jww\\' + drawing]
    # Below normal priority: several of these run at once (see JOBS).
    flags = 0x4000 if os.name == 'nt' else 0  # BELOW_NORMAL_PRIORITY_CLASS
    p = subprocess.run(cmd, cwd=os.path.join(c, 'jww'), env=env, capture_output=True, creationflags=flags)
    err = p.stderr.decode('utf-8', 'replace')
    with open(os.path.join(outdir, 'log.txt'), 'w', encoding='utf-8') as f:
        f.write(err)
    if not os.environ.get('KEEP_C'):
        shutil.rmtree(c, ignore_errors=True)
    problems = []
    if p.returncode != 0:
        problems.append(f'exit {p.returncode}')
    for line in err.splitlines():
        if line.startswith('jwemu:') or line.startswith('x86emu:') or 'unimplemented import' in line:
            problems.append(line.strip())
        elif line.startswith('[MessageBox]') and not any(st[0] == 'allow_msgbox' for st in T[name]):
            problems.append(line.strip())
    return name, problems


def sheet():
    import time
    from PIL import Image, ImageDraw
    # A new name each run: an image viewer that caches by path would show
    # the previous run's sheet.
    stamp = time.strftime('%H%M%S')
    for f in os.listdir(OUT):
        if f.startswith('sheet_'):
            os.remove(os.path.join(OUT, f))
    names = [n for n in T if os.path.isdir(os.path.join(OUT, n))]
    tiles = []
    for n in names:
        shots = sorted(f for f in os.listdir(os.path.join(OUT, n)) if f[0].isdigit() and f.endswith('.png'))
        for s in shots:
            tiles.append((f'{n}/{s[:-4]}', os.path.join(OUT, n, s)))
    per = 6
    for i in range(0, len(tiles), per):
        im = Image.new('RGB', (2 * 640, 3 * 370), (40, 40, 40))
        d = ImageDraw.Draw(im)
        for k, (label, path) in enumerate(tiles[i:i + per]):
            t = Image.open(path).convert('RGB').crop((20, 20, 1005, 710)).resize((640, 448 * 640 // 690))
            x, y = (k % 2) * 640, (k // 2) * 370
            im.paste(t.crop((0, 0, 640, 352)), (x, y + 18))
            d.text((x + 4, y + 2), label, fill=(255, 255, 0))
        im.save(os.path.join(OUT, f'sheet_{stamp}_{i // per + 1:02d}.png'))


def main():
    args = sys.argv[1:]
    if args and args[0] == '-l':
        print('\n'.join(T))
        return
    names = args or list(T)
    os.makedirs(OUT, exist_ok=True)
    # One per run, so that two runs at once do not pull it from under each other.
    drive = os.path.join(OUT, f'_drive_{os.getpid()}')
    shutil.rmtree(drive, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, 'orig'), os.path.join(drive, 'jww'))
    jobs = int(os.environ.get('JOBS', '4'))
    try:
        with ThreadPoolExecutor(jobs) as ex:
            results = list(ex.map(lambda n: run_test(n, drive), names))
    finally:
        shutil.rmtree(drive, ignore_errors=True)
    lines = []
    for name, problems in results:
        lines.append(f'{"ok " if not problems else "BAD"} {name}' + ''.join(f'\n      {p}' for p in problems))
    text = '\n'.join(lines)
    print(text)
    with open(os.path.join(OUT, 'summary.txt'), 'w', encoding='utf-8') as f:
        f.write(text + '\n')
    sheet()


if __name__ == '__main__':
    main()
