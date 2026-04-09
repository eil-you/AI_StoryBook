python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
Write-Host "가상환경이 생성되고 라이브러리가 설치되었습니다. 가상환경 활성화 후 __uvicorn app.main:app --reload --port 8000__ 로 실행하세요."