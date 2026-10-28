"""Build a private-data-free distribution using an explicit file allowlist."""
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
BOOT='''#!/bin/zsh
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
PYTHON=""
for candidate in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  print "Python 3.10 이상이 필요합니다. https://www.python.org/downloads/macos/"
  read "?Enter를 누르면 종료합니다."
  exit 1
fi
"$PYTHON" TARGET
status_code=$?
if (( status_code != 0 )); then
  print "오류가 발생했습니다. 위 안내를 확인하세요."
fi
read "?Enter를 누르면 창을 닫습니다."
exit $status_code
'''
def build():
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='council-build-') as tmp:
        root=Path(tmp)/'AI-Meeting-Room-macOS'
        root.mkdir()
        for name in ('server.py','static/index.html','static/style.css','static/app.js'):
            dst=root/name;dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,dst)
        for name in ('install.py','launcher.py','시작 안내.html'):
            shutil.copy2(ROOT/'distribution'/name,root/name)
        # Build only the reviewed, bundled skill; never read private user configuration.
        skill=(ROOT/'skills/planning-council/SKILL.md').read_text()
        dst=root/'skills/planning-council/SKILL.md'
        dst.parent.mkdir(parents=True);dst.write_text(skill)
        for name,target in {'설치.command':'install.py','실행.command':'launcher.py',
                            '연결 확인.command':'launcher.py --check',
                            'Claude 초기 설정.command':'launcher.py --configure-claude'}.items():
            p=root/name;p.write_text(BOOT.replace('TARGET',target));p.chmod(0o755)
        manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(root.rglob('*')) if p.is_file()}
        (root/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        archive=OUT/'AI-Meeting-Room-macOS.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(root.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(root.parent))
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        (OUT/'AI-Meeting-Room-macOS.sha256').write_text(digest+'  '+archive.name+'\n')
        print(archive)
        print(f'{archive.stat().st_size:,} bytes; {len(manifest)+1} files')
        return archive

if __name__=='__main__': build()
