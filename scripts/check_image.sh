#!/usr/bin/env sh
# 공개로 올릴 이미지에 키·개인 파일이 없는지 확인한다 (v0.6.2 N4, D3). 있으면 이름을 보이고 실패한다.
# 사용: sh scripts/check_image.sh 이미지이름
set -eu
image="$1"
found=$(docker run --rm --entrypoint sh "$image" -c '
  cd /app
  for name in .env .env.local service_account.json profile.yaml profile.md data; do
    [ -e "$name" ] && echo "$name"
  done
  find . -name "*.json" -not -path "./.streamlit/*"
  true
')
if [ -n "$found" ]; then
  echo "이미지에 넣으면 안 되는 파일이 있음 ($image):"
  echo "$found"
  exit 1
fi
echo "비밀 파일 없음: $image"
