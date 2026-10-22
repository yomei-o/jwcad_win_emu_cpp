# Replays a tools/cmdcheck.py script against the real Jw_win.exe on Windows,
# so the emulator's screenshots have something to be compared with.
#
#   powershell -File tools/realrun.ps1 -Exe C:\...\jww\Jw_win.exe -Script script.txt -Out dir [-Arg file]
#
# Input goes in as window messages (PostMessage), so the mouse is left alone,
# and the window sits at the bottom of the z-order (on the screen: a window
# off it is never painted, and Jw_cad's view does not answer WM_PRINT).  Screenshots composite PrintWindow
# captures of every window of the process onto a 1280x800 picture with the
# main window at (20, 20) - where the emulator puts it - so the two line up.
# The association question Jw_cad asks at start is always answered キャンセル.
param([string]$Exe, [string]$Script, [string]$Out, [string]$Arg = "", [int]$X0 = 20, [int]$Y0 = 20)
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing @"
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Runtime.InteropServices;
public static class R {
  public struct RECT { public int L, T, R, B; }
  public struct POINT { public int X, Y; }
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, System.Text.StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
  public static string Text(IntPtr h) { var sb = new System.Text.StringBuilder(256); GetWindowText(h, sb, 256); return sb.ToString(); }
  // Every top-level window of the process, shown or not.
  public static List<IntPtr> AllTops(uint pid) {
    var list = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (p == pid) list.Add(h); return true; }, IntPtr.Zero);
    return list;
  }
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowEx(IntPtr parent, IntPtr after, string cls, string title);
  // The first Edit control anywhere under a window.
  public static IntPtr FindEdit(IntPtr h) {
    IntPtr c = IntPtr.Zero;
    while ((c = FindWindowEx(h, c, null, null)) != IntPtr.Zero) {
      if (Cls(c) == "Edit" && IsWindowVisible(c)) return c;
      IntPtr d = FindEdit(c);
      if (d != IntPtr.Zero) return d;
    }
    return IntPtr.Zero;
  }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr h);
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int s);
  // The window tree with screen rectangles, client areas and styles, for the
  // script's "dump" (same layout as the emulator's).
  public static string Tree(IntPtr h, int depth) {
    var sb = new System.Text.StringBuilder();
    RECT r; GetWindowRect(h, out r);
    RECT c; GetClientRect(h, out c); POINT p = new POINT(); ClientToScreen(h, ref p);
    RECT d; string vis = "";
    if (depth == 0 && DwmGetWindowAttribute(h, 9, out d, 16) == 0) vis = " visible " + d.L + "," + d.T + "-" + d.R + "," + d.B;
    sb.AppendFormat("{0}{1:X8} {2,-24} {3,4},{4,4} {5,4}x{6,-4} client {7},{8} {9}x{10} st={11:X8} ex={12:X8} \"{13}\"{14}\n",
      new string(' ', depth * 2), h.ToInt64(), Cls(h), r.L, r.T, r.R - r.L, r.B - r.T, p.X, p.Y, c.R, c.B,
      GetWindowLongStyleRaw(h, -16), GetWindowLongStyleRaw(h, -20), Text(h), vis);
    var kids = new List<IntPtr>();
    EnumChildWindows(h, (k, l) => { if (GetParent(k) == h) kids.Add(k); return true; }, IntPtr.Zero);
    foreach (var k in kids) sb.Append(Tree(k, depth + 1));
    return sb.ToString();
  }
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr a, int x, int y, int cx, int cy, uint f);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern IntPtr ChildWindowFromPointEx(IntPtr p, POINT pt, uint flags);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr h, uint cmd);
  [DllImport("user32.dll")] public static extern int GetClassLong(IntPtr h, int i);
  [DllImport("user32.dll")] public static extern IntPtr GetFocus();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool f);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [StructLayout(LayoutKind.Sequential)] public struct GUITHREADINFO {
    public int cbSize, flags; public IntPtr hwndActive, hwndFocus, hwndCapture, hwndMenuOwner, hwndMoveSize, hwndCaret; public RECT rcCaret; }
  [DllImport("user32.dll")] public static extern bool GetGUIThreadInfo(uint tid, ref GUITHREADINFO gi);

  public static List<IntPtr> Tops(uint pid) {
    var list = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (p == pid && IsWindowVisible(h)) list.Add(h); return true; }, IntPtr.Zero);
    return list;  // EnumWindows goes top of the z-order first
  }
  public static string Cls(IntPtr h) { var sb = new System.Text.StringBuilder(256); GetClassName(h, sb, 256); return sb.ToString(); }

  // The deepest visible child under a screen point, starting from a top-level window.
  public static IntPtr Deepest(IntPtr top, int sx, int sy) {
    IntPtr h = top;
    for (int depth = 0; depth < 20; depth++) {
      POINT p = new POINT { X = sx, Y = sy }; ScreenToClient(h, ref p);
      IntPtr c = ChildWindowFromPointEx(h, p, 1 | 4);  // CWP_SKIPINVISIBLE | CWP_SKIPTRANSPARENT
      if (c == IntPtr.Zero || c == h) break;
      h = c;
    }
    return h;
  }
  public static IntPtr LParam(int x, int y) { return (IntPtr)((y << 16) | (x & 0xFFFF)); }

  // Composite every visible window of the process, bottom first.
  public static void Shot(uint pid, IntPtr main, int x0, int y0, string path) {
    using (var canvas = new Bitmap(1280, 800)) {
      using (var g = Graphics.FromImage(canvas)) g.Clear(Color.FromArgb(0x3A, 0x6E, 0xA5));
      var tops = Tops(pid); tops.Reverse();
      foreach (var h in tops) {
        RECT r; GetWindowRect(h, out r);
        int w = r.R - r.L, hh = r.B - r.T;
        if (w <= 0 || hh <= 0) continue;
        using (var bmp = new Bitmap(w, hh)) {
          using (var g = Graphics.FromImage(bmp)) { IntPtr dc = g.GetHdc(); PrintWindow(h, dc, 2); g.ReleaseHdc(dc); }
          int dx = r.L - x0 + 20, dy = r.T - y0 + 20;
          // Windows that sit on the real screen (a message box centred there)
          // keep their offset from the main window only roughly; place them
          // centred like the emulator does when they are far away.
          if (h != main && (dx < -w || dx > 1280)) { dx = (1280 - w) / 2; dy = (800 - hh) / 2; }
          using (var g = Graphics.FromImage(canvas)) {
            // Leave out DWM's invisible borders (PrintWindow paints them black).
            bool framed = (GetWindowLongStyle(h) & 0x00C00000) == 0x00C00000;
            if (framed) g.DrawImage(bmp, new Rectangle(dx + 7, dy, w - 14, hh - 7), new Rectangle(7, 0, w - 14, hh - 7), GraphicsUnit.Pixel);
            else g.DrawImage(bmp, dx, dy);
          }
        }
      }
      canvas.Save(path, System.Drawing.Imaging.ImageFormat.Png);
    }
  }
  [DllImport("user32.dll", EntryPoint="GetWindowLong")] public static extern int GetWindowLongStyleRaw(IntPtr h, int i);
  public static int GetWindowLongStyle(IntPtr h) { return GetWindowLongStyleRaw(h, -16); }
}
"@

