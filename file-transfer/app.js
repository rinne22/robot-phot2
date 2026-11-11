'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const config = window.TRANSFER_CONFIG || {};
  const BUCKET = 'pc-transfer', MAX_FILE = 50000000, PREVIEW_LIMIT = 10000000, PAGE_SIZE = 25;
  const SESSION_KEY = 'relay-auth:' + (config.supabaseUrl || 'unconfigured');
  let base = '', configured = false, session = null, refreshPromise = null;
  let files = [], selected = new Set(), filter = 'all', page = 1, usage = null, busy = false, sharing = null;
  let toastTimer, previewUrl = null, previewSequence = 0, dialogResolve = null, viewEpoch = 0, listRequest = 0;
  const formatSize = n => n < 1000 ? `${n} B` : n < 1000000 ? `${(n / 1000).toFixed(1)} KB` : `${(n / 1000000).toFixed(1)} MB`;
  const date = s => new Date(s).toLocaleString('ja-JP', {year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
  const ext = name => (name.split('.').pop() || '').toLowerCase();
  const imageExt = new Set(['png','jpg','jpeg','gif','webp','avif']);
  const textExt = new Set(['txt','md','csv','json','log','xml','css','js','ts','py','c','cpp','h','ino','html','htm','svg','yaml','yml']);
  const docExt = new Set(['pdf','doc','docx','xls','xlsx','ppt','pptx','txt','md','csv']);
  const typeOf = file => imageExt.has(ext(file.filename)) ? 'images' : docExt.has(ext(file.filename)) ? 'documents' : 'others';
  function notify(message, error = false) {
    clearTimeout(toastTimer); $('toast').textContent = message; $('toast').classList.toggle('error',error); $('toast').hidden = false;
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, error ? 14000 : 7000);
  }
  function friendly(error) {
    const text = error?.message || String(error);
    if (/Failed to fetch|NetworkError|network|ネットワーク/i.test(text)) return '通信できません。インターネット接続とSupabaseの稼働状態を確認し、もう一度お試しください。';
    if (/Invalid login credentials/i.test(text)) return 'メールアドレスまたはパスワードが正しくありません。';
    if (/Email not confirmed/i.test(text)) return '確認メールのリンクを開いてからログインしてください。';
    if (/rate limit|over_email_send_rate_limit/i.test(text)) return '送信回数の上限です。少し時間をあけてください。無料の認証メールには制限があります。';
    if (/row.level|policy|permission denied|42501/i.test(text)) return 'アクセス権限がありません。ログイン状態とsupabase.sqlの設定を確認してください。';
    if (/quota|exceeded|402|too large|413|Payload too large/i.test(text)) return '無料枠またはファイル容量の制限に達しました。課金は行いません。容量・通信量を管理画面で確認してください。';
    return text.length > 350 ? text.slice(0,350) : text;
  }
  function saveSession(value) {
    session = value;
    try { if (value) sessionStorage.setItem(SESSION_KEY,JSON.stringify(value)); else sessionStorage.removeItem(SESSION_KEY); }
    catch { notify('このブラウザではログイン情報を保存できません。再読み込みするとログインし直す必要があります。'); }
  }
  function acceptSession(value) {
    if (!value.access_token || !value.refresh_token) throw new Error('ログイン情報を取得できませんでした。');
    saveSession({...value,expires_at:value.expires_at || Math.floor(Date.now()/1000)+(Number(value.expires_in)||3600)});
  }
  async function parseResponse(response) {
    if (response.status === 204) return null;
    const text = await response.text();
    let data;
    try { data = text ? JSON.parse(text) : null; } catch { data = {message:text}; }
    if (!response.ok) {
      const error = new Error(data?.msg || data?.message || data?.error_description || data?.error || `通信エラー (${response.status})`);
      error.status = response.status; throw error;
    }
    return data;
  }
  async function raw(path, options = {}, token = null) {
    if (!configured) throw new Error('Supabaseの初回設定を完了してください。');
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(),30000);
    try {
      return await parseResponse(await fetch(base + path, {...options, signal:controller.signal,
        headers:{apikey:config.publishableKey,...(token ? {Authorization:`Bearer ${token}`} : {}), 'Content-Type':'application/json',...options.headers}}));
    } catch (error) { if (error.name==='AbortError') throw new Error('通信がタイムアウトしました。再読み込みして状態を確認してください。'); throw error; }
    finally {clearTimeout(timeout);}
  }
  async function token(force = false) {
    if (!session) throw new Error('ログインしてください。');
    if (!force && session.expires_at > Date.now()/1000 + 90) return session.access_token;
    if (!refreshPromise) {
      const previous = session;
      refreshPromise = raw('/auth/v1/token?grant_type=refresh_token',{method:'POST',body:JSON.stringify({refresh_token:previous.refresh_token})})
        .then(data => { if(session!==previous) throw new Error('ログイン状態が変わりました。'); acceptSession(data); return session.access_token; })
        .catch(error => { if ([400,401,403].includes(error.status) && session===previous) {saveSession(null);showAccount();} throw error; })
        .finally(() => {refreshPromise=null;});
    }
    return refreshPromise;
  }
  async function api(path, options = {}) {
    try {return await raw(path, options, await token());}
    catch (error) { if(error.status===401 && session) return raw(path,options,await token(true)); throw error; }
  }
  const rpc = (name,body={}) => api('/rest/v1/rpc/'+name,{method:'POST',body:JSON.stringify(body)});
  function uploadEnabled() { return Boolean(configured && session && usage?.uploads_enabled); }
  function showAccount() {
    $('account-email').textContent = session?.user?.email || '未ログイン';
    $('logout').hidden = !session; $('logout').disabled = busy;
    $('auth-panel').hidden = Boolean(session); $('refresh').disabled = !session;
    $('upload-top').disabled = !uploadEnabled();
    $('drop-zone').setAttribute('aria-disabled',String(!uploadEnabled()));
    ['login','signup','recover'].forEach(id => {$(id).disabled = !configured;});
    if (!session) {files=[];selected.clear();usage=null;renderFiles();renderUsage();}
  }
  function renderUsage() {
    $('storage-meter').value = usage?.used_bytes || 0;
    $('storage-meter').max = usage?.limit_bytes || 800000000;
    $('storage-label').textContent = usage ? `${formatSize(usage.used_bytes)} / ${formatSize(usage.limit_bytes)}` : '接続後に使用量を表示';
    $('own-storage').textContent = usage ? `うち自分の使用量 ${formatSize(usage.own_bytes)}（予約中を含む）` : 'ファイルは非公開で保存されます';
    if (usage && !usage.uploads_enabled) $('file-caption').textContent = usage.reason || 'アップロードは停止中です。';
    if(session && !usage) $('file-caption').textContent = '容量を確認できないためアップロードを停止しています。「更新」を押してください。';
    $('upload-top').disabled = !uploadEnabled(); $('drop-zone').setAttribute('aria-disabled',String(!uploadEnabled()));
  }
  async function reload(silent = false) {
    if(!session) return;
    const epoch=viewEpoch, request=++listRequest;
    $('refresh').disabled=true;
    try {
      // 最大10,000件。Supabaseの標準1000行制限を避けて500件ずつ取得する。
      const listTask = (async () => {
        const all=[];
        for (let offset=0;offset<10000;offset+=500) {
          const part=await api(`/rest/v1/transfer_files?select=id,filename,size_bytes,mime_type,created_at,object_path&status=eq.ready&order=created_at.desc,id.desc&limit=500&offset=${offset}`);
          all.push(...part); if(part.length<500) break;
        }
        return all;
      })();
      const [listResult, quotaResult] = await Promise.allSettled([listTask,rpc('transfer_usage')]);
      if(epoch!==viewEpoch || request!==listRequest) return;
      if(listResult.status==='fulfilled') { files=listResult.value; selected=new Set([...selected].filter(id=>files.some(f=>f.id===id))); renderFiles(); }
      else { $('file-caption').textContent='一覧を更新できませんでした。通信回復後に「更新」を押してください。'; if(!silent) notify(friendly(listResult.reason),true); }
      if(quotaResult.status==='fulfilled') usage=quotaResult.value;
      else {usage=null;if(!silent)notify('容量を確認できないため、アップロードを停止しています。\n'+friendly(quotaResult.reason),true);}
      renderUsage();
    } finally { if(epoch===viewEpoch) $('refresh').disabled=!session; }
  }
  function visibleFiles() {
    const query=$('search').value.toLocaleLowerCase();
    return files.filter(f => (!query || f.filename.toLocaleLowerCase().includes(query)) && (filter==='all' || typeOf(f)===filter))
      .sort((a,b) => $('sort').value==='name' ? a.filename.localeCompare(b.filename,'ja') : ($('sort').value==='oldest'?1:-1)*(new Date(a.created_at)-new Date(b.created_at)) || a.id.localeCompare(b.id));
  }
  function node(tag,text,className) {const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(className)n.className=className; return n;}
  function action(label,title,handler) {const b=node('button',label);b.type='button';b.title=title;b.setAttribute('aria-label',title);b.addEventListener('click',handler);return b;}
  function renderFiles() {
    const list=visibleFiles(), pages=Math.max(1,Math.ceil(list.length/PAGE_SIZE));page=Math.min(page,pages);
    const current=list.slice((page-1)*PAGE_SIZE,page*PAGE_SIZE);
    $('file-list').replaceChildren();
    for (const file of current) {
      const row=node('tr'), checkCell=node('td',undefined,'check-cell'), check=node('input');check.type='checkbox';check.checked=selected.has(file.id);check.setAttribute('aria-label',file.filename+'を選択');
      check.addEventListener('change',()=>{check.checked?selected.add(file.id):selected.delete(file.id);renderFiles();});checkCell.append(check);row.append(checkCell);
      const nameCell=node('td'), name=node('div',undefined,'file-name'), icon=node('span',(ext(file.filename)||'FILE').slice(0,4).toUpperCase(),'file-icon '+(typeOf(file)==='images'?'image':ext(file.filename)==='pdf'?'pdf':''));
      const nameButton=action(file.filename,file.filename+'をプレビュー',()=>preview(file));name.append(icon,nameButton);nameCell.append(name);row.append(nameCell);
      row.append(node('td',(ext(file.filename)||'ファイル').toUpperCase(),'type-column'),node('td',formatSize(file.size_bytes)),node('td',date(file.created_at),'date-column'));
      const cell=node('td'), actions=node('div',undefined,'file-actions');actions.append(action('↓',file.filename+'をダウンロード',()=>download(file)),action('共有',file.filename+'の共有リンク',()=>openShare(file)),action('削除',file.filename+'を削除',()=>deleteFiles([file])));cell.append(actions);row.append(cell);$('file-list').append(row);
    }
    $('file-count').textContent=list.length;
    $('file-caption').textContent=session ? `${files.length}件を保存中 · ${list.length}件を表示対象` : 'ログインすると保存済みファイルを表示します';
    $('empty-state').hidden=list.length>0;
    $('empty-state').querySelector('h3').textContent=!session?'次のPCへ、最初のファイルを。':files.length?'該当するファイルがありません':'まだファイルがありません';
    $('empty-state').querySelector('p').textContent=!session?'ログインしてアップロードすると、ここに表示されます。':files.length?'検索条件や左側の種類を変更してください。':'上のエリアからファイルをアップロードしてください。';
    $('select-all').checked=current.length>0&&current.every(f=>selected.has(f.id));
    $('select-all').indeterminate=current.some(f=>selected.has(f.id))&&!$('select-all').checked;
    $('select-all').disabled=!current.length;
    $('bulk-bar').hidden=!selected.size;$('selected-count').textContent=`${selected.size}件を選択中`;
    $('pagination').hidden=pages<=1;$('page-label').textContent=`${page} / ${pages}`;$('prev-page').disabled=page===1;$('next-page').disabled=page===pages;
  }
  function chooseFiles() {if(!uploadEnabled())return notify(session ? usage?.reason || '容量の確認後にアップロードできます。「更新」を押してください。':'ログインしてからファイルを選択してください。',true);$('file-input').click();}
  function uploadXHR(file,path,access,onProgress) {
    return new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest();xhr.open('POST',base+'/storage/v1/object/'+BUCKET+'/'+path.split('/').map(encodeURIComponent).join('/'));
      xhr.setRequestHeader('apikey',config.publishableKey);xhr.setRequestHeader('Authorization','Bearer '+access);
      // 元の種類にかかわらず、クラウドでは実行できないダウンロード形式で保存する。
      xhr.setRequestHeader('Content-Type','application/octet-stream');xhr.setRequestHeader('x-upsert','false');xhr.setRequestHeader('cache-control','no-store');
      xhr.timeout=15*60*1000;
      xhr.upload.onprogress=e=>{if(e.lengthComputable)onProgress(Math.min(99,Math.round(e.loaded/e.total*100)));};
      xhr.onerror=()=>reject(new Error('ネットワークエラー。接続を確認してください。'));
      xhr.ontimeout=()=>reject(new Error('アップロードがタイムアウトしました。一覧を更新して完了済みか確認してください。'));
      xhr.onload=()=>{if(xhr.status>=200&&xhr.status<300)return resolve();let msg='アップロードエラー ('+xhr.status+')';try{const d=JSON.parse(xhr.responseText);msg=d.message||d.error||msg;}catch{}const e=new Error(msg);e.status=xhr.status;reject(e);};
      xhr.send(file);
    });
  }
  async function uploadFiles(input) {
    if(!input.length)return;
    if(busy)return notify('現在のアップロードが終わってから追加してください。');
    if(!uploadEnabled())return chooseFiles();
    const incoming=Array.from(input);
    if(incoming.length>100)return notify('一度に選べるファイルは100個までです。',true);
    busy=true;showAccount();$('uploads').hidden=false;$('queue-list').replaceChildren();
    const queue=incoming.map(file=>{const item=node('div',undefined,'queue-item'),label=node('span',file.name+' · '+formatSize(file.size)),status=node('span','待機中','queue-status'),progress=node('progress');progress.max=100;progress.value=0;progress.setAttribute('aria-label',file.name+'の進捗');item.append(label,status,progress);$('queue-list').append(item);return {file,status,progress};});
    let next=0,success=0;
    async function worker() {
      while(next<queue.length) {
        const {file,status,progress}=queue[next++];let reserved=null;
        try {
          if(!file.size || file.size>Math.min(MAX_FILE,usage?.file_limit||MAX_FILE))throw new Error('空のファイル、または50 MBを超えるファイルはアップロードできません。');
          if(file.name.length>255 || /[\x00-\x1f\x7f]/.test(file.name))throw new Error('ファイル名を255文字以内にし、制御文字を含めないでください。');
          status.textContent='容量を確認中';
          reserved=await rpc('transfer_reserve',{p_filename:file.name,p_size:file.size,p_mime:file.type||'application/octet-stream'});
          // PostgRESTのバージョンにより複合型が配列になる場合にも対応。
          if(Array.isArray(reserved))reserved=reserved[0];
          if(!reserved?.id || !reserved?.object_path)throw new Error('容量予約の応答が不正です。supabase.sqlを確認してください。');
          status.textContent='0%';
          await uploadXHR(file,reserved.object_path,await token(),value=>{progress.value=value;status.textContent=value+'%';});
          progress.value=100;status.textContent='保存完了';success++;
        } catch(error) {
          status.textContent=friendly(error);status.style.color='var(--red)';
          // 応答消失でも保存済みの実体があればSQL側は取消しない。
          if(reserved?.id)try{await rpc('transfer_cancel',{p_id:reserved.id});}catch{}
        }
      }
    }
    try {await Promise.all([worker(),worker()]);notify(`${incoming.length}件中${success}件をクラウドに保存しました。${success<incoming.length?'失敗したファイルの表示を確認してください。':''}`,success<incoming.length);}
    finally {busy=false;$('file-input').value='';await reload();showAccount();}
  }
  function filePath(file) {return BUCKET+'/'+file.object_path.split('/').map(encodeURIComponent).join('/');}
  async function signed(file,seconds) {
    const data=await api('/storage/v1/object/sign/'+filePath(file),{method:'POST',body:JSON.stringify({expiresIn:seconds})});
    const value=data.signedURL||data.signedUrl;
    if(!value)throw new Error('共有URLを作成できませんでした。');
    const url=new URL(value.startsWith('/storage/v1/')?base+value:value.startsWith('/')?base+'/storage/v1'+value:value);
    if(url.origin!==base || url.protocol!=='https:')throw new Error('共有URLの接続先が不正です。');
    url.searchParams.set('download',file.filename);return url.href;
  }
  async function fileBlob(file) {
    const access=await token();
    const response=await fetch(base+'/storage/v1/object/authenticated/'+filePath(file)+'?fresh='+crypto.randomUUID(),{headers:{apikey:config.publishableKey,Authorization:'Bearer '+access},cache:'no-store'});
    if(!response.ok)await parseResponse(response);
    return response.blob();
  }
  async function download(file) {
    try {
      notify('ダウンロードを準備しています…');
      const blob=await fileBlob(file),url=URL.createObjectURL(new Blob([blob],{type:'application/octet-stream'}));
      const a=node('a');a.href=url;a.download=file.filename;a.rel='noopener';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      notify('ダウンロードを開始しました。');
    }catch(error){notify(friendly(error),true);}
  }
  function clearPreview() {previewSequence++;if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;$('preview-content').replaceChildren();}
  async function preview(file) {
    clearPreview();$('preview-title').textContent=file.filename;$('preview-content').textContent='読み込み中…';$('preview-dialog').showModal();
    const epoch=viewEpoch, sequence=previewSequence;
    const previewType=imageExt.has(ext(file.filename))?'image':ext(file.filename)==='pdf'?'pdf':textExt.has(ext(file.filename))?'text':null;
    if(!previewType || file.size_bytes>PREVIEW_LIMIT) {$('preview-content').textContent=!previewType?'この形式はプレビューに対応していません。ダウンロードして開いてください。':'プレビューは10 MBまでです。ダウンロードして開いてください。';return;}
    try {
      const blob=await fileBlob(file);
      if(epoch!==viewEpoch || sequence!==previewSequence || !$('preview-dialog').open)return;
      if(previewType==='text') {
        const text=await blob.slice(0,1000000).text();if(sequence!==previewSequence || !$('preview-dialog').open)return;
        $('preview-content').replaceChildren(node('pre',text+(blob.size>1000000?'\n…先頭1 MBのみ表示しています。':'')));
      } else {
        previewUrl=URL.createObjectURL(new Blob([blob],{type:previewType==='pdf'?'application/pdf':({jpg:'image/jpeg',jpeg:'image/jpeg',png:'image/png',gif:'image/gif',webp:'image/webp',avif:'image/avif'})[ext(file.filename)]}));
        const content=node(previewType==='image'?'img':'iframe');content.src=previewUrl;
        if(previewType==='image'){content.alt=file.filename;content.onerror=()=>{$('preview-content').textContent='画像として開けません。ダウンロードしてください。';};}
        else {content.title=file.filename;content.setAttribute('sandbox','allow-same-origin');content.referrerPolicy='no-referrer';}
        $('preview-content').replaceChildren(content);
      }
    }catch(error){$('preview-content').textContent=friendly(error);}
  }
  function openShare(file) {sharing=file;$('share-name').textContent=file.filename;$('share-result').hidden=true;$('share-url').value='';$('share-dialog').showModal();}
  async function createShare() {
    if(!sharing)return;$('create-share').disabled=true;$('share-result').hidden=true;
    try {const seconds=Number($('share-duration').value);$('share-url').value=await signed(sharing,seconds);$('share-expires').textContent='有効期限の目安：'+date(new Date(Date.now()+seconds*1000));$('share-result').hidden=false;}
    catch(error){notify(friendly(error),true);}finally{$('create-share').disabled=false;}
  }
  function confirmDelete(list) {
    $('confirm-message').textContent=list.length===1?`「${list[0].filename}」をクラウドから削除します。`:`選択した${list.length}件をクラウドから削除します。`;
    $('confirm-dialog').showModal();return new Promise(resolve=>{dialogResolve=resolve;});
  }
  async function deleteFiles(list) {
    if(!list.length || busy)return notify('アップロードが終わってから削除してください。');
    if(!await confirmDelete(list))return;
    $('delete-selected').disabled=true;
    let done=0;
    try {
      // 1リクエスト100件まで。一部成功後の失敗でも実際の一覧を再取得する。
      for(let i=0;i<list.length;i+=100){const part=list.slice(i,i+100);await api('/storage/v1/object/'+BUCKET,{method:'DELETE',body:JSON.stringify({prefixes:part.map(f=>f.object_path)})});done+=part.length;part.forEach(f=>selected.delete(f.id));}
      notify(done+'件を削除しました。');
    } catch(error){notify(`${done}件の削除要求が完了しました。\n`+friendly(error),true);}
    finally{$('delete-selected').disabled=false;await reload();}
  }
  async function authenticate(mode) {
    const email=$('email').value.trim(),password=$('password').value;
    if(!$('email').reportValidity() || (mode!=='recover'&&!$('password').reportValidity()))return;
    ['login','signup','recover'].forEach(id=>{$(id).disabled=true;});
    try {
      const redirect=location.origin+location.pathname;
      if(mode==='recover') {await raw('/auth/v1/recover?redirect_to='+encodeURIComponent(redirect),{method:'POST',body:JSON.stringify({email})});notify('該当するアカウントがある場合、パスワード再設定メールが届きます。');return;}
      const data=await raw(mode==='signup'?'/auth/v1/signup?redirect_to='+encodeURIComponent(redirect):'/auth/v1/token?grant_type=password',{method:'POST',body:JSON.stringify({email,password})});
      if(!data.access_token){notify('確認メールのリンクを開いて登録を完了し、この画面でログインしてください。');return;}
      acceptSession(data);viewEpoch++;$('password').value='';showAccount();await reload();notify('ログインしました。');
    }catch(error){notify(friendly(error),true);}finally{['login','signup','recover'].forEach(id=>{$(id).disabled=!configured;});}
  }
  async function logout() {
    if(busy)return notify('アップロードが終わってからログアウトしてください。');
    try {if(session)await api('/auth/v1/logout',{method:'POST'});}
    catch(error){notify('サーバー側のログアウトを確認できませんでした。このPCのログイン情報は削除します。\n'+friendly(error),true);}
    finally{viewEpoch++;saveSession(null);selected.clear();clearPreview();document.querySelectorAll('dialog[open]').forEach(d=>d.close());$('share-url').value='';sharing=null;showAccount();}
  }
  function init() {
    try {
      const url=new URL(config.supabaseUrl);
      if(url.protocol!=='https:' || !/^[a-z0-9-]+\.supabase\.co$/.test(url.hostname) || url.pathname!=='/' || url.search || url.hash)throw new Error();
      let safeKey=/^sb_publishable_[A-Za-z0-9_-]+$/.test(config.publishableKey||'');
      if(!safeKey){try{const part=config.publishableKey.split('.')[1];const jwt=JSON.parse(atob(part.replace(/-/g,'+').replace(/_/g,'/')));safeKey=jwt.role==='anon';}catch{}}
      if(!safeKey || config.bucket!==BUCKET)throw new Error();base=url.origin;configured=true;
    }catch {configured=false;$('setup-notice').hidden=false;}
    $('auth-form').addEventListener('submit',e=>{e.preventDefault();authenticate('login');});
    $('signup').onclick=()=>authenticate('signup');$('recover').onclick=()=>authenticate('recover');$('logout').onclick=logout;
    $('upload-top').onclick=chooseFiles;$('drop-zone').onclick=chooseFiles;
    $('drop-zone').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseFiles();}};
    $('file-input').onchange=e=>uploadFiles(e.target.files);
    for(const event of ['dragenter','dragover'])$('drop-zone').addEventListener(event,e=>{e.preventDefault();if(uploadEnabled())$('drop-zone').classList.add('dragover');});
    $('drop-zone').ondragleave=()=>{$('drop-zone').classList.remove('dragover');};
    $('drop-zone').ondrop=e=>{e.preventDefault();$('drop-zone').classList.remove('dragover');if(uploadEnabled())uploadFiles(e.dataTransfer.files);else chooseFiles();};
    window.addEventListener('dragover',e=>e.preventDefault());window.addEventListener('drop',e=>e.preventDefault());
    $('refresh').onclick=()=>reload();$('search').oninput=()=>{page=1;renderFiles();};$('sort').onchange=()=>{page=1;renderFiles();};
    document.querySelectorAll('[data-filter]').forEach(button=>{button.onclick=()=>{filter=button.dataset.filter;page=1;document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b===button));$('files-heading').firstChild.textContent=button.textContent.replace(/[▦▧▤□]/g,'').trim()+' ';renderFiles();};});
    $('select-all').onchange=()=>{const list=visibleFiles().slice((page-1)*PAGE_SIZE,page*PAGE_SIZE);list.forEach(f=>$('select-all').checked?selected.add(f.id):selected.delete(f.id));renderFiles();};
    $('delete-selected').onclick=()=>deleteFiles(files.filter(f=>selected.has(f.id)));$('prev-page').onclick=()=>{page--;renderFiles();};$('next-page').onclick=()=>{page++;renderFiles();};
    document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());$('preview-dialog').addEventListener('close',clearPreview);
    $('confirm-cancel').onclick=()=>{$('confirm-dialog').close();};$('confirm-delete').onclick=()=>{const resolve=dialogResolve;dialogResolve=null;$('confirm-dialog').close();resolve?.(true);};$('confirm-dialog').addEventListener('close',()=>{dialogResolve?.(false);dialogResolve=null;});
    $('create-share').onclick=createShare;$('copy-share').onclick=async()=>{try{await navigator.clipboard.writeText($('share-url').value);notify('共有リンクをコピーしました。');}catch{$('share-url').select();notify('URLを選択しました。Ctrl+Cでコピーしてください。');}};
    $('password-form').onsubmit=async e=>{e.preventDefault();try{await api('/auth/v1/user',{method:'PUT',body:JSON.stringify({password:$('new-password').value})});$('new-password').value='';$('password-dialog').close();notify('パスワードを更新しました。');}catch(error){notify(friendly(error),true);}};
    document.addEventListener('visibilitychange',()=>{if(!document.hidden&&session&&!busy)reload(true);});
    window.addEventListener('beforeunload',e=>{if(busy){e.preventDefault();e.returnValue='';}});
    showAccount();startSession();
  }
  async function startSession() {
    if(!configured)return;
    try {
      const params=new URLSearchParams(location.hash.slice(1));
      if(params.has('error_description')){const message=params.get('error_description');history.replaceState(null,'',location.pathname+location.search);throw new Error(message);}
      if(params.get('access_token')&&params.get('refresh_token')) {
        acceptSession({access_token:params.get('access_token'),refresh_token:params.get('refresh_token'),expires_in:Number(params.get('expires_in'))||3600});
        history.replaceState(null,'',location.pathname+location.search);
      } else {try{const stored=sessionStorage.getItem(SESSION_KEY);if(stored)session=JSON.parse(stored);}catch{session=null;}}
      if(session){const user=await api('/auth/v1/user');session.user=user;saveSession(session);showAccount();await reload();if(params.get('type')==='recovery')$('password-dialog').showModal();}
    }catch(error){saveSession(null);showAccount();notify(friendly(error),true);}
  }
  init();
})();
