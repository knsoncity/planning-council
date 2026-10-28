import argparse
from pathlib import Path
import shutil
import sys

FILES = ['server.py','launcher.py','실행.command','연결 확인.command','Claude 초기 설정.command',
         '시작 안내.html','static/index.html','static/app.js','static/style.css',
         'skills/planning-council/SKILL.md','MANIFEST.json']
MARKER='.council-install'

def install(source, target):
    source,target=Path(source),Path(target)
    if target.is_symlink() or (target.exists() and not (target/MARKER).is_file()):
        raise ValueError('설치 대상에 다른 폴더가 있습니다. 기존 폴더를 확인하세요.')
    for rel in FILES:
        if not (source/rel).is_file() or (source/rel).is_symlink():
            raise ValueError('설치 파일이 누락되거나 올바르지 않습니다: '+rel)
    target.mkdir(parents=True,exist_ok=True)
    for rel in FILES:
        dst=target/rel
        if dst.is_symlink() or any(p.is_symlink() for p in dst.parents if p == target or target in p.parents):
            raise ValueError('심볼릭 링크가 있는 경로에는 설치하지 않습니다.')
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/rel,dst)
    (target/MARKER).write_text('AI Meeting Room macOS\n')
    return target

def main():
    if sys.platform!='darwin':
        raise SystemExit('macOS 전용 설치본입니다.')
    target=Path.home()/'Applications/AI Meeting Room'
    result=install(Path(__file__).resolve().parent,target)
    print(f'설치 완료: {result}\n연결 확인.command → Claude 초기 설정.command → 실행.command 순서로 진행하세요.')
    print('업데이트해도 회의 기록은 Application Support에 별도로 보존됩니다.')
    import subprocess
    subprocess.run(['open',str(result)],check=False)

if __name__=='__main__':
    try: main()
    except (OSError,ValueError) as error:
        print('설치 실패:',error)
        raise SystemExit(1)
