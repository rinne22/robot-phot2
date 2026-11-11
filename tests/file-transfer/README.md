# 開発者向けの検証

利用者がPCへインストールするものではありません。実際の受け渡しテストは公開ページの `file-transfer/TESTING.md` を使います。

- `python3 tests/file-transfer/browser_test.py`：Python PlaywrightとChromiumがある開発環境で実行。初期設定前の表示、API呼び出しの送受信形式、独立したブラウザセッション、ダウンロードしたバイト列、XSSを防ぐテキスト表示、署名URLの組み立て、検索・フィルタ、削除・容量確認失敗時の停止を検証する。**APIはテスト専用の模擬応答**で、Supabaseへの実接続確認ではない。
- `cd tests/file-transfer && npm install && npm test`：PGlite 0.5.16上でPostgreSQLの実SQLを実行。Supabaseの最小Storage/Authスキーマを模擬してRLS・権限・トリガー・容量予約を検証する。**Hosted SupabaseのStorageサービスやメール送信は検証しない**。
- `python3 scripts/package_transfer.py`：利用者向けソースZIPを再作成する。

2026年11月11日の結果：SQL検証23項目成功。Chromiumで操作検証成功。Hosted Supabaseの実APIでも認証・保存・別セッションからの取得・共有・RLS・削除を確認した。標準メール配送、利用者自身の新規登録、Windows実機2台での転送は未実施。公開後にTESTING.mdの確認を行うこと。

`live_test.py` はstdinで一時テストアカウント2つのJSONを受け取り、Hosted Supabaseに接続して検証する。パスワード・トークンは出力しない。実行時の設定を使うため、検証専用アカウントのみ指定すること。

接続時のHosted APIテストは10項目成功（署名URLの実際の期限切れ拒否を含む）。`live_browser.py` では元のページを閉じ、独立したブラウザコンテキストから同一バイトを取り出せることも確認した。Cloud実行環境のChromiumにはHTTPS検査CAが未設定だったため、`RELAY_VERIFIED_HTTPS_BRIDGE=1` で環境既定のCAを検証するurllibを経由した。模擬データは使っていないが、Chromium単独の外向きTLS接続やWindows実機の検証ではない。検証アカウント・ファイルは終了後に削除済み。
