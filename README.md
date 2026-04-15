<H1>📘 [PROJECT] AI StoryBook : 나만의 동화책 제작 서비스</H1>

### " 단 한번의 클릭으로 아이의 꿈을 현실로, AI 맞춤형 동화 제작 및 인쇄 서비스"

- **타겟 고객**: 자녀에게 특별한 선문을 주고 싶은 부모님, 조카의 성장 과정을 동화로 남기고 싶은 가족 사용자.
  
- **주요 기능 목록**:
  - **AI 스토리 생성**: 아이의 이름, 키워드를 반영한 맞춤형 시나리오 생성.
  - **AI 삽화 생성**: 각 페이지 테마에 맞는 고품질 이미지 자동 생성.
  - **고해상도 미리보기**: 실제 인쇄될 템플릿과 레이아웃을 실시간으로 확인.
  - **주문/결제 연동**: 실제 인쇄소와 연동되어 실물 도서 제작 및 주문취소/조회 기능 제공.
&nbsp;&nbsp;
<h2>💻 실행 방법</h2>

> **사전 요구사항**: Python 3.12+, Node.js 18+

**① 백엔드**
```bash
cd backend

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
# .\.venv\Scripts\Activate.ps1    # Windows PowerShell

# 패키지 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 OPENAI_API_KEY 입력 (필수)
# SweetBook / AWS 키가 없어도 mock 모드로 전체 플로우 동작

# 서버 실행
uvicorn app.main:app --reload --port 8000
```
- API 서버: http://localhost:8000
- Swagger UI: http://localhost:8000/docs

**② 프론트엔드**
```bash
cd frontend

npm install
npm run dev
```
- 브라우저: http://localhost:5173
   
&nbsp;&nbsp;
<h2> 📋 사용한 API 목록</h2>

**SweetBook API** (`https://api-sandbox.sweetbook.com/v1`)

| Method | Endpoint | 용도 |
|---|---|---|
| GET | `/templates/{templateUid}` | 템플릿 상세 조회 (프리뷰 레이아웃) |
| POST | `/books` | DRAFT 책 생성 |
| POST | `/books/{bookUid}/cover` | 표지 이미지 업로드 |
| POST | `/books/{bookUid}/contents` | 내지 페이지 업로드 |
| POST | `/books/{bookUid}/finalization` | 책 완성 처리 |
| POST | `/orders/estimate` | 주문 금액 사전 조회 |
| POST | `/orders` | 주문 생성 |
| GET | `/orders` | 주문 목록 조회 |
| GET | `/orders/{orderUid}` | 주문 상세 조회 |
| POST | `/orders/{orderUid}/cancel` | 주문 취소 |
| PATCH | `/orders/{orderUid}/shipping` | 배송지 수정 |

&nbsp;&nbsp;
<h2>🤖 AI 도구 사용 내역</h2>

| AI 도구 | 활용 내용 |
|---|---|
| Claude Code | 백엔드 API 설계 및 구현, 코드 리뷰, 디버깅 |
| ChatGPT | 아이디어 기획 및 요구사항 정리 |

&nbsp;&nbsp;
<h2>🔨 설계 의도</h2>

### 💡 왜 이 서비스를 선택했나요?
단순히 디지털 결과물로 끝나는 AI 서비스가 아니라, **'실제 만질 수 있는 물건'** 으로 이어지는 경험이 사용자에게 훨씬 큰 가치를 준다고 생각했습니다. "AI가 내 아이의 이야기를 쓴다"는 감성적 접근과 "내 손에 책이 쥐어진다"는 실무적 연동이 결합된 비즈니스 모델에 매력을 느꼈습니다.

### 📈 비즈니스 가능성
- **커스터마이징 시장 성장**: 기성 동화책이 아닌 '내 아이'가 주인공인 유일한 책에 대한 부모의 지불 용의는 매우 높습니다.
- **자동화된 공급망**: 재고 없이 주문 발생 시에만 제작(Print on Demand)되므로 리스크가 낮고 확장성이 뛰어납니다.

### 🛠 시간이 더 있었다면 추가했을 기능
- **목소리 합성(TTS)**: 부모님의 목소리를 학습시켜 AI가 동화를 읽어주는 오디오북 기능.
- **다양한 화풍 선택**: 수채화, 유화, 픽셀 아트 등 아이의 취향에 맞는 삽화 스타일 필터 기능.
- **협업 편집**: 여러 명의 가족이 함께 페이지별로 내용을 수정하고 코멘트를 남길 수 있는 소셜 기능.