$psi = New-Object System.Diagnostics.ProcessStartInfo $Exe
$psi.WorkingDirectory = Split-Path $Exe
if ($Arg) { $psi.Arguments = '"' + $Arg + '"' }
$p = [System.Diagnostics.Process]::Start($psi)
$pid0 = [uint32]$p.Id
$main = [IntPtr]::Zero
for ($i = 0; $i -lt 80 -and $main -eq [IntPtr]::Zero; $i++) {
  Start-Sleep -Milliseconds 250
  # Not only the visible ones: started from an ssh session the program is
  # told SW_HIDE, and nothing it creates is shown.
  foreach ($h in [R]::AllTops($pid0)) {
    $c = [R]::Cls($h)
    if ($c -eq "#32770" -and [R]::Text($h) -eq "jw_win") { [R]::SendMessage($h, 0x0111, [IntPtr]2, [IntPtr]::Zero) | Out-Null }   # IDCANCEL
    elseif ($c.StartsWith("Afx:00400000:b:")) { $main = $h }
  }
}
if ($main -eq [IntPtr]::Zero) { "no main window"; Stop-Process -Id $p.Id -Force; exit 1 }
[R]::ShowWindow($main, 4) | Out-Null   # SW_SHOWNOACTIVATE
[R]::SetWindowPos($main, [IntPtr]1, $X0, $Y0, 987, 691, 0x0010) | Out-Null   # HWND_BOTTOM, SWP_NOACTIVATE: behind everything, but on the screen so it paints
try { $p.WaitForInputIdle(10000) | Out-Null } catch {}
Start-Sleep -Milliseconds 800

