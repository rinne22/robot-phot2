#!/usr/bin/env python3
"""Create a deterministic source ZIP; never includes runtime sessions or credentials."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
files=['index.html','style.css','app.js','config.js','supabase.sql','setup.html','README.md','TESTING.md']
with zipfile.ZipFile(root/'file-transfer/relay-source.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
 for name in files:
  info=zipfile.ZipInfo('file-transfer/'+name,date_time=(2026,11,11,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
  z.writestr(info,(root/'file-transfer'/name).read_bytes())
print('Packaged 8 implementation and setup files')
