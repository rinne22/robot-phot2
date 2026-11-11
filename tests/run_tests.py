#!/usr/bin/env python3
"""Build the entire actual sketch with host Arduino/IR mocks; no source function copies."""
from pathlib import Path
import re, subprocess, tempfile, sys
root=Path(__file__).resolve().parents[1]
variant='--front-stop' in sys.argv
s=(root/('design-guide/robot_front_stop.ino' if variant else 'robot_final.ino')).read_text()
# Arduino normally inserts prototypes. Insert them after the DriveState enum for host C++.
sigs=re.findall(r'^((?:void|bool|int|unsigned int|DriveState) \w+\([^\n]*\))\s*\{',s,re.M)
pos=s.index('DriveState Drive_Num')
s=s[:pos]+'\n'.join(x+';' for x in sigs)+'\n'+s[pos:]
with tempfile.TemporaryDirectory() as tmp:
 Path(tmp,'generated-sketch.hpp').write_text(s)
 subprocess.run(['g++',*(['-DFRONT_STOP_VARIANT'] if variant else []),'-std=c++17','-Wall','-Wextra','-Werror','-I'+str(root/'tests/stubs'),'-I'+tmp,str(root/'tests/robot_test.cpp'),'-o',tmp+'/test'],check=True)
 subprocess.run([tmp+'/test'],check=True)
