import os, uuid, logging
from typing import Dict, List

import openai
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from promts import MEETING_SUMMARY_PROMPT

openai.api_key = os.getenv('OPENAI_API_KEY')
logger = logging.getLogger('dialogue-backend')
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

app = FastAPI()
conversations: Dict[str, List[str]] = {}

# ---------- helpers ---------- #
async def transcribe(file: UploadFile) -> str:
    audio = await file.read()
    r = await openai.AsyncClient().audio.transcriptions.create(
        file=audio, model='whisper-1', language='ru')
    return r.text

async def summarize(text: str) -> str:
    r = await openai.AsyncClient().chat.completions.create(
        model='gpt-4o',
        messages=[
            {"role":"system","content":MEETING_SUMMARY_PROMPT},
            {"role":"user","content":text}
        ],
        max_tokens=700)
    return r.choices[0].message.content.strip()

# ---------- routes ---------- #
@app.post('/process_audio')
async def process_audio(file: UploadFile = File(...), session_id: str = Form(...)):
    text = await transcribe(file)
    conversations.setdefault(session_id, []).append(text)
    return JSONResponse({'transcription': text})

class SessionBody(BaseModel):
    session_id: str

@app.post('/get_summary')
async def get_summary(body: SessionBody):
    sess = body.session_id
    if sess not in conversations or not conversations[sess]:
        return JSONResponse({'summary': 'Нет данных для суммирования.'})
    full = '\n'.join(conversations[sess])
    summary = await summarize(full)
    return JSONResponse({'summary': summary})