# RESUME — 作業の引き継ぎ

別の Claude（別のマシン）がこのリポの作業を続けるためのメモ。まず README.md と
これを読み、`git pull` してから始めること。

## 何をしているか

Windows 版 Jw_cad（`orig/Jw_win.exe`、10.03.6）を**無改変**で x86 エミュレータ上で動かし、
WASM にしてブラウザで動かす。CPU・ローダは `src/emu/`（x86_emu_cpp 由来）、
Win32 の user32/gdi32 などは `src/win32/` に自作。comctl32 は Wine の DLL をゲストとして動かす。

公開版: https://yomei-o.github.io/jwcad_win_emu_cpp/

## いまの状態（2026-10-22）

* 起動・作図・開く・上書き保存・印刷（PDF/PNG）・ブラウザのファイルパネルは動作確認済み
* 見た目は本物（Windows 11 上の Jw_cad）のキャプチャと合わせ済み：枠・キャプションボタン・
  メニューバー・ツールバー帯・チェックボックス・MessageBox
* **いまやっていること：全コマンドの動作確認**（ユーザーの依頼「きちんと動いているか各コマンドを確認して」）
  * `tools/cmdcheck.py` で 108 個のテスト（ツールバーの全コマンド・メニュー・ズーム・ファイル入出力）を回し、
    クラッシュ・未実装 API・エラー MessageBox は**ゼロ**
  * スクリーンショットを目で見て確認中。本物との比較（`tools/realcheck.py`）は 67 中 約30 で中断
    （ユーザーがこの PC を使い始めたため）

### この回で直したもの（未 push 分を含む、下の「最初にやること」参照）

* コピー → 貼付が何も貼れなかった：Jw_cad は OleSetClipboard（MFC COleDataSource）を使う。
  OleSetClipboard / OleGetClipboard を実装（`src/win32/shell_ole.cpp`）
* ファイル選択で日付が 1970 になる：`list_directory` が host パスを stat_path に渡して C: を二重変換していた
  → `FileTable::stat_host` を追加
* 文字入力ボックスのフォント欄が空・縦 244px：ドロップダウン型 ComboBox は高さを保つ
  （WM_WINDOWPOSCHANGING で選択欄の高さに直す。`controls.cpp`）
* コマンドラインの日本語ファイル名が開けない（ネイティブ版）：argv を GetCommandLineW から UTF-8 で取る
* `--drive-c` を絶対パス化。MultiByteToWideChar(CP_UTF8) の MB_ERR_INVALID_CHARS を実装
* ヘッドレス実行のスクリプト時刻を「プログラムの時計」に変更（`main_gui.cpp` HeadlessHost）：
  計算中は進まない。並列実行や遅いマシンでも同じ所でイベントが届く

### 2026-10-23（会社の PC で追加）

* 文字コマンドの「書込み文字種変更」ダイアログと文字入力ボックスを本物と比較（`text_font` テスト）
  * ラジオボタンがチェックボックスで描かれていた（DrawFrameControl の DFCS_BUTTONRADIO=4）→ 本物の 12x12 の形で描く
  * 枠・影：この PC の Windows 11 は**角が四角**。枠は背景を約 33% 暗く、影は左右 18%→16px で減衰、
    下は 31% で長く伸びる（実測値は `user.cpp` の compose_dwm のコメント）
  * ドロップダウン型コンボを描き直すと子の Edit を白く塗りつぶしていた（開いた瞬間フォント名が消えた）
  * 公開版で「フォントのリストが変な位置に出る」のは、前回直したコンボの高さ（244px のまま）の古い wasm だったため
* 基本設定のプロパティシートのボタンがアラビア語で☒になっていた：リソースの言語を選ばず先頭を返していた
  → 日本語・中立・英語の順に選ぶ（`strings.cpp` と `hooks_win32c.cpp` の 2 か所）
* `realrun.ps1` に画面そのもののキャプチャ（`screen_*.png`、DWM の枠と影が写る）と `dump`（本物の窓ツリー）を追加

