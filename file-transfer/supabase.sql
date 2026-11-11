-- Relay / Supabase Free専用プロジェクト用。SQL Editorで全体を1回実行。
-- 実行前にREADME.mdを読むこと。Freeの組織で使い、有料へ変更しない。
begin;
create schema if not exists transfer_private;
revoke all on schema transfer_private from public, anon, authenticated;

create table if not exists public.transfer_settings (
 id boolean primary key default true check (id),
 uploads_enabled boolean not null default true,
 stop_reason text not null default '管理者がアップロードを停止しています。',
 storage_limit bigint not null default 800000000 check(storage_limit between 1 and 800000000),
 file_limit bigint not null default 50000000 check(file_limit between 1 and 50000000),
 db_limit bigint not null default 400000000 check(db_limit between 1 and 400000000),
 file_count_limit integer not null default 10000 check(file_count_limit between 1 and 10000)
);
insert into public.transfer_settings(id) values(true) on conflict do nothing;
alter table public.transfer_settings enable row level security;
revoke all on public.transfer_settings from anon, authenticated;

create table if not exists public.transfer_files (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references auth.users(id),
 filename text not null check(char_length(filename) between 1 and 255),
 size_bytes bigint not null check(size_bytes between 1 and 50000000),
 mime_type text not null check(char_length(mime_type) between 1 and 255),
 status text not null default 'pending' check(status in ('pending','ready')),
 created_at timestamptz not null default now(),
 object_path text generated always as (owner_id::text || '/' || id::text) stored,
 unique(object_path)
);
create index if not exists transfer_files_owner_date on public.transfer_files(owner_id,created_at desc);
alter table public.transfer_files enable row level security;
revoke all on public.transfer_files from anon, authenticated;
grant select on public.transfer_files to authenticated;
drop policy if exists transfer_files_own on public.transfer_files;
create policy transfer_files_own on public.transfer_files for select to authenticated
 using (owner_id=(select auth.uid()));

-- 読み取りだけの公開RPC。全体の使用量のみ返し、他人のファイル名等は返さない。
create or replace function transfer_private.usage_for_owner(p_owner uuid) returns jsonb
language plpgsql security definer set search_path='' as $$
declare cfg public.transfer_settings; used bigint; own_bytes bigint; db_bytes bigint; other_bytes bigint; n bigint;
begin
 select * into strict cfg from public.transfer_settings where id;
 select coalesce(sum(size_bytes),0), coalesce(sum(size_bytes) filter(where owner_id=p_owner),0),count(*)
 into used,own_bytes,n from public.transfer_files;
 -- このアプリ以外のバケットも容量として数える。専用プロジェクトで利用すること。
 select coalesce(sum((metadata->>'size')::bigint),0) into other_bytes from storage.objects where bucket_id<>'pc-transfer';
 used:=used+other_bytes;
 db_bytes:=pg_catalog.pg_database_size(pg_catalog.current_database());
 return jsonb_build_object('used_bytes',used,'own_bytes',own_bytes,'limit_bytes',cfg.storage_limit,
 'file_limit',cfg.file_limit,'db_bytes',db_bytes,'db_limit',cfg.db_limit,'file_count',n,
 'uploads_enabled',cfg.uploads_enabled and used<cfg.storage_limit and db_bytes<cfg.db_limit and n<cfg.file_count_limit,
 'reason',case when not cfg.uploads_enabled then cfg.stop_reason when db_bytes>=cfg.db_limit then 'データベースの安全上限に達しました。管理者が使用量を確認してください。'
 when n>=cfg.file_count_limit then 'ファイル件数の上限に達しました。不要なファイルを削除してください。'
 when used>=cfg.storage_limit then '保存容量の安全上限に達しました。不要なファイルを削除してください。' else '' end);
end $$;

create or replace function public.transfer_usage() returns jsonb
language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null then raise exception 'ログインが必要です。' using errcode='42501'; end if;
 return transfer_private.usage_for_owner(auth.uid());
end $$;


-- 容量を先に予約。並行アップロードでも全員共通のロックで判定する。
create or replace function public.transfer_reserve(p_filename text,p_size bigint,p_mime text) returns public.transfer_files
language plpgsql security definer set search_path='' as $$
declare u jsonb; result public.transfer_files;
begin
 if auth.uid() is null then raise exception 'ログインが必要です。' using errcode='42501'; end if;
 perform pg_catalog.pg_advisory_xact_lock(7291142026);
 -- 24時間以上経過し、実体がない予約だけを回収。クラウド保存済みのファイルは消さない。
 delete from public.transfer_files f where f.status='pending' and f.created_at<now()-interval '24 hours'
 and not exists(select 1 from storage.objects o where o.bucket_id='pc-transfer' and o.name=f.object_path);
 u:=public.transfer_usage();
 if not (u->>'uploads_enabled')::boolean then raise exception '%',u->>'reason'; end if;
 if p_size is null or p_size<1 or p_size>(u->>'file_limit')::bigint then raise exception '1ファイルは1バイト以上50 MB以下にしてください。'; end if;
 if p_filename is null or char_length(p_filename) not between 1 and 255 or p_filename ~ '[[:cntrl:]]' then raise exception 'ファイル名が無効です。'; end if;
 if p_mime is null or char_length(p_mime) not between 1 and 255 then raise exception 'ファイルの種類が無効です。'; end if;
 if (u->>'used_bytes')::bigint+p_size>(u->>'limit_bytes')::bigint then raise exception '空き容量が不足しています。不要なファイルを削除してください。'; end if;
 insert into public.transfer_files(owner_id,filename,size_bytes,mime_type) values(auth.uid(),p_filename,p_size,p_mime) returning * into result;
 return result;
