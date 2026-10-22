# Runs tools/cmdcheck.py's tests against the real Jw_win.exe (Windows only)
# and puts each real screenshot next to the emulator's, for comparison.
#
#   python tools/cmdcheck.py            # first: the emulator side
#   python tools/realcheck.py [tests]   # then: the real side, and the pairs
#
# The real program keeps its settings in HKCU\Software\Jw_cad.  They are
# exported first and imported back at the end; in between each test starts
# with none, as the emulator's tests do, except Direct2D off (the view must
# draw with GDI to be captured, and the emulator has no Direct2D either).
# The pairs go to tmp/cmd/<test>/pair_<shot>.png: emulator above, real below.
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'tmp', 'cmd')
WORK = os.path.join(ROOT, 'tmp', 'realrun')
KEY = r'HKCU\Software\Jw_cad'


def reg(*args):
    return subprocess.run(['reg', *args], capture_output=True)


def run_real(name):
    outdir = os.path.join(WORK, name)
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir)
    # A folder per test: the previous run's process may not have let go of
    # its files yet.
    drive = os.path.join(outdir, 'jww')
    shutil.copytree(os.path.join(ROOT, 'orig'), drive)
    reg('delete', KEY, '/f')
    reg('add', KEY + r'\jw_win\View', '/v', 'Direct2d', '/t', 'REG_DWORD', '/d', '0', '/f')
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    os.path.join(ROOT, 'tools', 'realrun.ps1'), '-Exe', os.path.join(drive, 'Jw_win.exe'),
                    '-Script', os.path.join(OUT, name, 'script.txt'), '-Out', outdir,
                    '-Arg', os.path.join(drive, '木造平面例.jww')], capture_output=True, timeout=300)
    shutil.rmtree(drive, ignore_errors=True)


def pairs(name):
    from PIL import Image
    emu_dir, real_dir = os.path.join(OUT, name), os.path.join(WORK, name)
    for f in sorted(os.listdir(emu_dir)):
        if not (f[0].isdigit() and f.endswith('.png')) or not os.path.exists(os.path.join(real_dir, f)):
            continue
        a = Image.open(os.path.join(emu_dir, f)).convert('RGB').crop((20, 20, 1005, 710))
        b = Image.open(os.path.join(real_dir, f)).convert('RGB').crop((20, 20, 1005, 710))
        im = Image.new('RGB', (985, 690 * 2 + 4), (255, 0, 0))
        im.paste(a, (0, 0))
        im.paste(b, (0, 694))
        im.save(os.path.join(emu_dir, 'pair_' + f))


def main():
    sys.path.insert(0, os.path.dirname(__file__))
    import cmdcheck
    names = sys.argv[1:] or [n for n in cmdcheck.T if os.path.exists(os.path.join(OUT, n, 'script.txt'))]
    os.makedirs(WORK, exist_ok=True)
    backup = os.path.join(WORK, 'jwcad_backup.reg')
    have_backup = reg('export', KEY, backup, '/y').returncode == 0
    try:
        for n in names:
            print('real:', n, flush=True)
            try:
                run_real(n)
                pairs(n)
            except Exception as ex:  # one test failing must not stop the restore
                print('  failed:', ex, flush=True)
    finally:
        reg('delete', KEY, '/f')
        if have_backup:
            reg('import', backup)
        print('settings restored' if have_backup else 'no settings to restore')


if __name__ == '__main__':
    main()
