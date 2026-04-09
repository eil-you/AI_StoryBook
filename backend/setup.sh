#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "가상환경이 생성되고 라이브러리가 설치되었습니다. 가상환경 활성화 후 __uvicorn app.main:app --reload --port 8000__ 로 실행하세요."