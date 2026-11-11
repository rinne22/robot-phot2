// Supabase Dashboard → Project Settings → API / API Keys の公開用の値だけを設定します。
// service_role / sb_secret_... / DBパスワードは絶対に書かないでください。
window.TRANSFER_CONFIG = Object.freeze({
  supabaseUrl: '',
  publishableKey: '',
  bucket: 'pc-transfer'
});