### ファイル入出力（2026-10-22 夜、ユーザーの依頼「DXF などいろんな形式で入出力できるか調べて」）

結果：**JWW / JWC / DXF / SFC / P21 の保存と読み込みがすべて往復できる**。テストは `tests/io/` と
cmdcheck の `save_*`・`open_*`・`dxf_*`・`file_batch`・`image_*`・`jwf_*`・`text_file_read`。

| 形式 | 保存 | 開く | メモ |
|---|---|---|---|
| JWW | ○ | ○ | 名前を付けて保存で拡張子が付かなかった（下の 1） |
| JWC | ○ | ○ | |
| DXF | ○ | ○ | 内蔵の書出し（R12 相当）と JWW2DXFConv.dll（AC1024、レジストリ `DXF\DxfOutUseDll=1`）の両方 |
| SFC（SXF） | ○ | ○ | common_lib.dll |
| P21（SXF） | ○ | ○ | common_lib_AP202.dll。作業ファイルを %TEMP% に作る（下の 4） |
| 他の CAD 風 DXF | — | ○ | `tools/gen_dxf.py`：R12（ENTITIES だけ）、R2000、R2007（UTF-8）。SPLINE だけ出ない（Jw_cad 側の仕様と思うが本物で未確認） |
| 画像（BMP） | 同梱で JWW に | ○ | 画像編集→画像挿入。JPEG/PNG は Direct2D 表示のときだけ Jw_cad が許す（下の 6） |
| 環境設定 .jwf | ○ | ○ | |
| テキスト（文字→文読） | | ○ | Shift-JIS |
| ファイル一括変換 | ○ | | 複数選択（OFN_ALLOWMULTISELECT） |

直したもの：

1. **MultiByteToWideChar** がバッファ不足のとき何も書かなかった。ATL の `CString(const char*)` は
   長さ -1・バッファは終端なしの長さで呼び、Windows が「書けた分は書いて失敗する」ことに頼る。
   Jw_cad の狭い文字列リテラルがすべて空の CString になり、`"" == ".jww"` が真 → 拡張子が付かない、
   DXF 保存が空の MessageBox で失敗、など。（`kernel_extra.cpp`）
2. **WindowFromPoint 相当**：HTTRANSPARENT を返す子（グループボックス）は飛ばして下の兄弟を探す。
   新規作成ダイアログの「保存形式」ラジオが押せなかった。（`user.cpp` window_from_point）
3. **CB_SELECTSTRING / LB_FINDSTRING に空文字列**は何も選ばない。DDX_CBString が空の値を先に送って
   選択を .jww に戻していた（DXF を開くのファイル選択が .jww で始まる）。（`controls.cpp`）
4. C: をフォルダに割り当てたとき **TEMP/TMP は C:\Temp**、GetTempPath はフォルダを作る。ホストの
   %TEMP% は C: の中に無いので P21 保存が「0 :」で失敗していた。
5. **PlgBlt** が stub だった。挿入画像は DrawDibDraw でメモリ DC に描いてから PlgBlt（マスク付き）で写す。
6. Jw_cad が JPEG/PNG/GIF/TIFF の挿入を許すのは `[0xa088f4]`（レジストリ `View\Direct2d`）が真のときだけ。
   エミュレータは Direct2D が無いと答える → GDI 表示 → BMP だけ（Direct2D の無い実機と同じ）。
   GDI 表示では GDI+ は呼ばれない（gdiplus は stub のまま）。
7. **ファイルを開く／保存のダイアログ**（GetOpenFileName / GetSaveFileName）を新しく作った（`dialog.cpp`
   file_dialog）。これまでは JWEMU_OPEN 環境変数だけ。複数選択、拡張子なしの名前には種類の拡張子を付ける。
8. **ANSI のファイル API**（CreateFileA・FindFirstFileA など）をエミュレータ本体は UTF-8 で読んでいた。
   SXF の DLL は Shift-JIS のパスを渡すので日本語名の SFC/P21 が壊れた。GUI 層で CP932 → W に置き換え
   （`Emulator::replace_hook`、`ansi.cpp` の末尾）。配布の図面 16 個すべてが一括変換で JWC/DXF/SFC/P21 になる

