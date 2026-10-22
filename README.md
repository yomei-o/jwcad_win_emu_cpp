# jwcad_win_emu_cpp

Windows 版 **Jw_cad**（`orig/Jw_win.exe`、Jw_cad 10.03.6）を、改造せずにそのまま
x86 エミュレータで動かすためのリポジトリです。目標は WASM にしてブラウザで動かすこと。

* CPU・ローダ・kernel32 などは [x86_emu_cpp](https://github.com/yomei-o/x86_emu_cpp)
  （commit 18b9024）を `src/emu/` に取り込んだもの
* その上に **Win32 GUI 層**（`src/win32/`）を新しく書いている：user32（窓・メッセージ・
  メニュー・ダイアログ・標準コントロール）、gdi32（ソフトウェア描画）、レジストリ、
  コードページ 932 など
* MFC は Jw_win.exe に静的リンクされているのでゲストコードとしてそのまま動く
* comctl32 は **Wine 8.0 の comctl32.dll（LGPL）**をゲストとしてそのまま動かす
  （`dlls_dist/wine/`、出どころとライセンスは同じ場所の README.md）
* Direct2D / DirectWrite / GDI+ などは「無い」と答える（Jw_cad は GDI 描画に切り替わる）

**状態: メインウィンドウが表示されるところまで。** 本物の Jw_win.exe が起動処理
（MFC・comctl32・common_lib.dll の初期化、関連付けの確認）を通り、メニュー・
ツールバー・レイヤボタン・ステータスバーを描いてメッセージループに入る。
操作（クリック・作図）の確認はこれから。

![エミュレータ上の Jw_cad](docs/first_window.png)

## ブラウザで動かす

**<https://yomei-o.github.io/jwcad_win_emu_cpp/>**（Chrome / Edge / Firefox。初回は
サービスワーカーを入れるために一度だけ自動で再読み込みします）

エミュレータは Web Worker の中で動き、Jw_cad が入力を待つ間は `Atomics.wait` で
止まります。そのため SharedArrayBuffer が要り、GitHub Pages では `coi-sw.js` が
COOP/COEP ヘッダを付けています。画面は Worker が描いた ImageBitmap をページへ送っています。
設定（レジストリ）はブラウザの localStorage に残ります。

![ブラウザで線を引いたところ](docs/browser_line.png)

```sh
sh tools/build_wasm.sh            # -> jwemu.js / jwemu.wasm / jwemu.data（emsdk）
node tools/test_wasm.mjs          # node でヘッドレスに起動して tmp/wasm.png
node tools/web_test.mjs           # ヘッドレス Chrome で開いて線を引き tmp/web_*.png
```

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
* `dlls_dist/wine/comctl32.dll` は Wine（GNU LGPL 2.1 以降、`dlls_dist/wine/COPYING.LIB`）
* `src/third_party/libtera/` は libtera の kanji.c（BSD）
* `src/third_party/stb_truetype.h` は stb（パブリックドメイン / MIT）
* それ以外のソースは MIT（`LICENSE`）
