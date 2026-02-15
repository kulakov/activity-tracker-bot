#!/usr/bin/env python3
"""Real-time voice conversation server.

Architecture:
    Phone/browser  ─── WebSocket (audio PCM + JSON) ───  This server
                                                            │
                                        ┌───────────────────┤
                                        ▼                   ▼
                                   Silero-free VAD    faster-whisper (STT)
                                   (webrtcvad)              │
                                                            ▼
                                                      RAG (ChromaDB)
                                                            │
                                                            ▼
                                                    Claude API (streaming)
                                                            │
                                                            ▼
                                                    edge-tts (sentence by sentence)
                                                            │
                                                            ▼
                                                    MP3 chunks → browser

System requirements:
    - ffmpeg (apt install ffmpeg)
    - ~2 GB RAM for Whisper medium + embedding model

Quick start:
    1. cp .env.example .env && edit .env
    2. pip install -r requirements.txt
    3. python ingest.py --dir ./docs/project --collection project
    4. python realtime_server.py
    5. Open https://<your-ip>:8765 on phone

For mic access from phone you need HTTPS.  The server auto-generates
a self-signed cert on first run (accept the browser warning once).
Or set VKB_SSL_CERT / VKB_SSL_KEY to use your own cert.
"""

import asyncio
import io
import json
import logging
import os
import re
import ssl
import subprocess
import wave
from pathlib import Path

import edge_tts
import numpy as np
import webrtcvad
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from faster_whisper import WhisperModel

import config
from knowledge_base import KnowledgeBase

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Globals (initialized in startup)
# ──────────────────────────────────────────────────────────
whisper_model: WhisperModel | None = None
kb: KnowledgeBase | None = None

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"


# ──────────────────────────────────────────────────────────
# LLM backends (streaming where possible)
# ──────────────────────────────────────────────────────────

async def llm_stream(message: str, context: str, history: list[dict]):
    """Yield text tokens from the LLM."""
    backend = config.LLM_BACKEND
    if backend == "anthropic":
        async for tok in _stream_anthropic(message, context, history):
            yield tok
    elif backend == "ollama":
        async for tok in _stream_ollama(message, context, history):
            yield tok
    elif backend == "claude-cli":
        # CLI doesn't stream well — yield whole response at once
        text = await _call_claude_cli(message, context, history)
        yield text
    else:
        raise ValueError(f"Unknown LLM backend: {backend}")


def _build_system(context: str) -> str:
    s = config.SYSTEM_PROMPT
    if context:
        s += "\n\n## Relevant context from knowledge base:\n" + context
    return s


async def _stream_anthropic(message: str, context: str, history: list[dict]):
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    msgs = list(history[-config.MAX_HISTORY_MESSAGES:])
    msgs.append({"role": "user", "content": message})

    async with client.messages.stream(
        model=config.ANTHROPIC_MODEL,
        max_tokens=4096,
        system=_build_system(context),
        messages=msgs,
    ) as stream:
        async for tok in stream.text_stream:
            yield tok


async def _stream_ollama(message: str, context: str, history: list[dict]):
    import httpx

    system = _build_system(context)
    msgs = [{"role": "system", "content": system}]
    msgs.extend(history[-config.MAX_HISTORY_MESSAGES:])
    msgs.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{config.OLLAMA_BASE_URL}/api/chat",
            json={"model": config.OLLAMA_MODEL, "messages": msgs, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                tok = data.get("message", {}).get("content", "")
                if tok:
                    yield tok


async def _call_claude_cli(message: str, context: str, history: list[dict]) -> str:
    parts: list[str] = []
    if context:
        parts.append(f"Context:\n{context}\n")
    for h in history[-6:]:
        role = "User" if h["role"] == "user" else "Assistant"
        parts.append(f"{role}: {h['content']}")
    parts.append(f"User: {message}")
    prompt = "\n\n".join(parts)

    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", "--model", "sonnet", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return f"[error] {stderr.decode()[:300]}"
    return stdout.decode().strip()


# ──────────────────────────────────────────────────────────
# TTS helper
# ──────────────────────────────────────────────────────────

async def tts_to_mp3(text: str) -> bytes:
    """Synthesize *text* and return raw MP3 bytes."""
    comm = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE)
    buf = io.BytesIO()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


# ──────────────────────────────────────────────────────────
# Voice session (one per WebSocket connection)
# ──────────────────────────────────────────────────────────

