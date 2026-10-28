# Planning Council · 우리의 AI 회의실

기획·사업·디자인·개발이 독립 검토하고 서로 반박한 뒤, CBO가 결론과 팀별 역할·업무 순서를 정리하는 macOS 회의실입니다.

## macOS 설치본 다운로드

**[AI-Meeting-Room-macOS.zip 다운로드](https://github.com/knsoncity/planning-council/raw/refs/heads/main/dist/AI-Meeting-Room-macOS.zip)**

[SHA-256 확인 파일](dist/AI-Meeting-Room-macOS.sha256) · [설치 안내](시작%20안내.html)

1. ZIP을 내려받아 압축을 풉니다.
2. Python 3.10 이상, Codex CLI, Claude Code를 설치합니다. 공식 링크는 ZIP의 `시작 안내.html`에 있습니다.
3. `설치.command`를 더블클릭합니다. `~/Applications/AI Meeting Room`에 설치됩니다.
4. 설치 폴더에서 `연결 확인.command`와 `Claude 초기 설정.command`를 실행합니다.
5. `실행.command`를 열고 본인 또는 회사의 OpenAI·Claude API 키를 입력합니다.
6. 브라우저의 `http://127.0.0.1:8876`에서 새 안건을 시작합니다.

Apple 서명·공증된 앱이 아닌 Python/CLI 기반 시험 배포본입니다. macOS가 실행을 차단하면 배포자를 확인하고 시스템 설정의 해당 파일 실행 허용 절차를 따르세요. 전체 보안 기능을 끄지 마세요.

## 주요 기능

- 기본 간단 회의: 대표 4명 검토 + 교차 토론 4회 + CBO 1회, 총 9회 호출.
- 전체 회의: 팀원 20명 검토 + 팀 내 반박 20회 + 팀 간 토론 20회 + CBO 1회, 총 61회 호출.
- 원탁에서 실제 발언·반론 대상·근거·판단 변경 확인.
- 쉬운 말로 내 의견 → 이유 → 할 일 정리.
- CBO 종합 판단과 팀별 책임·전달할 자료·시작 조건·업무 순서.
- 로컬 저장, 실패 단계 재시도, 회의 내보내기.

## 비용과 계정

**API 요금은 ChatGPT/Claude 월 구독과 별도입니다.** 각 사용자가 본인 또는 회사의 키를 사용합니다. API 잔액과 모델 접근 권한이 필요합니다.

- 입력한 키는 화면에 표시하거나 앱 설정 파일에 저장하지 않습니다.
- Codex는 실행 전용 임시 인증 폴더를 사용하며 개인 로그인 파일을 복사하지 않습니다. 강제 종료 시 임시 파일이 남을 수 있습니다.
- Claude 초기 설정은 회의실 전용 폴더에 남습니다.
- 안건과 토론 내용은 해당 AI 서비스로 전송됩니다.
- 앱 자체의 금액 상한 기능은 아직 없습니다. 먼저 간단 회의로 사용량을 확인하세요.

[OpenAI 인증 안내](https://learn.chatgpt.com/docs/auth) · [Claude 개발자 인증 안내](https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account)

## 기록과 공유

회의 기록은 `~/Library/Application Support/AI Meeting Room/data`에 저장됩니다. 팀원 간 자동 동기화·공동 편집은 없습니다. 필요한 회의만 내보내서 공유하세요.

저장소와 ZIP에는 제작자의 인증정보·실제 회의·회사별 맥락이 포함되지 않습니다. 범용 지침은 [planning-council 스킬](skills/planning-council/SKILL.md)에 있습니다.

## 검증 범위

- 설치·업데이트 보존, 배포 포함 목록, 인증 환경 분리, 회의 실행·재시도 로직을 검사했습니다.
- Codex 0.163.0 / Claude Code 2.1.304 환경에서 필요한 옵션을 확인했습니다.
- 신규 팀원의 API 키·결제·모델 접근 및 다른 Mac에서 실제 유료 호출은 검증하지 않았습니다.
- 연결 확인은 설치와 옵션 검사입니다. 첫 실제 회의에서 API 접근을 확인하세요.
- macOS 전용입니다. 업데이트 전 실행 중인 회의실을 종료하세요. 기록은 설치 폴더와 분리되어 보존됩니다.

## 개발과 재빌드

Python 표준 라이브러리만 사용합니다.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_macos.py
```

빌드는 명시된 파일만 포함합니다. data, auth, .env, 개인 회의와 캡처는 배포하지 않습니다. GitHub 소스 ZIP을 내려받았다면 루트의 설치.command도 사용할 수 있습니다.
