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
  * `tools/cmdcheck.py` で 68 個のテスト（ツールバーの全コマンド・メニュー・ズーム）を回し、
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

## 最初にやること

1. `git pull`
2. ネイティブをビルドして全テストを回す（最後の修正後、全体はまだ回していない）
   ```sh
   sh tools/build.sh
   python tools/cmdcheck.py          # 全テスト。JOBS=4 で並列、結果は tmp/cmd/
   ```
   `ok` が並べば OK。`tmp/cmd/sheet_*.png` が一覧（6 枚ずつ）。
3. WASM を作り直して push（**この回の修正は jwemu.wasm にまだ入っていない**）
   ```sh
   sh tools/build_wasm.sh
   node tools/web_test.mjs           # 線・アップロード・スクロール・開く・保存・印刷
   ```
   全部 `ok` なら commit → pull → push（ユーザーの方針：確認済みの成果は聞かずに push まで）

## 残りの作業（優先順）

1. **文字入力ボックスの文字が大きすぎる**（ユーザー指摘）。いま約 16px。本物の大きさを
   `realcheck.py text_typed` で撮って合わせる（`realrun.ps1` は 文字入力 の Edit に WM_CHAR を送るよう直してある）。
   エディットのフォントは Jw_cad が WM_SETFONT で与えている。フォント名・高さを JWEMU_TRACE_MSG で追うと早い
2. **外変（外部変形）のファイル一覧でメモ欄が文字化け**：BAT は Shift-JIS なのに `[UTF-8]` と表示される。
   Jw_cad の UTF-8 判定方法を調べる（MB_ERR_INVALID_CHARS は実装したが変わらなかった。
   IsTextUnicode か、自前判定か、別の API）。本物の表示を realcheck で確認してから
3. **基設（基本設定）のタブ**がただの文字列に見える（Wine comctl32 の SysTabControl32）。本物と比較
4. **建平・建断・建立**のファイル選択が空。本物も空か確認
5. **ホイールで拡大縮小しない**。本物の既定値も無効かもしれない。確認
6. 押下中のツールバーボタン（「／」など）が本物は市松模様、こちらは単色（Wine の imagelist がアルファ扱いしている疑い）
7. メニューなどの文字幅：本物は Yu Gothic UI。代わりのフォントが横に広い（「ファイル(F)」本物 46px / こちら 60px）
8. 未実装 import の一覧：`--script` に `4000 dump` の 1 行を書くと `[unimplemented]` で出る。
   OLE 埋め込み・メタファイル（CreateMetaFile 等）・PolyBezierTo・GdiAlphaBlend など。使われた時に実装

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
