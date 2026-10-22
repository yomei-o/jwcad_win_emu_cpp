# jwcad_win_emu_cpp

Windows 版 **Jw_cad**（`orig/Jw_win.exe`、Jw_cad 10.03.6）を、改造せずにそのまま
x86 エミュレータで動かすためのリポジトリです。目標は WASM にしてブラウザで動かすこと。

* CPU・ローダ・kernel32 などは [x86_emu_cpp](https://github.com/yomei-o/x86_emu_cpp)
  （commit 18b9024）を `src/emu/` に取り込んだもの
* その上に **Win32 GUI 層**（`src/win32/`）を新しく書いている：user32（窓・メッセージ・
  メニュー・ダイアログ・標準コントロール）、gdi32（ソフトウェア描画）、レジストリ、
  コードページ 932 など
* MFC は Jw_win.exe に静的リンクされているのでゲストコードとしてそのまま動く
* comctl32 は本物の DLL（5.82）をゲストとしてロードする。Microsoft の DLL なので
  リポジトリには入れず、`tools/build.sh` が手元の `C:\Windows\SysWOW64` からコピーする
* Direct2D / DirectWrite / GDI+ などは「無い」と答える（Jw_cad は GDI 描画に切り替わる）

**状態: 作業中。** まずメインウィンドウが表示されるところまでが目標。

## ビルドと実行（ネイティブ）

```sh
sh tools/build.sh                     # -> jwemu.exe（w64devkit の g++、低優先度）
./jwemu.exe orig/Jw_win.exe           # 窓で動かす
./jwemu.exe --headless --time 8000 --shot out.png orig/Jw_win.exe   # 画面を PNG に
```

## 権利

* `orig/` は Jw_cad の配布物そのまま（著作権は清水治郎・田中善文両氏、使用条件は
  `orig/Jw_win.txt`）
* `fonts/` は IPAex フォント（IPA Font License）、BIZ UDGothic・Liberation・Carlito（SIL OFL）
* `src/third_party/libtera/` は libtera の kanji.c（BSD）
* `src/third_party/stb_truetype.h` は stb（パブリックドメイン / MIT）
* それ以外のソースは MIT（`LICENSE`）