9. **MoveFileW・ReplaceFileW・PathFileExistsW・PathIsDirectoryW** がパスを二重に変換していた
   （FileTable の関数は自分で host_path する）。ファイル名変更が失敗、ネイティブで PathFileExists が常に偽。
   INI・GetTempFileName・LoadImage の fopen は `FileTable::fopen_guest`（日本語パス）
10. ブラウザ版でも DXF・SFC 保存を確認（`web_test.mjs` に追加。SFC は common_lib.dll を仮想 C: から読む）

ほかに確認したもの：ファイル操作（比較・名前変更・削除・属性変更・図面情報コピー。送信は MAPI が無いので
「メール システム サポートを読み込めません」= メールソフトの無い実機と同じ）、旧バージョン（Ver4.20）保存と読込、
図形の配置、図形登録（.jws 書き出し）。

調べるのに足した道具：

* `-c` のトレースに呼び出し元（`[hook] Name <- 0x...`）
* `JWEMU_STACK=<API名>`：その API の呼び出しごとに EBP チェーン
* `JWEMU_BREAK=addr,addr`（16 進）：そこに来たらレジスタと、レジスタ・スタック先頭が指す文字列を表示
* cmdcheck の手順に `('put', src, name)`・`('arg', name)`・`('env', k, v)`・`('reg', key, name, dword)`・
  `('allow_msgbox',)`、`KEEP_C=1` で C: を残す

## 最初にやること

1. `git pull`
2. ネイティブをビルドして全テストを回す（最後の修正後、全体はまだ回していない）
   ```sh
   sh tools/build.sh
   python tools/cmdcheck.py          # 全テスト。JOBS=4 で並列、結果は tmp/cmd/
   ```
   `ok` が並べば OK。`tmp/cmd/sheet_*.png` が一覧（6 枚ずつ）。
3. WASM を作り直して push（2026-10-23 時点で jwemu.wasm は最新）
   ```sh
   sh tools/build_wasm.sh
   node tools/web_test.mjs           # 線・アップロード・スクロール・開く・保存・印刷
   ```
   （Node 20 では `node --experimental-websocket tools/web_test.mjs`。WebSocket が標準で無い）
   全部 `ok` なら commit → pull → push（ユーザーの方針：確認済みの成果は聞かずに push まで）

## 残りの作業（優先順）

1. **文字入力ボックスの文字が大きすぎる**（ユーザー指摘）。いま約 16px。本物の大きさを
   `realcheck.py text_typed` で撮って合わせる（`realrun.ps1` は 文字入力 の Edit に WM_CHAR を送るよう直してある）。
   エディットのフォントは Jw_cad が WM_SETFONT で与えている。フォント名・高さを JWEMU_TRACE_MSG で追うと早い
2. ~~外変のファイル一覧でメモ欄が文字化け（`[UTF-8]`）~~ → 直った（`[S-JIS]` と正しい日本語）。
   原因は MultiByteToWideChar（「ファイル入出力」の 1）
3. **基設（基本設定）のタブ**がただの文字列に見える（Wine comctl32 の SysTabControl32）。本物と比較
4. **建平・建断・建立**のファイル選択が空。本物も空か確認
5. **ホイールで拡大縮小しない**。本物の既定値も無効かもしれない。確認
6. 押下中のツールバーボタン（「／」など）が本物は市松模様、こちらは単色。調べた所：左のパレットは Wine の
   ToolbarWindow32（TBSTYLE_FLAT なし、テーマなし）。Wine は CDIS_CHECKED かつ非 hot のときだけ
   TOOLBAR_DrawPattern（55AA のパターンブラシで PatBlt）を呼ぶが、呼ばれていない＝ボタンが CHECKED になっていない
   らしい（MFC は DefWindowProc 経由で TB_SETSTATE を送るので JWEMU_TRACE_MSG に出ない）。パターンブラシ自体は正しい。
   TrackMouseEvent（WM_MOUSELEAVE）は実装した