$lastDown = @{}  # hwnd -> [time, x, y] for double clicks
$prev = 0
foreach ($line in Get-Content -Encoding UTF8 $Script) {
  $f = $line.Split(' ', 3)
  if ($f.Count -lt 2) { continue }
  $t = [int]$f[0]; $cmd = $f[1]; $rest = if ($f.Count -gt 2) { $f[2] } else { "" }
  $gap = [Math]::Max(0, [Math]::Min($t - $prev, 3000)); $prev = $t
  Start-Sleep -Milliseconds $gap
  try { $p.WaitForInputIdle(5000) | Out-Null } catch {}
  $a = $rest.Split(' ')
  switch ($cmd) {
    { $_ -in "move", "down", "up" } {
      $x = [int]$a[0]; $y = [int]$a[1]; $b = if ($a.Count -gt 2) { [int]$a[2] } else { 0 }
      $sx = $x - 20 + $X0; $sy = $y - 20 + $Y0
      # The window under the point: the topmost of the process that contains it.
      $target = $main
      foreach ($h in [R]::Tops($pid0)) {
        $r = New-Object R+RECT; [R]::GetWindowRect($h, [ref]$r) | Out-Null
        if ($sx -ge $r.L -and $sx -lt $r.R -and $sy -ge $r.T -and $sy -lt $r.B) { $target = $h; break }
      }
      $w = [R]::Deepest($target, $sx, $sy)
      $pt = New-Object R+POINT; $pt.X = $sx; $pt.Y = $sy; [R]::ScreenToClient($w, [ref]$pt) | Out-Null
      $lp = [R]::LParam($pt.X, $pt.Y)
      $mk = @(1, 2, 16)[$b]
      if ($cmd -eq "move") { [R]::PostMessage($w, 0x0200, [IntPtr]0, $lp) | Out-Null }
      elseif ($cmd -eq "down") {
        $msg = @(0x0201, 0x0204, 0x0207)[$b]
        $now = [Environment]::TickCount
        $key = "$w/$b"
        $dbl = ([R]::GetClassLong($w, -26) -band 8) -ne 0   # CS_DBLCLKS
        if ($dbl -and $lastDown.ContainsKey($key) -and ($now - $lastDown[$key]) -lt 500) { $msg += 2; $lastDown.Remove($key) }
        else { $lastDown[$key] = $now }
        [R]::PostMessage($w, $msg, [IntPtr]$mk, $lp) | Out-Null
      } else {
        [R]::PostMessage($w, @(0x0202, 0x0205, 0x0208)[$b], [IntPtr]0, $lp) | Out-Null
      }
    }
    "wheel" {
      $x = [int]$a[0]; $y = [int]$a[1]; $d = [int]$a[2]
      $sx = $x - 20 + $X0; $sy = $y - 20 + $Y0
      $w = [R]::Deepest($main, $sx, $sy)
      [R]::PostMessage($w, 0x020A, [IntPtr](($d -band 0xFFFF) -shl 16), [R]::LParam($sx, $sy)) | Out-Null
    }
    { $_ -in "key", "char" } {
      $gi = New-Object R+GUITHREADINFO; $gi.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($gi)
      $tid = [R]::GetWindowThreadProcessId($main, [ref]$pid0)
      [R]::GetGUIThreadInfo($tid, [ref]$gi) | Out-Null
      $w = if ($gi.hwndFocus -ne [IntPtr]::Zero) { $gi.hwndFocus } else { $main }
      # Without the foreground the thread may report no focus: typing then goes
      # to the edit control of a window that has one (the 文字入力 box).
      if ([R]::Cls($w) -ne "Edit") {
        foreach ($h in [R]::Tops($pid0)) { $ed = [R]::FindEdit($h); if ($ed -ne [IntPtr]::Zero -and $h -ne $main) { $w = $ed; break } }
      }
      if ($cmd -eq "key") {
        $vk = [int]$a[0]
        [R]::PostMessage($w, 0x0100, [IntPtr]$vk, [IntPtr]1) | Out-Null
        [R]::PostMessage($w, 0x0101, [IntPtr]$vk, [IntPtr]0xC0000001) | Out-Null
      } else {
        foreach ($ch in $rest.ToCharArray()) { [R]::PostMessage($w, 0x0102, [IntPtr][int]$ch, [IntPtr]1) | Out-Null }
      }
    }
    "dump" {
      $txt = ""
      foreach ($h in [R]::Tops($pid0)) { $txt += [R]::Tree($h, 0) }
      [IO.File]::WriteAllText((Join-Path $Out "tree.txt"), $txt, [Text.Encoding]::UTF8)
    }
    "shot" {
      Start-Sleep -Milliseconds 2000
      try { $p.WaitForInputIdle(5000) | Out-Null } catch {}
      $name = Split-Path $rest -Leaf
      [R]::Shot($pid0, $main, $X0, $Y0, (Join-Path $Out $name))
      # And the screen itself, where DWM's border and shadow show (PrintWindow
      # leaves them out).  Other windows may be in front: use it for frames.
      $bmp = New-Object System.Drawing.Bitmap 1280, 800
      $g = [System.Drawing.Graphics]::FromImage($bmp)
      $g.CopyFromScreen($X0 - 20, $Y0 - 20, 0, 0, (New-Object System.Drawing.Size 1280, 800))
      $bmp.Save((Join-Path $Out ("screen_" + $name))); $g.Dispose(); $bmp.Dispose()
    }
  }
}
Start-Sleep -Milliseconds 500
[R]::Shot($pid0, $main, $X0, $Y0, (Join-Path $Out "final.png"))
Stop-Process -Id $p.Id -Force
$p.WaitForExit(10000) | Out-Null
