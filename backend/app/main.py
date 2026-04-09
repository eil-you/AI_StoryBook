from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import requests

app = FastAPI(title="FastAPI Backend for Pre-task")

# Vite 기본 포트 허용
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessageIn(BaseModel):
    message: str

class MessageOut(BaseModel):
    reply: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/chat", response_model=MessageOut)
def chat(payload: MessageIn):
    """
    간단한 에코 엔드포인트.
    환경변수 OPENAI_API_KEY 가 설정되어 있으면 OpenAI API 를 호출하려 시도합니다 (예시).
    """
    msg = payload.message
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": msg}],
                    "max_tokens": 150
                },
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            return {"reply": reply}
        except Exception:
            return {"reply": f"(fallback) Echo: {msg}"}
    return {"reply": f"Echo: {msg}"}