7. メニューなどの文字幅：本物は Yu Gothic UI。代わりのフォントが横に広い（「ファイル(F)」本物 46px / こちら 60px）
8. 未実装 import の一覧：`--script` に `4000 dump` の 1 行を書くと `[unimplemented]` で出る。
   OLE 埋め込み・メタファイル（CreateMetaFile 等）・PolyBezierTo・GdiAlphaBlend など。使われた時に実装
9. ファイル入出力の残り（上の「ファイル入出力」）：DXF の SPLINE が読まれないのが本物も同じか、
   新しいファイルダイアログの見た目（本物は Vista の IFileDialog）。JPEG/PNG の画像挿入は Direct2D が要るので大仕事

## テストの道具

### tools/cmdcheck.py（エミュレータ側・どこでも）

* テストは `T = {...}` に手順で書く（ボタン名・座標・クリック・文字・スクショ）。座標は画面座標で、
  初回起動時のメイン窓 (20,20) が前提。図面は 木造平面例.jww をコマンドライン引数で開く
* 各テストは自分専用の C: と空のレジストリで動く（tmp/cmd/<test>/）
* `python tools/cmdcheck.py -l` で一覧、名前を並べると個別実行
* ログは tmp/cmd/<test>/log.txt（`[MessageBox]`、`jwemu:` 例外、`[unimplemented]`）
* 画像ビューアがパスでキャッシュするので、一覧は毎回違う名前（sheet_時刻_NN.png）

### tools/realcheck.py + realrun.ps1（本物との比較・**Windows のみ**）

* 同じスクリプトを本物の Jw_win.exe に PostMessage で流し、PrintWindow で撮って
  `tmp/cmd/<test>/pair_*.png`（上がエミュレータ、下が本物）を作る
* **本物の窓が画面に出る**（z 順の一番下だが、ダイアログは前に出ることがある）。
  ユーザーが PC を使っている時は動かさない。聞いてから
* **HKCU\Software\Jw_cad を一時的に消す**（毎テスト空の設定、Direct2d=0 だけ入れる）。
  開始時に export、終了時に import で戻す。途中で殺した場合は手で戻すこと：
  `reg delete HKCU\Software\Jw_cad /f` → `reg import <バックアップ>`。
  元の設定のバックアップは作業したマシンの `tmp/realrun/jwcad_ORIGINAL_backup.reg`（git 外）。
  別マシンでやるなら最初に必ず自分で export しておく
* 本物の描画領域は一部しか撮れない（黒い線・点グリッドが写らない）。比べられるのは
  コントロールバー・ステータスバー・ダイアログ・メニュー。描画結果はエミュレータ側の画像で判断する
* 起動時の関連付け確認ダイアログには必ず IDCANCEL を送る（install.exe を動かさない）
* ビルド機（192.168.6.14）は ssh セッションでは窓が表示されず PrintWindow が真っ黒。使えない

### その他

* `--script` の `dump`：窓ツリーと未実装 import を stderr に出す
* `JWEMU_TRACE_MSG=1`：メッセージのトレース、`-c`：API 呼び出しのトレース
* run.sh / 手で動かす時は `--drive-c` や `--shot` を**絶対パス**で（ゲストが chdir するので相対は迷子になる）

## 分かっていること（ハマりどころ）

* 先に登録したフックが勝つ。GUI 層（install_all）の順番に注意
* x86 の catch はディスパッチャに戻らず外側の call_guest の番兵へ ret する → NestedReturn
* MFC は DS_MODALFRAME など Windows 11 の DWM 枠（7px 透明＋1px 枠）前提で配置を計算する。
  ダイアログ単位は ＭＳ Ｐゴシック 9pt の高さ（1em）で決まる → フォントの OS/2 値を MS フォントに合わせた
* 本物の見た目の比較は「同じ位置・サイズ」で撮り、窓ツリー（位置・client・style）も比べると原因が早く分かる
* ユーザーの好み：メイン窓は最大化しない（背景の青が見える方が好き）、comctl32 は Wine、
  CP932 は libtera の kanji.c、repo を clone すれば全部ビルドできること、返事は日本語