# Sentence-ending pattern (period, !, ?, or newline after >=15 chars)
_SENT_END = re.compile(r"(?<=[.!?])\s|(?<=[.!?])$|\n")


class VoiceSession:
    SAMPLE_RATE = 16000
    FRAME_MS = 20
    FRAME_BYTES = SAMPLE_RATE * FRAME_MS // 1000 * 2  # 640 bytes (int16 mono)
    SILENCE_FRAMES = 30       # ~600 ms silence → end of utterance
    MIN_SPEECH_FRAMES = 5     # ignore clicks / very short noises

    def __init__(self, ws: WebSocket, collection: str):
        self.ws = ws
        self.collection = collection
        self.history: list[dict] = []

        self.vad = webrtcvad.Vad(2)
        self._speech_buf = bytearray()
        self._silence_n = 0
        self._speaking = False
        self._speech_n = 0

        self._responding = False
        self._cancel = False

    # ── main loop ────────────────────────────────────────

    async def run(self):
        try:
            while True:
                msg = await self.ws.receive()
                if "bytes" in msg and msg["bytes"]:
                    await self._on_audio(msg["bytes"])
                elif "text" in msg and msg["text"]:
                    await self._on_json(json.loads(msg["text"]))
        except WebSocketDisconnect:
            logger.info("Client disconnected")

    # ── control messages ─────────────────────────────────

    async def _on_json(self, msg: dict):
        kind = msg.get("type")
        if kind == "select":
            self.collection = msg.get("collection", self.collection)
            self.history = []
            await self._send({"type": "status", "text": f"collection: {self.collection}"})
        elif kind == "clear":
            self.history = []
            await self._send({"type": "status", "text": "history cleared"})
        elif kind == "text":
            # Support text input alongside voice
            text = msg.get("text", "").strip()
            if text:
                asyncio.create_task(self._process_text(text))

    # ── audio frames (640 bytes = 20 ms @ 16 kHz int16) ─

    async def _on_audio(self, frame: bytes):
        if len(frame) != self.FRAME_BYTES:
            return

        try:
            is_speech = self.vad.is_speech(frame, self.SAMPLE_RATE)
        except Exception:
            return

        if is_speech:
            # Barge-in: user started speaking while bot is responding
            if self._responding:
                self._cancel = True
                self._responding = False
                await self._send({"type": "barge_in"})

            self._speech_buf.extend(frame)
            self._speech_n += 1
            self._silence_n = 0
            if not self._speaking:
                self._speaking = True
                await self._send({"type": "status", "text": "listening"})

        elif self._speaking:
            self._speech_buf.extend(frame)
            self._silence_n += 1

            if self._silence_n >= self.SILENCE_FRAMES:
                if self._speech_n >= self.MIN_SPEECH_FRAMES:
                    audio = bytes(self._speech_buf)
                    self._reset_speech()
                    asyncio.create_task(self._process_speech(audio))
                else:
                    self._reset_speech()

    def _reset_speech(self):
        self._speech_buf = bytearray()
        self._speaking = False
        self._speech_n = 0
        self._silence_n = 0

    # ── speech processing pipeline ───────────────────────

    async def _process_speech(self, pcm: bytes):
        self._responding = True
        self._cancel = False

        await self._send({"type": "status", "text": "transcribing"})

        # STT
        audio_np = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        loop = asyncio.get_event_loop()
        segments, _ = await loop.run_in_executor(
            None,
            lambda: whisper_model.transcribe(audio_np, vad_filter=False),
        )
        text = " ".join(s.text for s in segments).strip()

        if not text or self._cancel:
            self._responding = False
            return

        await self._process_text(text)

    async def _process_text(self, text: str):
        self._responding = True
        self._cancel = False

        await self._send({"type": "transcript", "role": "user", "text": text})
        await self._send({"type": "status", "text": "thinking"})

        # RAG
        results = kb.search(text, self.collection) if self.collection else []
        context = "\n\n---\n\n".join(
            f"[{r['source']}]\n{r['text']}" for r in results
        ) if results else ""

        # LLM streaming → sentence TTS → audio chunks
        full_response = ""
        sentence_buf = ""

        await self._send({"type": "audio_start"})

        try:
            async for token in llm_stream(text, context, self.history):
                if self._cancel:
                    break
                full_response += token
                sentence_buf += token

                if self._should_flush(sentence_buf):
                    sentence = sentence_buf.strip()
                    sentence_buf = ""
                    if sentence:
                        await self._speak_sentence(sentence)

            # flush remainder
            if sentence_buf.strip() and not self._cancel:
                await self._speak_sentence(sentence_buf.strip())

        except Exception as e:
            logger.exception("LLM error")
            await self._send({"type": "error", "text": str(e)[:300]})

        await self._send({"type": "audio_end"})

        if full_response and not self._cancel:
            await self._send({"type": "transcript", "role": "assistant", "text": full_response})
            self.history.append({"role": "user", "content": text})
            self.history.append({"role": "assistant", "content": full_response})
            if len(self.history) > config.MAX_HISTORY_MESSAGES * 2:
                self.history = self.history[-config.MAX_HISTORY_MESSAGES * 2:]

        self._responding = False

    @staticmethod
    def _should_flush(buf: str) -> bool:
        stripped = buf.rstrip()
        if len(stripped) < 15:
            return False
        if stripped[-1] in ".!?\n":
            return True
        # Also flush after semicolons / colons in longer buffers
        if len(stripped) > 80 and stripped[-1] in ";:":
            return True
        return False

    async def _speak_sentence(self, text: str):
        if self._cancel:
            return
        try:
            mp3 = await tts_to_mp3(text)
            if mp3 and not self._cancel:
                await self.ws.send_bytes(mp3)
        except Exception:
            logger.exception("TTS error for: %s", text[:60])

    async def _send(self, msg: dict):
        try:
            await self.ws.send_text(json.dumps(msg))
        except Exception:
            pass


