"""macOS team launcher. No subscription credential copying or key persistence."""
import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
PORT = 8876
SUPPORT = Path.home() / 'Library/Application Support/AI Meeting Room'

def environment(root, openai_key='', claude_key=''):
    # No inherited provider credentials, alternate API endpoints or shell startup state.
    env = {k: os.environ[k] for k in ('HOME','USER','LOGNAME','PATH','LANG','LC_ALL','TMPDIR','SHELL') if k in os.environ}
    env.update(CODEX_HOME=str(root/'codex'), CLAUDE_CONFIG_DIR=str(root/'claude'),
               COUNCIL_SKILL_PATH=str(ROOT/'skills/planning-council/SKILL.md'), COUNCIL_API_ONLY='1')
    if openai_key:
        env['OPENAI_API_KEY'] = openai_key
    if claude_key:
        env['ANTHROPIC_API_KEY'] = claude_key
    for name in ('codex','claude'):
        (root/name).mkdir(mode=0o700, parents=True, exist_ok=True)
    return env

def check_tools():
    required = {'codex': ('exec','--help', ['--ignore-user-config','--output-schema','--ephemeral']),
                'claude': ('--help', None, ['--safe-mode','--strict-mcp-config','--no-session-persistence'])}
    good = True
    for name, (arg, extra, flags) in required.items():
        path = shutil.which(name)
        if not path:
            print(f'[설치 필요] {name}: 시작 안내.html의 공식 설치 링크를 확인하세요.')
            good = False
            continue
        try:
            r = subprocess.run([path,arg]+([extra] if extra else []), capture_output=True, text=True, timeout=20)
            supported = r.returncode == 0 and all(flag in r.stdout+r.stderr for flag in flags)
        except (OSError, subprocess.TimeoutExpired):
            supported = False
        print(f'[{("사용 가능" if supported else "업데이트 필요")}] {name}')
        good &= supported
    print('검사는 프로그램과 필요한 옵션의 존재만 확인합니다. 계정·잔액·모델 접근은 실제 실행 때 확인됩니다.')
    return good

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--configure-claude', action='store_true')
    args=parser.parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('이 배포본은 macOS용입니다.')
    if not check_tools():
        webbrowser.open((ROOT/'시작 안내.html').as_uri())
        return 1
    if args.check:
        return 0
    SUPPORT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.configure_claude:
        key=getpass.getpass('본인/회사 Claude API 키 (화면에 표시되지 않음): ').strip()
        if not key:
            return 1
        print('Claude가 열리면 API 키 인증을 선택하고 초기 설정을 마친 뒤 /exit로 종료하세요.')
        # Native onboarding handles API-key trust. No fabricated consent settings.
        env=environment(SUPPORT/'auth')
        env['ANTHROPIC_API_KEY']=key
        return subprocess.call(['claude','--safe-mode'],env=env,cwd=ROOT)
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/bootstrap',timeout=2) as response:
            existing=json.load(response)
        if existing.get('app')=='personal-council-v1':
            print('이미 실행 중인 회의실을 엽니다.')
            webbrowser.open(f'http://127.0.0.1:{PORT}')
            return 0
    except (OSError,ValueError):
        pass
    print('\nAPI 사용량은 ChatGPT/Claude 구독과 별도로 과금됩니다.')
    print('입력한 키는 앱 설정 파일에 저장하지 않으며 이 실행에만 사용합니다.')
    openai_key=getpass.getpass('본인/회사 OpenAI API 키: ').strip()
    claude_key=getpass.getpass('본인/회사 Claude API 키: ').strip()
    if not openai_key or not claude_key:
        print('두 키가 모두 필요합니다. 회의실을 시작하지 않았습니다.')
        return 1
    # Codex auth is temporary and never touches the user's normal Codex account.
    with tempfile.TemporaryDirectory(prefix='council-auth-') as temp:
        env=environment(Path(temp),openai_key,claude_key)
        env['CLAUDE_CONFIG_DIR']=str(SUPPORT/'auth/claude')
        Path(env['CLAUDE_CONFIG_DIR']).mkdir(parents=True,exist_ok=True,mode=0o700)
        login=subprocess.run(['codex','-c','cli_auth_credentials_store="file"','login','--with-api-key'],input=openai_key+'\n',
                             text=True,capture_output=True,env=env,timeout=30)
        if login.returncode:
            print('Codex API 키 등록 실패. 공식 CLI 설치 및 API 키를 확인하세요.')
            return 1
        print(f'회의실: http://127.0.0.1:{PORT}\n종료: 이 창에서 Control+C')
        try:
            return subprocess.call([sys.executable,str(ROOT/'server.py'),'--open','--port',str(PORT),
                                    '--data',str(SUPPORT/'data')],env=env,cwd=ROOT)
        except KeyboardInterrupt:
            return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (EOFError, KeyboardInterrupt):
        print('\n취소했습니다.')
    except (OSError, subprocess.TimeoutExpired):
        print('실행에 실패했습니다. 연결 확인.command와 시작 안내.html을 확인하세요.')
        raise SystemExit(1)
