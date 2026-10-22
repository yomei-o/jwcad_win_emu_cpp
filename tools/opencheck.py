# Opens drawings one by one in the emulator and reports what went wrong:
# a crash, an emulator exception, an unimplemented import that was called, or
# a message box (Jw_cad's own error messages come that way).
#
#   python tools/opencheck.py FILE...      any of .jww .jwc .dxf .sfc .p21
#
# Each file gets a fresh copy of orig/ as C:\jww and an empty registry, is
# copied in beside the samples and named on the command line, and is given a
# few seconds of the program's time.  Results: tmp/open/<n>_<name>/ (log.txt,
# shot.png), a summary on stdout, and tmp/open/sheet.png with every screen.
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'tmp', 'open')
EXE = os.path.join(ROOT, 'jwemu.exe')
# OPEN_TIME: program milliseconds before the check (a big SXF file takes a
# while); OPEN_WALL: seconds of real time before giving up.
TIME = int(os.environ.get('OPEN_TIME', '6000'))
WALL = int(os.environ.get('OPEN_WALL', '600'))


def run(i, path, drive):
    name = os.path.basename(path)
    outdir = os.path.join(OUT, f'{i:03d}_{name}')
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir)
    c = os.path.join(outdir, 'c')
    shutil.copytree(drive, c)
    shutil.copy(path, os.path.join(c, 'jww', name))
    script = os.path.join(outdir, 'script.txt')
    with open(script, 'w', encoding='utf-8') as f:
        f.write('6000 dump\n')
    cmd = [EXE, '--headless', '--drive-c', c, '--time', str(TIME + 500), '--fonts', os.path.join(ROOT, 'fonts'),
           '--dlls', os.path.join(ROOT, 'dlls'), '--script', script, '--shot', os.path.join(outdir, 'shot.png'),
           'C:\\jww\\Jw_win.exe', 'C:\\jww\\' + name]
    env = dict(os.environ, JWEMU_REGISTRY=os.path.join(outdir, 'reg.txt'))
    flags = 0x4000 if os.name == 'nt' else 0  # BELOW_NORMAL_PRIORITY_CLASS
    try:
        p = subprocess.run(cmd, cwd=os.path.join(c, 'jww'), env=env, capture_output=True, creationflags=flags,
                           timeout=WALL)
        err, code = p.stderr.decode('utf-8', 'replace'), p.returncode
    except subprocess.TimeoutExpired:
        err, code = '', 'timeout'
    with open(os.path.join(outdir, 'log.txt'), 'w', encoding='utf-8') as f:
        f.write(err)
    shutil.rmtree(c, ignore_errors=True)
    problems = [] if code == 0 else [f'exit {code}']
    for line in err.splitlines():
        if line.startswith(('jwemu:', 'x86emu:', '[MessageBox]')) or 'unimplemented import' in line:
            problems.append(line.strip())
    # The title bar names the drawing once it is open.
    opened = any(name in line and 'jw_win' in line for line in err.splitlines())
    if not opened:
        problems.append('the title does not name the file (not opened?)')
    return name, outdir, problems


def main():
    files = [os.path.abspath(f) for f in sys.argv[1:]]
    if not files:
        print(__doc__ or 'usage: opencheck.py FILE...')
        return
    os.makedirs(OUT, exist_ok=True)
    drive = os.path.join(OUT, f'_drive_{os.getpid()}')
    shutil.rmtree(drive, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, 'orig'), os.path.join(drive, 'jww'))
    try:
        with ThreadPoolExecutor(int(os.environ.get('JOBS', '4'))) as ex:
            results = list(ex.map(lambda a: run(a[0], a[1], drive), enumerate(files)))
    finally:
        shutil.rmtree(drive, ignore_errors=True)
    bad = 0
    for name, _, problems in results:
        print(('ok  ' if not problems else 'BAD ') + name + ''.join('\n      ' + p for p in problems[:6]))
        bad += bool(problems)
    print(f'{len(results) - bad} ok, {bad} with problems')
    try:
        from PIL import Image, ImageDraw
        cols, tw, th = 4, 320, 225
        rows = (len(results) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * tw, rows * (th + 16)), (40, 40, 40))
        d = ImageDraw.Draw(sheet)
        for k, (name, outdir, _) in enumerate(results):
            shot = os.path.join(outdir, 'shot.png')
            x, y = (k % cols) * tw, (k // cols) * (th + 16)
            if os.path.exists(shot):
                sheet.paste(Image.open(shot).convert('RGB').crop((20, 20, 1005, 710)).resize((tw, th)), (x, y + 16))
            d.text((x + 4, y + 2), name.encode('ascii', 'replace').decode(), fill=(255, 255, 0))
        sheet.save(os.path.join(OUT, 'sheet.png'))
    except ImportError:
        pass


if __name__ == '__main__':
    main()