# ──────────────────────────────────────────────────────────
# HTTP routes
# ──────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/collections")
async def api_collections():
    cols = kb.list_collections() if kb else []
    return {"collections": cols}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Wait for initial "start" message with collection name
    try:
        init = await asyncio.wait_for(websocket.receive_text(), timeout=30)
        data = json.loads(init)
        collection = data.get("collection", "")
    except Exception:
        await websocket.close()
        return

    if collection not in (kb.list_collections() if kb else []):
        await websocket.send_text(json.dumps({
            "type": "error",
            "text": f"Collection '{collection}' not found",
        }))
        await websocket.close()
        return

    logger.info("Session started: collection=%s", collection)
    session = VoiceSession(websocket, collection)
    await session.run()


# ──────────────────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    global whisper_model, kb

    logger.info("Loading Whisper model '%s' ...", config.WHISPER_MODEL)
    device = config.WHISPER_DEVICE
    if device == "auto":
        try:
            import ctranslate2
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
    whisper_model = WhisperModel(
        config.WHISPER_MODEL,
        device=device,
        compute_type="float16" if device == "cuda" else "int8",
    )
    logger.info("Whisper ready (device=%s)", device)

    logger.info("Loading knowledge base ...")
    kb = KnowledgeBase()
    logger.info("Collections: %s", kb.list_collections())


# ──────────────────────────────────────────────────────────
# Self-signed cert generator
# ──────────────────────────────────────────────────────────

def ensure_ssl_cert() -> tuple[str, str]:
    """Generate a self-signed cert if none is configured."""
    cert = os.getenv("VKB_SSL_CERT")
    key = os.getenv("VKB_SSL_KEY")
    if cert and key and Path(cert).exists() and Path(key).exists():
        return cert, key

    cert_dir = Path(__file__).parent / ".certs"
    cert_dir.mkdir(exist_ok=True)
    cert_path = cert_dir / "server.crt"
    key_path = cert_dir / "server.key"

    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)

    logger.info("Generating self-signed SSL certificate ...")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_path), "-out", str(cert_path),
            "-days", "365", "-nodes",
            "-subj", "/CN=voice-kb-local",
        ],
        check=True,
        capture_output=True,
    )
    logger.info("SSL cert created at %s", cert_dir)
    return str(cert_path), str(key_path)


# ──────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("VKB_HOST", "0.0.0.0")
    port = int(os.getenv("VKB_PORT", "8765"))

    cert_file, key_file = ensure_ssl_cert()

    logger.info("Starting server on https://%s:%d", host, port)
    logger.info("Open this URL on your phone (accept the cert warning once)")

    uvicorn.run(
        "realtime_server:app",
        host=host,
        port=port,
        ssl_certfile=cert_file,
        ssl_keyfile=key_file,
    )
