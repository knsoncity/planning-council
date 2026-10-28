#!/bin/zsh
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
"$PYTHON" launcher.py
status_code=$?
if (( status_code != 0 )); then
  print "오류가 발생했습니다. 위 안내를 확인하세요."
fi
read "?Enter를 누르면 창을 닫습니다."
exit $status_code
