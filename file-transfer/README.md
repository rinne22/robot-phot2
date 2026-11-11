# Relay：無料で使うPC間ファイル受け渡し

HTML・CSS・JavaScriptだけで動くGitHub Pages用サイトです。ファイル本体は**Supabaseのprivate Storage**、ファイル情報はPostgreSQLに保存します。アップロードが完了すればPC-Aの電源を切っても、PC-Bで同じアカウントにログインして取り出せます。ファイル本体をlocalStorageには保存しません。

**公開サイトはSupabase Freeへ接続済みです。** 東京リージョンの `relay-pc-transfer` にDB・private Storage・RLSを適用し、実際のAPIで保存・別ログインからの取得・共有・削除を確認しました。見本のファイルや架空のアップロードは表示しません。

認証メールの戻り先は、管理者がAuthentication → URL Configurationで、Site URLとRedirect URLsに `https://rinne22.github.io/robot-phot2/file-transfer/` を設定してください。連携ツールではこの認証設定の変更ができないため、管理画面での操作が必要です。メール配送と実際のWindows PC2台での転送は利用者の確認が必要です。

以下の作成手順は、設定を確認したい場合や別の自分用Supabase環境へ移す場合にも利用できます。

## 1. 無料の範囲と限界を先に確認

2026年11月11日確認の[Supabase Free料金表](https://supabase.com/pricing)では、ファイル保存1 GB、データベース500 MB、通常の送信量5 GBとキャッシュ送信量5 GB、月間利用者50,000人。Freeでは1週間非稼働で休止の対象になり、稼働プロジェクトは2つまでです。無料枠・規約は将来変わるため、公開前と運用中に公式ページを確認してください。

- **Free組織・Freeプロジェクトで利用し、カード登録・Proへの変更・有料オプション追加はしません。** Freeの制限を解除するために課金する処理はこのコードにありません。
- このアプリは専用Supabaseプロジェクトで使ってください。他のアプリや有料プロジェクトと同じ組織の枠を共有しない構成にします。
- 1ファイルは**50,000,000 bytes（50 MB）以下**。アプリ全体の保存上限を**800,000,000 bytes（800 MB）**に抑え、全ユーザー共通でSQLが判定します。画面を改造しても上限を回避できない設計です。
- DBの安全上限は400 MB、ファイル・予約は合計10,000件まで。上限到達時は新規アップロードを拒否し、理由を表示します。削除・既存ファイルの取り出しは可能です（Supabase自体が制限中の場合を除く）。
- 通信量・認証メール・月間利用者数など、**無料枠全体の実測値をこの静的サイトだけで自動取得・厳密制御することはできません**。Supabase DashboardのUsageで確認してください。署名付き共有URLは期限内に複数回使えるため、URL発行数だけでは通信量を制限できません。Free側の制限と運用者の監視が必要です。
- 保存はPCと独立していますが、**無料で無期限に消えないことや、いつでも無休止でアクセスできることは保証されません**。休止・保持期間・復旧条件は[Project Pausing](https://supabase.com/docs/guides/platform/pausing)を確認し、定期的に利用・バックアップしてください。休止中はDashboardから復旧するまで使えません。重要ファイルの唯一の保存先にはしないでください。
- 大量配布や一般公開のファイル配信サービスには向きません。私的な少人数の受け渡し用です。GitHub Pagesの利用規約・帯域制限も守ってください。

## 2. ファイル構成

```text
file-transfer/
  index.html       ファイル管理画面
  style.css        ダークモード・レスポンシブデザイン
  app.js           Supabase Auth / REST / Storageへの実接続
  config.js        公開用の接続先・公開キー（初期状態は空）
  supabase.sql     DB・private bucket・RLS・容量予約・トリガー
  setup.html       ブラウザで読める導入案内
  README.md        この手順書
  TESTING.md       PC-A/PC-B・共有・RLSの確認方法
```

フレームワーク・ビルド・有料サーバー・R2・PCアプリは不要です。API呼び出しはブラウザからSupabaseへ直接HTTPSで送信します。

## 3. Supabase Freeを作る

1. [supabase.com](https://supabase.com/)で無料アカウントを作り、Free組織を選びます。課金情報は入力しません。
2. New projectで**このアプリ専用**のプロジェクトを作成します。近いリージョンを選び、DBパスワードはパスワード管理ソフト等で保存します。**DBパスワードはサイトにもGitHubにも記載しません。**
3. 起動完了後、SQL Editor → New queryを開き、`supabase.sql` の**全文**を貼り付けてRunします。エラーが出た場合は先へ進まず修正してください。コードは再実行可能ですが、既存データのある他プロジェクトに混ぜないでください。
4. Table Editorに `transfer_settings` と `transfer_files` があることを確認します。Storage → `pc-transfer` が**Private**、最大サイズ50 MB、許可MIMEが`application/octet-stream`であることを確認します。
5. Authentication → Providers / Sign In → EmailでEmail/Passwordを有効にします。メール確認はONを推奨します。
6. Authentication → URL Configurationで以下を登録します（末尾の `/` を含めます）。
   - Site URL：`https://あなたのユーザー名.github.io/リポジトリ名/file-transfer/`
   - Redirect URLs：同じURL。ローカル検証時だけそのlocalhost URLも追加します。
7. Project Settings → API（またはConnect）で**Project URL**、API Keysで**Publishable key**（またはlegacyのanon key）を確認します。
8. `config.js` の空欄2つだけを編集します。

```js
window.TRANSFER_CONFIG = Object.freeze({
  supabaseUrl: 'https://プロジェクトID.supabase.co',
  publishableKey: 'sb_publishable_公開キー',
  bucket: 'pc-transfer'
});
```

**`service_role` / `sb_secret_...` / DBパスワードは絶対に使いません。** Publishable/anon keyはブラウザへ公開する前提の値です。データ保護はRLSとログイン認証が担当します。アプリはsecret keyとservice_role JWTを拒否します。supabase.co標準ドメインのみ対応します。

### 認証メールについて

Supabase標準のメール送信サービスには送信先・送信頻度の制限があります。標準サービスでは組織の許可されたメンバー宛だけに送信できる場合があります。[公式のメール設定](https://supabase.com/docs/guides/auth/auth-smtp)を確認してください。最初は所有者のアドレスで検証します。

公開ユーザーへの確認メール配信には、別途SMTP設定が必要になることがあります。SMTPの無料枠・カード不要条件は提供者により異なるため、この成果物では特定の外部サービスを必須にしていません。少人数で始める場合はDashboardのAuthentication → Usersで本人を確認して招待・作成し、必要な利用者だけ登録します。メール確認OFFはなりすまし登録を招くため、一般公開の対策として安易に使わないでください。

パスワード再設定メールも同じ制限の対象です。必要なら管理者がDashboardから対象者を確認して対応します。運用開始後、不要な新規登録はAuthenticationの設定で停止してください。

## 4. GitHub Pagesへ公開する

1. GitHubの公開リポジトリを用意します。無料アカウントでプライベートリポジトリのPagesが使えるとは限りません。ファイル本体・パスワード・秘密鍵はこのリポジトリに入れません。
2. `file-transfer/` フォルダをそのままアップロードし、`config.js` も保存します。既存サイトの中に置いても使えます。
3. Settings → Pages → Build and deployment → Deploy from a branch → `main` / `(root)` → Save。
4. Actionsの「pages build and deployment」が成功したら、公開URLの `/file-transfer/` を開きます。
5. 接続前の案内が消え、ログインボタンが押せることを確認します。接続先を変更した場合は再読み込みしてください。
6. ブラウザで `setup.html`、`supabase.sql`、`README.md`、`TESTING.md` も読めます。PCにアプリを入れる必要はありません。

既存のこのプロジェクトでは公開先は `https://rinne22.github.io/robot-phot2/file-transfer/` です。Supabase作成後、上記URLを認証の戻り先として設定してください。

## 5. 普段の使い方

- ログイン後、ファイルをドロップするか「アップロード」で複数選択します。同時送信は2件まで。50 MBを超えるファイルと空ファイルは拒否します。
- 「保存完了」になるまでタブを閉じません。送信中に閉じると中断する場合があります。応答だけ消えた場合も、一覧を更新すれば保存済みか確認できます。
- 別PCで同じURLへアクセスし、同じアカウントでログインして更新すれば一覧に表示されます。元PCの電源やブラウザに依存しません。
- ファイル名を押すと画像・PDF・テキストを表示します。プレビューは通信量節約のため10 MBまで、テキスト表示は先頭1 MBまでです。Word・Excel・ZIP等はダウンロードして開きます。PDFはブラウザのPDF表示設定によってプレビューできない場合があり、その場合はダウンロードしてください。
- HTML・SVG・JavaScript等はプレビューで**文字列表示**し、サイトの権限で実行しません。Storageでは全形式をoctet-streamとして保管します。
- 「↓」で元のファイル名でダウンロード。「削除」またはチェックして一括削除。削除は取り消せません。
- 「共有」→5分・1時間・24時間の期限を選び発行。**URL自体がアクセス権**なので、渡した相手がさらに転送することもできます。一覧や他のファイルにはアクセスできません。共有URLはSupabaseへ直接つながり、ログイン不要です。
- 共有リンクの期限はSupabaseが検証します。期限前に止めたい場合は元ファイルを削除します。署名URLの個別失効はこの構成では非対応です。受取済みのファイルやブラウザキャッシュまでは消せません。
- 共有PCではログアウトします。ログイン情報だけをタブ内sessionStorageに保存し、ファイル本体やパスワードは保存しません。ダウンロード済みファイルは共有PCに残るため自分で片付けます。

## 6. 容量・失敗時の運用

全体使用量は予約中も含みます。容量予約とStorageの書き込みをSQLで検証するため、同時操作で800 MBを超えて受理しません。ファイル数・DB上限も予約時に検証します。通信量・外部アプリの利用は別途Dashboardで監視します。

通信エラー時には未完了の予約を取り消します。PCを閉じて取消しが走らなかった場合、24時間以上古く実体のない予約だけが次回アップロード時に回収されます。保存済み実体は自動削除しません。予約中の容量も表示に含まれます。

通信量がFreeの上限に近い場合や一時停止したい場合はSQL Editorで次を実行します。

```sql
update public.transfer_settings
set uploads_enabled=false,
    stop_reason='通信量の無料枠に近づいたため、管理者がアップロードを停止しています。'
where id=true;
```

**このスイッチはアップロードを止めるだけです。** 既存の共有URLやダウンロードまで通信を止めるものではありません。共有の大量利用時はファイルを削除し、新規のアクセスを止めてください。Free組織のまま使い、上限を解除するための有料化はしません。上限に達したらプラットフォーム側で利用制限・休止が起こる場合があります。

再開する場合：

```sql
update public.transfer_settings set uploads_enabled=true where id=true;
```

アップロードだけ失敗する場合は、容量・StorageのPrivate/MIME設定・RLS・トリガー作成エラーを確認してください。一覧も使えない場合はSQL未実行、プロジェクト休止、接続先・公開キーの間違いを確認します。UIのエラーを無視して公開運用を始めないでください。

## 7. セキュリティの仕組み

- private bucket、認証済みユーザーのUUIDでStorageのパスを分離。
- ファイル一覧はRLSで本人のレコードだけSELECT可能。クライアントからメタデータの直接INSERT/UPDATE/DELETEは不可。
- 作成は認証を検証するRPCで容量予約してからStorageへ送信。Storageトリガーが実サイズを検証してreadyへ確定。削除はStorage API経由で行い、トリガーがDBの情報も削除。
- フォルダ名・実ファイルのIDはUUID。元ファイル名はDOMのtextContentで表示するので、名前にHTMLが含まれても実行しません。
- ダウンロードは認証済みのBlobをattachment扱いで保存。署名URLにもdownload指定。HTML等を署名URLで開いてもoctet-streamとして配信します。
- PDFはsandbox付きiframe、画像は許可した拡張子とMIMEでのみBlob表示。SVGは画像として実行しません。
- 外部スクリプト・フォント・広告・トラッカーはありません。CSPも設定しています。ただし、Pages上の同一オリジンに置く他ページや、ブラウザ拡張などの侵害まで防ぐものではありません。
- 既存の「誰でも読める」StorageポリシーはORで評価されてしまいます。**新規の専用プロジェクト**を使い、広いポリシーを追加しないでください。

## 8. 動作確認

[TESTING.md](TESTING.md)にPC-A/PC-Bの実機テストと、他アカウント・匿名アクセス・期限付き共有・容量超過・削除の確認手順を掲載しています。

ローカルPostgreSQL/RLSテスト23項目とブラウザ模擬テストに加え、Hosted Supabaseの実APIで認証・保存・独立したログインからの同一バイト取得・他アカウント拒否・共有・削除を確認しました。メールの実配送、利用者のアカウント登録、Windows実機2台での受け渡しは別途TESTING.mdで確認してください。

公式資料：[料金](https://supabase.com/pricing) / [RLS](https://supabase.com/docs/guides/storage/security/access-control) / [Storage配信](https://supabase.com/docs/guides/storage/serving/downloads) / [通信量](https://supabase.com/docs/guides/platform/manage-your-usage/egress) / [認証](https://supabase.com/docs/guides/auth/passwords)
