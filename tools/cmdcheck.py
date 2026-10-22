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
    '属変': (46, 414), 'BL化': (46, 441), 'BL解': (46, 463), '図形': (46, 575), '図登': (46, 597), '記変': (46, 619), '座標': (46, 641), '外変': (46, 667),
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
# Every sample drawing through ファイル一括変換 to one format.
ALL_SAMPLES = '"@2Dxf.jww" "Test1.jww" "Test2.jww" "Test3.jww" "Test4.jww" "Test5.jww" "Test6.jww" "Test7.jww" "サンプル.jww" "天空率表.jww" "敷地図.jww" "日影図.jww" "木造平面例.jww" "Ａマンション25d.jww" "Ａマンション平面例.jww" "Ａマンション立面例.jww"'
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
                    ('L', (577, 88)), ('wait', 2500), ('shot', 'embed'), ('key', 13), ('wait', 1500), ('shot', 'embed2'), ('key', 13), ('wait', 1000),
                    ('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('text', 'EMB'), ('L', (295, 290)),
                    ('wait', 5000), ('shot', 'saved')],
    'image_embedded_open': [('put', 'tests/io/embedded_bmp.jww', 'EMB.jww'), ('arg', 'EMB.jww'), ('wait', 2000), ('shot', 'opened')],
    'file_dialog': [('put', 'tests/io/pic.bmp', 'pic.bmp'), ('menu', '編集'), ('L', (170, 414)), ('wait', 1500),
                    ('L', (68, 88)), ('wait', 2500), ('shot', 'dialog'), ('LL', (440, 399)), ('wait', 2000),
                    ('L', (300, 250)), ('wait', 2000), ('shot', 'placed')],
    'dxf_save_dll': [('reg', r'Software\Jw_cad\jw_win\DXF', 'DxfOutUseDll', 1), ('menu', 'ファイル'), ('L', (95, 255)),
                     ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('text', 'DLL'), ('L', (295, 290)), ('wait', 8000),
                     ('shot', 'saved')],
    'dxf_open_dll': [('put', 'tests/io/T_dxf_dll.dxf', 'T_dxf_dll.dxf'), ('menu', 'ファイル'), ('L', (95, 233)), ('wait', 3000),
                     ('LL', (410, 205)), ('wait', 6000), ('shot', 'opened')],
    'menu_file_ops': [('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('shot', 'sub')],
    'menu_settings_open': [('menu', '設定'), ('wait', 500), ('shot', 'open')],
    'jwf_menu': [('menu', '設定'), ('L', (390, 114)), ('wait', 800), ('shot', 'sub')],
    'file_batch': [('allow_msgbox',), ('put', 'tests/io/T_jwc.jwc', 'A.jwc'), ('put', 'tests/io/T_jwc.jwc', 'B.jwc'), ('menu', 'ファイル'),
                   ('L', (95, 339)), ('wait', 800), ('L', (369, 427)), ('wait', 3000), ('shot', 'dlg'),
                   ('L', (688, 511)), ('text', '"A.jwc" "B.jwc"'), ('key', 13), ('wait', 3000), ('shot', 'next'),
                   ('L', (528, 417)), ('L', (637, 280)), ('wait', 8000), ('shot', 'done')],
    'jwf_write': [('menu', '設定'), ('L', (390, 114)), ('wait', 800), ('L', (557, 136)), ('wait', 2500), ('shot', 'dlg'),
                  ('text', 'TEST'), ('shot', 'typed'), ('key', 13), ('wait', 3000), ('shot', 'written')],
    'jwf_read': [('menu', '設定'), ('L', (390, 114)), ('wait', 800), ('L', (557, 114)), ('wait', 2500), ('shot', 'dlg'),
                 ('text', '尺単位.jwf'), ('key', 13), ('wait', 3000), ('shot', 'read')],
    'text_file_read': [('put', 'tests/io/memo.txt', 'memo.txt'), ('btn', '文字'), ('wait', 800), ('L', (719, 88)), ('wait', 2500),
                       ('shot', 'dlg'), ('text', 'memo.txt'), ('key', 13), ('wait', 2500), ('shot', 'chosen'),
                       ('L', (200, 250)), ('wait', 2000), ('shot', 'placed')],
    'batch_all_jwc': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 427)), ('wait', 3000),
                      ('L', (688, 511)), ('text', ALL_SAMPLES), ('key', 13), ('wait', 3000), ('L', (528, 393)),
                      ('L', (637, 280)), ('wait', 120000), ('shot', 'done')],
    'batch_all_dxf': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 427)), ('wait', 3000),
                      ('L', (688, 511)), ('text', ALL_SAMPLES), ('key', 13), ('wait', 3000), ('L', (528, 417)),
                      ('L', (637, 280)), ('wait', 120000), ('shot', 'done')],
    'batch_all_sfc': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 427)), ('wait', 3000),
                      ('L', (688, 511)), ('text', ALL_SAMPLES), ('key', 13), ('wait', 3000), ('L', (528, 441)),
                      ('L', (637, 280)), ('wait', 120000), ('shot', 'done')],
    'batch_all_p21': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 427)), ('wait', 3000),
                      ('L', (688, 511)), ('text', ALL_SAMPLES), ('key', 13), ('wait', 3000), ('L', (528, 465)),
                      ('L', (637, 280)), ('wait', 120000), ('shot', 'done')],
    'open_sfc_japanese': [('put', 'tests/io/T_sfc.sfc', '日本語の図面.sfc'), ('arg', '日本語の図面.sfc'), ('wait', 4000), ('shot', 'opened')],
    'open_p21_japanese': [('put', 'tests/io/T_p21.p21', '日本語の図面.p21'), ('arg', '日本語の図面.p21'), ('wait', 6000), ('shot', 'opened')],
    'save_old_version': [('allow_msgbox',), ('btn', '保存'), ('wait', 3000), ('L', (412, 131)), ('wait', 1500), ('text', 'OLD'),
                         ('L', (655, 290)), ('wait', 300), ('L', (667, 330)), ('wait', 300), ('shot', 'dialog'),
                         ('L', (295, 290)), ('wait', 2000), ('shot', 'confirm'), ('key', 13), ('wait', 4000), ('shot', 'saved')],
    'open_old_version': [('put', 'tests/io/v420.jww', 'v420.jww'), ('arg', 'v420.jww'), ('wait', 2000), ('shot', 'opened')],
    'fileop_compare': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 339)), ('wait', 3000), ('shot', 'dlg')],
    'fileop_rename': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 361)), ('wait', 3000), ('shot', 'dlg'),
                      ('L', (340, 348)), ('wait', 500), ('L', (434, 131)), ('wait', 1500), ('shot', 'ask'),
                      ('L', (560, 373))] + [('key', 8)] * 12 + [('text', '名前変更済.jww'), ('shot', 'typed'), ('key', 13),
                      ('wait', 2000), ('shot', 'renamed')],
    'fileop_delete': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 383)), ('wait', 3000), ('shot', 'dlg'),
                      ('L', (340, 348)), ('wait', 500), ('L', (408, 131)), ('wait', 1500), ('shot', 'ask'), ('key', 13), ('wait', 2000),
                      ('shot', 'deleted')],
    'fileop_attr': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 405)), ('wait', 3000), ('shot', 'dlg')],
    'fileop_send': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 458)), ('wait', 3000), ('shot', 'dlg')],
    'fileop_info_copy': [('allow_msgbox',), ('menu', 'ファイル'), ('L', (95, 339)), ('wait', 800), ('L', (369, 480)), ('wait', 3000), ('shot', 'dlg')],
    'shape_place': [('btn', '図形'), ('wait', 2000), ('LL', (735, 550)), ('wait', 1500), ('shot', 'picked'),
                    ('L', (200, 300)), ('wait', 1500), ('shot', 'placed')],
    'shape_register_save': [('btn', '図登'), ('wait', 800), ('L', (360, 370)), ('wait', 300), ('R', (640, 575)), ('wait', 1500),
                            ('shot', 'selected'), ('L', (562, 88)), ('wait', 3000), ('shot', 'mode2'),
                            ('L', (589, 88)), ('wait', 3000), ('shot', 'dlg'), ('L', (412, 131)), ('wait', 1500),
                            ('text', '木造住宅'), ('shot', 'name'), ('L', (295, 290)), ('wait', 3000), ('shot', 'saved')],
    'dxf_ext_misc': [('put', 'tests/io/ext_misc.dxf', 'ext_misc.dxf'), ('arg', 'ext_misc.dxf'), ('wait', 3000), ('shot', 'opened')],
    'text_rotated': [('btn', '文字'), ('wait', 800), ('L', (340, 88)), ('text', '30'), ('key', 9), ('wait', 300),
                     ('L', (300, 154)), ('text', 'ABC回転テキスト'), ('L', (300, 400)), ('wait', 1500), ('shot', 'placed')],
    'dxf_ext_ellipse': [('put', 'tests/io/ext_ellipse.dxf', 'ext_ellipse.dxf'), ('arg', 'ext_ellipse.dxf'), ('wait', 3000), ('shot', 'opened')],
    'dxf_resave_japanese': [('put', 'tests/io/ext_r2007.dxf', 'ext_r2007.dxf'), ('arg', 'ext_r2007.dxf'), ('wait', 2000),
                            ('menu', 'ファイル'), ('L', (95, 255)), ('wait', 3000), ('L', (412, 131)), ('wait', 1500),
                            ('text', '再保存'), ('L', (295, 290)), ('wait', 4000), ('shot', 'saved')],
    # ---- drawing, checked by what the saved DXF holds ----
    'dxf_baseline': [('dxf', 'BASE')],
    'd_line': [('btn', '／'), ('L', 'empty1'), ('L', 'empty2'), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'LINE': 1})],
    'd_rect': [('btn', '□'), ('L', 'empty1'), ('L', 'empty2'), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'LINE': 4})],
    'd_circle': [('btn', '○'), ('L', 'empty3'), ('L', (300, 300)), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'CIRCLE': 1})],
    'd_point': [('btn', '点'), ('L', 'empty1'), ('L', 'empty2'), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'POINT': 2})],
    'd_text': [('btn', '文字'), ('text', 'ABC123'), ('L', 'empty1'), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'TEXT': 1})],
    'd_erase': [('btn', '消去'), ('L', 'wall_bottom'), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'LINE': -1})],
    'd_undo': [('btn', '／'), ('L', 'empty1'), ('L', 'empty2'), ('btn', '戻る'), ('wait', 500), ('shot', 'drawn'),
               ('dxf', 'OUT'), ('expect', {'LINE': 0})],
    'd_double_line': [('btn', '2線'), ('L', 'wall_bottom'), ('L', (420, 620)), ('L', (600, 620)), ('shot', 'drawn'),
                      ('dxf', 'OUT'), ('expect', {'LINE': 2})],
    'd_center_line': [('btn', '中心線'), ('L', 'wall_left'), ('L', (625, 510)), ('L', (500, 300)), ('L', (500, 640)),
                      ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'LINE': 1})],
    'd_chain_line': [('btn', '連線'), ('L', 'empty1'), ('L', 'empty2'), ('L', 'empty3'), ('shot', 'drawn'),
                     ('dxf', 'OUT'), ('expect', {'LINE': 2})],
    # 寸法: 引出線の始点, 寸法線の位置, then the two ends.
    'd_dimension': [('btn', '寸法'), ('L', (500, 650)), ('L', (500, 610)), ('L', (380, 640)), ('L', (620, 640)),
                    ('shot', 'drawn'),
                    ('dxf', 'OUT'), ('expect_gt', {'LINE': 0}), ('expect', {'TEXT': 1})],
    # 複線: (L) on the line asks for the spacing afterwards; (R) uses the value
    # in the box (前回値), which is what was typed.
    'd_offset': [('btn', '複線'), ('text', '1000'), ('key', 13), ('R', 'wall_bottom'), ('shot', 'picked'),
                 ('L', (500, 640)), ('shot', 'drawn'),
                 ('dxf', 'OUT'), ('expect', {'LINE': 1})],
    'd_polygon': [('btn', '多角形'), ('L', 'empty2'), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'LINE': 5})],
    'd_copy': [('btn', '範囲'), ('L', (360, 370)), ('R', (640, 575)), ('wait', 800), ('btn', '複写'), ('wait', 800),
               ('L', (250, 250)), ('wait', 1500), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect_gt', {'LINE': 100})],
    'd_move': [('btn', '範囲'), ('L', (360, 370)), ('R', (640, 575)), ('wait', 800), ('btn', '移動'), ('wait', 800),
               ('L', (250, 250)), ('wait', 1500), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'LINE': 0}),
               ('expect_diff',)],
    'd_trim': [('btn', '伸縮'), ('L', (600, 558)), ('L', (700, 558)), ('wait', 800), ('shot', 'drawn'), ('dxf', 'OUT'),
               ('expect_diff',)],
    'd_corner': [('btn', '／'), ('L', (150, 200)), ('L', (300, 200)), ('L', (350, 150)), ('L', (350, 300)),
                 ('btn', 'コーナー'), ('L', (200, 200)), ('L', (350, 250)), ('wait', 800), ('shot', 'drawn'),
                 ('dxf', 'OUT'), ('expect', {'LINE': 2}), ('expect_diff',)],
    # Two lines meeting at a corner in the empty area, for 面取/コーナー-like commands.
    'd_chamfer': [('btn', '／'), ('L', (150, 200)), ('L', (350, 200)), ('L', (350, 200)), ('L', (350, 400)),
                  ('btn', '面取'), ('L', (250, 200)), ('L', (350, 300)), ('wait', 800), ('shot', 'drawn'),
                  ('dxf', 'OUT'), ('expect', {'LINE': 3})],
    'd_divide': [('btn', '／'), ('L', (150, 200)), ('L', (450, 200)), ('btn', '分割'), ('L', (300, 200)), ('L', (300, 200)),
                 ('wait', 800), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect_diff',)],
    # 接線, 点→円: a point, then the circle.
    'd_tangent_circle': [('btn', '○'), ('L', (250, 250)), ('L', (300, 250)), ('btn', '接線'), ('L', (130, 88)),
                         ('L', (500, 150)), ('L', (300, 250)), ('wait', 800), ('shot', 'drawn'), ('dxf', 'OUT'),
                         ('expect', {'CIRCLE': 1}), ('expect_gt', {'LINE': 0})],
    # 消去: (L) on a line is 部分消し (then its two ends), (R) erases it whole.
    'd_partial_erase': [('btn', '／'), ('L', (150, 200)), ('L', (450, 200)), ('btn', '消去'), ('L', (300, 200)),
                        ('L', (200, 200)), ('L', (400, 200)), ('wait', 800), ('shot', 'drawn'),
                        ('dxf', 'OUT'), ('expect', {'LINE': 2})],
    # ハッチ: the lines of the outline in turn, the first one again to close it, then 実行.
    'd_hatch': [('btn', '□'), ('L', (150, 150)), ('L', (350, 300)), ('btn', 'ハッチ'), ('L', (150, 200)), ('L', (250, 150)),
                ('L', (350, 250)), ('L', (250, 300)), ('L', (150, 200)), ('wait', 500), ('shot', 'picked'),
                ('L', (52, 88)), ('wait', 1500), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect_gt', {'LINE': 4})],
    'd_arc': [('btn', '○'), ('L', (45, 88)), ('L', (300, 300)), ('L', (400, 300)), ('L', (300, 200)), ('wait', 500),
              ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'ARC': 1})],
    'd_range_erase': [('btn', '範囲'), ('L', (360, 370)), ('R', (640, 575)), ('wait', 800), ('btn', '消去'), ('wait', 1500),
                      ('shot', 'drawn'), ('dxf', 'OUT'), ('expect_lt', {'LINE': -100})],
    'd_text_move': [('btn', '文字'), ('L', (418, 507)), ('wait', 500), ('L', (200, 250)), ('wait', 800), ('shot', 'drawn'),
                    ('dxf', 'OUT'), ('expect', {'TEXT': 0}), ('expect_diff',)],
    'd_envelope': [('btn', '□'), ('L', (150, 150)), ('L', (300, 300)), ('L', (250, 250)), ('L', (400, 400)), ('btn', '包絡'),
                   ('L', (130, 130)), ('L', (420, 420)), ('wait', 1000), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect_diff',)],
    'd_block': [('btn', '範囲'), ('L', (360, 370)), ('R', (640, 575)), ('wait', 800), ('btn', 'BL化'), ('wait', 1500),
                ('text', 'HOUSE'), ('key', 13), ('wait', 1500), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'INSERT': 1}),
                ('expect_lt', {'LINE': -100})],
    # 属変: (L) on a line moves it to the layer being written (書込みレイヤに変更 is on).
    'd_attr_change': [('btn', '属変'), ('L', 'wall_bottom'), ('wait', 1000), ('shot', 'drawn'), ('dxf', 'OUT'),
                      ('expect', {'LINE': 0}), ('expect_diff',)],
    # 線属性: 線色5 and 点線1, then a line.
    'd_line_attr': [('btn', '線属性'), ('wait', 1500), ('L', (398, 319)), ('L', (540, 265)), ('L', (512, 469)), ('wait', 800),
                    ('btn', '／'), ('L', 'empty1'), ('L', 'empty2'), ('shot', 'drawn'), ('dxf', 'OUT'),
                    ('expect', {'LINE': 1, 'LINE/ltDASHED1': 1})],
    # Layer 1 as the layer written to ((R) on its button; (L) changes how it shows), then a line.
    'd_layer': [('R', (931, 496)), ('wait', 500), ('btn', '／'), ('L', 'empty1'), ('L', 'empty2'), ('shot', 'drawn'),
                ('dxf', 'OUT'), ('expect', {'LINE': 1, 'LINE/L_0-1_': 1})],
    'd_copy_paste': [('btn', '範囲'), ('L', (360, 370)), ('R', (640, 575)), ('wait', 800), ('btn', 'コピー'), ('wait', 1000),
                     ('btn', '貼付'), ('wait', 1000), ('L', (250, 250)), ('wait', 1500), ('shot', 'drawn'), ('dxf', 'OUT'),
                     ('expect_gt', {'LINE': 100})],
    'd_block_release': [('btn', '範囲'), ('L', (360, 370)), ('R', (640, 575)), ('wait', 800), ('btn', 'BL化'), ('wait', 1500),
                        ('text', 'HOUSE'), ('key', 13), ('wait', 1500), ('btn', '範囲'), ('L', (360, 370)), ('R', (640, 575)), ('wait', 800),
                        ('btn', 'BL解'), ('wait', 1500),
                        ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'INSERT': 0, 'LINE': 0})],
    # 接円: three lines (the third comes out vertical: 水平・垂直 is on), then the circle touching all three.
    'd_tangent_circle3': [('btn', '／'), ('L', (150, 200)), ('L', (400, 200)), ('L', (150, 200)), ('L', (150, 450)),
                          ('L', (400, 200)), ('L', (150, 450)), ('btn', '接円'), ('L', (300, 200)), ('L', (150, 350)),
                          ('L', (400, 300)), ('wait', 800), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect', {'CIRCLE': 1})],
    # 曲線 (スプライン): the points it passes through, then 作図実行.  (連結線指定 is for
    # carrying on from an existing line, not for turning a polyline into a curve.)
    'd_curve': [('btn', '曲線'), ('L', (150, 200)), ('L', (250, 300)), ('L', (350, 200)), ('L', (450, 300)), ('wait', 500),
                ('shot', 'picked'), ('L', (555, 88)), ('wait', 1000), ('shot', 'drawn'), ('dxf', 'OUT'), ('expect_gt', {'LINE': 10})],
    'd_auto': [('btn', 'AUTO'), ('L', 'empty1'), ('L', 'empty2'), ('wait', 500), ('shot', 'drawn'), ('dxf', 'OUT'),
               ('expect_diff',)],
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


# ('dxf', name): ファイル → DXF形式で保存 → 新規 → name → OK, so that what the
# test drew can be counted.  Expanded into ordinary steps here.
def expand(steps):
    out = []
    for st in steps:
        if st[0] == 'dxf':
            # (No ESC first: in Jw_cad ESC is 戻る and would undo what was just drawn.)
            out += [('wait', 300), ('menu', 'ファイル'), ('L', (95, 255)), ('wait', 3000),
                    ('L', (412, 131)), ('wait', 1500), ('text', st[1]), ('L', (295, 290)), ('wait', 5000)]
        else:
            out.append(st)
    return out


# Entities in a DXF's ENTITIES section: by type ("LINE"), and also by type and
# colour ("LINE/c5"), line type ("LINE/ltDOT") and layer ("LINE/L0-1"), so a
# test can check what it drew as well as how many.
def dxf_counts(path):
    import collections
    lines = open(path, 'rb').read().decode('cp932', 'replace').splitlines()
    pairs = [(c.strip(), v.strip()) for c, v in zip(lines[0::2], lines[1::2])]
    counts = collections.Counter()
    in_entities = False
    prev = None
    ent = None

    def close():
        if ent:
            t = ent['type']
            counts[t] += 1
            if '62' in ent: counts[f'{t}/c{ent["62"]}'] += 1
            if '6' in ent: counts[f'{t}/lt{ent["6"]}'] += 1
            if '8' in ent: counts[f'{t}/L{ent["8"]}'] += 1

    for code, value in pairs:
        if code == '2' and prev == 'SECTION':
            in_entities = value == 'ENTITIES'
        if code == '0':
            close()
            ent = None
            if in_entities and value not in ('SECTION', 'ENDSEC', 'EOF', 'SEQEND', 'VERTEX'):
                ent = {'type': value}
            prev = value
        elif ent is not None and code in ('62', '6', '8') and code not in ent:
            ent[code] = value
    close()
    return dict(counts)


BASELINE = os.path.join(OUT, '_baseline_counts.txt')


def baseline():
    with open(BASELINE, encoding='utf-8') as f:
        return eval(f.read())


def script_for(name, steps, outdir):
    lines = []
    t = 1500  # on the program's clock (see HeadlessHost), so the drawing is open by then
    n = 0

    def add(s, dt=150):
        nonlocal t
        lines.append(f'{t} {s}')
        t += dt

    last = [None]

    def click(p, button=0, count=1):
        x, y = pt(p)
        # Get there the way a hand does, in several moves: some of Jw_cad's
        # steps (2線's side, 中心線's direction) wait for the mouse to move
        # after a click, and one jump straight onto the next click is not that.
        if last[0]:
            x0, y0 = last[0]
            for k in range(1, 5):
                add(f'move {x0 + (x - x0) * k // 5} {y0 + (y - y0) * k // 5}', 30)
        add(f'move {x} {y}', 60)
        last[0] = (x, y)
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
    script, end = script_for(name, expand(T[name]), outdir)
    sp = os.path.join(outdir, 'script.txt')
    with open(sp, 'w', encoding='utf-8') as f:
        f.write(script)
    reg = os.path.join(outdir, 'reg.txt')
    env = dict(os.environ, JWEMU_REGISTRY=reg)
    # ('reg', key under HKCU, value name, dword): a setting in place before start.
    seeds = [st for st in T[name] if st[0] == 'reg']
    if seeds:
        with open(reg, 'w', encoding='utf-8', newline='\n') as f:
            f.write('jwemu-registry 1\n')
            for _, key, value, dword in seeds:
                f.write(f'K 1 {key}\n')
                f.write(f'V 4 {value.encode("utf-8").hex()} {int(dword).to_bytes(4, "little").hex()}\n')
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
    # ('dxf', name) then ('expect', {type: change}) / ('expect_diff',): what the
    # saved drawing holds against the baseline (the same drawing saved untouched).
    checks = []
    for st in T[name]:
        if st[0] != 'dxf':
            continue
        saved = os.path.join(c, 'jww', st[1] + '.dxf')
        if not os.path.exists(saved):
            checks.append(f'no {st[1]}.dxf was saved')
            continue
        shutil.copy(saved, os.path.join(outdir, st[1] + '.dxf'))
        counts = dxf_counts(saved)
        with open(os.path.join(outdir, 'counts.txt'), 'w', encoding='utf-8') as f:
            f.write(repr(counts))
        if name == 'dxf_baseline':
            with open(BASELINE, 'w', encoding='utf-8') as f:
                f.write(repr(counts))
            continue
        base = baseline()
        delta = {k: counts.get(k, 0) - base.get(k, 0) for k in set(counts) | set(base)}
        delta = {k: v for k, v in delta.items() if v}
        for e in T[name]:
            if e[0] == 'expect':
                for k, v in e[1].items():
                    if delta.get(k, 0) != v:
                        checks.append(f'{k}: expected {v:+d}, got {delta.get(k, 0):+d} (all changes: {delta})')
            elif e[0] == 'expect_gt':
                for k, v in e[1].items():
                    if not delta.get(k, 0) > v:
                        checks.append(f'{k}: expected more than {v:+d}, got {delta.get(k, 0):+d} (all changes: {delta})')
            elif e[0] == 'expect_lt':
                for k, v in e[1].items():
                    if not delta.get(k, 0) < v:
                        checks.append(f'{k}: expected less than {v:+d}, got {delta.get(k, 0):+d} (all changes: {delta})')
            elif e[0] == 'expect_diff':
                body = lambda p: open(p, 'rb').read().split(b'ENTITIES', 1)[-1]
                if body(saved) == body(os.path.join(OUT, 'dxf_baseline', 'BASE.dxf')):
                    checks.append('the drawing did not change')
    if not os.environ.get('KEEP_C'):
        shutil.rmtree(c, ignore_errors=True)
    problems = list(checks)
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
    if any(st[0] == 'dxf' for n in names for st in T[n]) and 'dxf_baseline' not in names:
        print(*run_test('dxf_baseline', drive))
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
