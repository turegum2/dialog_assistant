import os, uuid, asyncio, time
from io import BytesIO
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import openai
from openai import AsyncOpenAI
from promts import MEETING_SUMMARY_PROMPT

# ──────────────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not задан в переменных окружения")
openai.api_key = OPENAI_API_KEY
oclient = AsyncOpenAI()

app = FastAPI(title="Dialog Assistant API")

# ─── Память о диалогах ────────────────────────────────────────────────────────
TRANSCRIPTS: Dict[str, List[str]] = {}      # session_id -> list[str]
TOUCH: Dict[str, float] = {}                # время последнего обращения
TTL = 60 * 60 * 24                          # 24 ч

def touch(session_id: str) -> None:
    TOUCH[session_id] = time.time()

async def gc_sessions() -> None:
    """Периодически вычищаем простоявшие > TTL."""
    while True:
        now = time.time()
        for sid in list(TOUCH):
            if now - TOUCH[sid] > TTL:
                TRANSCRIPTS.pop(sid, None)
                TOUCH.pop(sid, None)
        await asyncio.sleep(3600)
@app.on_event("startup")
async def _startup():
    asyncio.create_task(gc_sessions())

# ─── Эндпоинт 1. Транскрипция ────────────────────────────────────────────────
@app.post("/process_audio")
async def process_audio(file: UploadFile = File(...),
                        session_id: str = Form(...)):
    try:
        touch(session_id)
        audio_bytes = BytesIO(await file.read())
        audio_bytes.name = file.filename                       # ← нужно Whisper-1

        tr = await oclient.audio.transcriptions.create(
            model="whisper-1",
            file=audio_bytes,
            language="ru"
        )
        text = tr.text.strip()

        TRANSCRIPTS.setdefault(session_id, []).append(text)
        return {"transcription": text}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ─── Эндпоинт 2. Итоговое резюме ─────────────────────────────────────────────
@app.post("/get_meeting_summary")
async def get_meeting_summary(session_id: str = Form(...)):
    if session_id not in TRANSCRIPTS:
        return {"summary": "Транскрипции отсутствуют."}

    full_dialogue = "\n".join(TRANSCRIPTS[session_id])
    prompt = (MEETING_SUMMARY_PROMPT +
              "\n\n---\n\nТранскрипция встречи (без изменений):\n" +
              full_dialogue)

    try:
        chat = await oclient.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Ты – опытный секретарь-резюмировщик."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.4
        )
        summary = chat.choices[0].message.content.strip()
        return {"summary": summary}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)