end $$;

create or replace function public.transfer_cancel(p_id uuid) returns void
language plpgsql security definer set search_path='' as $$
begin
 if auth.uid() is null then raise exception 'ログインが必要です。' using errcode='42501'; end if;
 perform pg_catalog.pg_advisory_xact_lock(7291142026);
 delete from public.transfer_files f where f.id=p_id and f.owner_id=auth.uid() and f.status='pending'
 and not exists(select 1 from storage.objects o where o.bucket_id='pc-transfer' and o.name=f.object_path);
end $$;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
 values('pc-transfer','pc-transfer',false,50000000,array['application/octet-stream'])
 on conflict(id) do update set public=false,file_size_limit=50000000,allowed_mime_types=array['application/octet-stream'];

-- アップロードされた実サイズを検証し、改ざんや未予約の書き込みを拒否する。
create or replace function transfer_private.guard_object() returns trigger
language plpgsql security definer set search_path='' as $$
declare f public.transfer_files; actual_size bigint; u jsonb;
begin
 if new.bucket_id<>'pc-transfer' then return new; end if;
 perform pg_catalog.pg_advisory_xact_lock(7291142026);
 select * into f from public.transfer_files where object_path=new.name for update;
 if not found then raise exception '有効な容量予約がありません。'; end if;
 if tg_op='INSERT' and f.status<>'pending' then raise exception '上書きは許可されていません。'; end if;
 u:=transfer_private.usage_for_owner(f.owner_id);
 if (u->>'used_bytes')::bigint>(u->>'limit_bytes')::bigint then raise exception '保存容量の上限を超えています。'; end if;
 if not (select uploads_enabled from public.transfer_settings where id) then raise exception '管理者がアップロードを停止しています。'; end if;
 if (u->>'db_bytes')::bigint>=(u->>'db_limit')::bigint then raise exception 'データベース容量の上限に達しました。'; end if;
 actual_size:=(new.metadata->>'size')::bigint;
 -- Storageは送信前の権限確認でもINSERTを試行し、直後にロールバックする。
 -- その時点では実サイズ未確定。予約は維持し、readyにはしない。
 if tg_op='INSERT' and actual_size is null and f.status='pending' then return new; end if;
 if actual_size is null or actual_size<>f.size_bytes then raise exception '予約容量と実ファイルの容量が一致しません。'; end if;
 if coalesce(new.metadata->>'mimetype','')<>'application/octet-stream' then raise exception '安全なダウンロード形式でアップロードしてください。'; end if;
 update public.transfer_files set status='ready' where id=f.id;
 return new;
end $$;
create or replace function transfer_private.remove_record() returns trigger
language plpgsql security definer set search_path='' as $$
begin
 if old.bucket_id='pc-transfer' then
  perform pg_catalog.pg_advisory_xact_lock(7291142026);
  delete from public.transfer_files where object_path=old.name;
 end if;
 return old;
end $$;
drop trigger if exists transfer_guard on storage.objects;
create trigger transfer_guard before insert or update on storage.objects for each row execute function transfer_private.guard_object();
drop trigger if exists transfer_remove on storage.objects;
create trigger transfer_remove after delete on storage.objects for each row execute function transfer_private.remove_record();

-- RLSのデフォルト拒否を維持。既存の広いStorageポリシーがない専用プロジェクトで実行する。
drop policy if exists transfer_insert on storage.objects;
create policy transfer_insert on storage.objects for insert to authenticated with check (
 bucket_id='pc-transfer' and (storage.foldername(name))[1]=(select auth.uid())::text
 and exists(select 1 from public.transfer_files f where f.object_path=name and f.owner_id=(select auth.uid()) and f.status='pending')
);
drop policy if exists transfer_select on storage.objects;
create policy transfer_select on storage.objects for select to authenticated using (
 bucket_id='pc-transfer' and (storage.foldername(name))[1]=(select auth.uid())::text
 and exists(select 1 from public.transfer_files f where f.object_path=name and f.owner_id=(select auth.uid()) and f.status='ready')
);
drop policy if exists transfer_delete on storage.objects;
create policy transfer_delete on storage.objects for delete to authenticated using (
 bucket_id='pc-transfer' and (storage.foldername(name))[1]=(select auth.uid())::text
);
-- UPDATEポリシーは作らない。匿名SELECT・INSERTも作らない。
revoke all on function public.transfer_usage() from public,anon;
revoke all on function public.transfer_reserve(text,bigint,text) from public,anon;
revoke all on function public.transfer_cancel(uuid) from public,anon;
grant execute on function public.transfer_usage() to authenticated;
grant execute on function public.transfer_reserve(text,bigint,text) to authenticated;
grant execute on function public.transfer_cancel(uuid) to authenticated;
revoke all on function transfer_private.usage_for_owner(uuid) from public,anon,authenticated;
revoke all on function transfer_private.guard_object() from public,anon,authenticated;
revoke all on function transfer_private.remove_record() from public,anon,authenticated;
commit;
