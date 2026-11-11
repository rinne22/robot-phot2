# 開発者向けの検証

利用者がPCへインストールするものではありません。実際の受け渡しテストは公開ページの `file-transfer/TESTING.md` を使います。

- `python3 tests/file-transfer/browser_test.py`：Python PlaywrightとChromiumがある開発環境で実行。初期設定前の表示、API呼び出しの送受信形式、独立したブラウザセッション、ダウンロードしたバイト列、XSSを防ぐテキスト表示、署名URLの組み立て、検索・フィルタ、削除・容量確認失敗時の停止を検証する。**APIはテスト専用の模擬応答**で、Supabaseへの実接続確認ではない。
- `cd tests/file-transfer && npm install && npm test`：PGlite 0.5.16上でPostgreSQLの実SQLを実行。Supabaseの最小Storage/Authスキーマを模擬してRLS・権限・トリガー・容量予約を検証する。**Hosted SupabaseのStorageサービスやメール送信は検証しない**。
- `python3 scripts/package_transfer.py`：利用者向けソースZIPを再作成する。

2026年11月11日の結果：SQL検証21項目成功。Chromiumで操作検証成功。Supabase未作成のため実クラウド接続、標準メール配送、実機2台での転送、Windows実機での確認は未実施。公開後にTESTING.mdの確認を行うこと。
