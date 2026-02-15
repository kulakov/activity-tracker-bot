#!/usr/bin/env python3
"""Voice Knowledge Base Assistant — Telegram bot.

System requirements:
    - Python 3.11+
    - ffmpeg  (apt install ffmpeg / brew install ffmpeg)
    - ~2 GB RAM for Whisper medium + embedding model

Quick start:
    1. cp .env.example .env   # fill in tokens
    2. pip install -r requirements.txt
    3. python ingest.py --dir ./docs/my_project --collection my_project
    4. python bot.py
"""

import asyncio
import io
import logging
import tempfile
from pathlib import Path

import edge_tts
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from faster_whisper import WhisperModel
from pydub import AudioSegment

import config
from knowledge_base import KnowledgeBase

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

router = Router()

# ---------- globals filled in main() ----------
whisper_model: WhisperModel | None = None
kb: KnowledgeBase | None = None
conversations: dict[int, dict] = {}  # chat_id -> state


# ==============================================================
# Conversation state
# ==============================================================

def get_conv(chat_id: int) -> dict:
    if chat_id not in conversations:
        conversations[chat_id] = {"history": [], "collection": None}
    return conversations[chat_id]


# ==============================================================
# STT  (faster-whisper, local)
# ==============================================================

async def transcribe(audio_path: str) -> str:
    loop = asyncio.get_event_loop()
    segments, _ = await loop.run_in_executor(
        None,
        lambda: whisper_model.transcribe(
            audio_path,
            language=None,  # auto-detect
            vad_filter=True,
        ),
    )
    # segments is a generator — consume it in the executor too
    text_parts: list[str] = []
    for seg in segments:
        text_parts.append(seg.text)
    return " ".join(text_parts).strip()


# ==============================================================
# TTS  (edge-tts, free Microsoft voices)
# ==============================================================

async def synthesize(text: str) -> bytes:
    """Return OGG OPUS bytes ready for Telegram voice message."""
    comm = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE)

    mp3_buf = io.BytesIO()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            mp3_buf.write(chunk["data"])
    mp3_buf.seek(0)

    # Convert MP3 -> OGG OPUS so Telegram shows it as a voice message
    audio = AudioSegment.from_mp3(mp3_buf)
    ogg_buf = io.BytesIO()
    audio.export(ogg_buf, format="ogg", codec="libopus")
    return ogg_buf.getvalue()


# ==============================================================
# LLM  (pluggable backends)
# ==============================================================

async def ask_llm(message: str, context: str, history: list[dict]) -> str:
    backend = config.LLM_BACKEND
    if backend == "anthropic":
        return await _ask_anthropic(message, context, history)
    if backend == "ollama":
        return await _ask_ollama(message, context, history)
    if backend == "claude-cli":
        return await _ask_claude_cli(message, context, history)
    raise ValueError(f"Unknown LLM backend: {backend}")


async def _ask_anthropic(message: str, context: str, history: list[dict]) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

    system = config.SYSTEM_PROMPT
    if context:
        system += "\n\n## Relevant context from knowledge base:\n" + context

    msgs = list(history[-config.MAX_HISTORY_MESSAGES :])
    msgs.append({"role": "user", "content": message})

    resp = await client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=4096,
        system=system,
        messages=msgs,
    )
    return resp.content[0].text


async def _ask_ollama(message: str, context: str, history: list[dict]) -> str:
    import httpx

    system = config.SYSTEM_PROMPT
    if context:
        system += "\n\n## Relevant context from knowledge base:\n" + context

    msgs = [{"role": "system", "content": system}]
    msgs.extend(history[-config.MAX_HISTORY_MESSAGES :])
    msgs.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{config.OLLAMA_BASE_URL}/api/chat",
            json={"model": config.OLLAMA_MODEL, "messages": msgs, "stream": False},
        )
        r.raise_for_status()
        return r.json()["message"]["content"]


async def _ask_claude_cli(message: str, context: str, history: list[dict]) -> str:
    """Use the `claude` CLI (included in Claude Max subscription)."""
    prompt_parts: list[str] = []
    if context:
        prompt_parts.append(f"Context from knowledge base:\n{context}\n")
    for h in history[-6:]:
        role = "User" if h["role"] == "user" else "Assistant"
        prompt_parts.append(f"{role}: {h['content']}")
    prompt_parts.append(f"User: {message}")
    full_prompt = "\n\n".join(prompt_parts)

    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", "--model", "sonnet", full_prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error("claude-cli error: %s", stderr.decode())
        return f"[claude-cli error] {stderr.decode()[:300]}"
    return stdout.decode().strip()


# ==============================================================
# Handlers
# ==============================================================

@router.message(Command("start"))
async def cmd_start(msg: types.Message):
    collections = kb.list_collections()
    lines = [
        "**Voice Knowledge Base Assistant**\n",
        "Send a voice message — I'll answer using your knowledge base.\n",
        "**Commands:**",
        "/collections — list knowledge bases",
        "/select `<name>` — choose active KB",
        "/clear — reset conversation history",
        "/status — show current settings",
    ]
    if collections:
        lines.append(f"\nAvailable: {', '.join(collections)}")
    else:
        lines.append("\nNo collections yet. Run `ingest.py` to add documents.")
    await msg.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("collections"))
async def cmd_collections(msg: types.Message):
    cols = kb.list_collections()
    if cols:
        text = "**Collections:**\n" + "\n".join(
            f"  `{c}` ({kb.collection_count(c)} chunks)" for c in cols
        )
    else:
        text = "No collections. Use `ingest.py` to add documents."
    await msg.answer(text, parse_mode="Markdown")


@router.message(Command("select"))
async def cmd_select(msg: types.Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("Usage: /select <collection_name>")
        return

    name = parts[1].strip()
    cols = kb.list_collections()
    if name not in cols:
        await msg.answer(f"Not found: `{name}`\nAvailable: {', '.join(cols)}", parse_mode="Markdown")
        return

    conv = get_conv(msg.chat.id)
    conv["collection"] = name
    conv["history"] = []
    await msg.answer(f"Active collection: **{name}**", parse_mode="Markdown")


@router.message(Command("clear"))
async def cmd_clear(msg: types.Message):
    get_conv(msg.chat.id)["history"] = []
    await msg.answer("History cleared.")


@router.message(Command("status"))
async def cmd_status(msg: types.Message):
    conv = get_conv(msg.chat.id)
    lines = [
        f"Collection: `{conv['collection'] or 'none'}`",
        f"History: {len(conv['history'])} messages",
        f"LLM: {config.LLM_BACKEND}",
        f"Whisper: {config.WHISPER_MODEL}",
        f"TTS: {config.TTS_VOICE}",
    ]
    await msg.answer("\n".join(lines), parse_mode="Markdown")


# ---------- voice / audio handler ----------

@router.message(F.voice | F.audio)
async def handle_voice(msg: types.Message, bot: Bot):
    conv = get_conv(msg.chat.id)

    # Auto-select if only one collection exists
    if not conv["collection"]:
        cols = kb.list_collections()
        if len(cols) == 1:
            conv["collection"] = cols[0]
        elif cols:
            await msg.answer(
                f"Select a collection first: /select <name>\nAvailable: {', '.join(cols)}"
            )
            return
        else:
            await msg.answer("No knowledge bases. Run `ingest.py` first.")
            return

    status = await msg.answer("Listening...")

    tmp_path = None
    try:
        # 1. Download voice file
        file_id = msg.voice.file_id if msg.voice else msg.audio.file_id
        file = await bot.get_file(file_id)
        bio = await bot.download_file(file.file_path)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(bio.read() if hasattr(bio, "read") else bio)
            tmp_path = tmp.name

        # 2. Transcribe
        user_text = await transcribe(tmp_path)
        logger.info("Transcribed: %s", user_text)

        if not user_text:
            await status.edit_text("Could not transcribe. Try again.")
            return

        await status.edit_text(f"_{user_text}_\n\nThinking...", parse_mode="Markdown")

        # 3. RAG — search KB
        results = kb.search(user_text, conv["collection"])
        context = "\n\n---\n\n".join(
            f"[{r['source']}]\n{r['text']}" for r in results
        ) if results else ""

        # 4. LLM
        answer = await ask_llm(user_text, context, conv["history"])

        # 5. Update history
        conv["history"].append({"role": "user", "content": user_text})
        conv["history"].append({"role": "assistant", "content": answer})
        if len(conv["history"]) > config.MAX_HISTORY_MESSAGES * 2:
            conv["history"] = conv["history"][-config.MAX_HISTORY_MESSAGES * 2 :]

        # 6. Send text reply
        # Truncate for Telegram message limit (4096 chars)
        display_answer = answer[:3900] + "..." if len(answer) > 3900 else answer
        await status.edit_text(
            f"_{user_text}_\n\n{display_answer}",
            parse_mode="Markdown",
        )

        # 7. TTS — speak the answer
        tts_text = answer[:2000]  # keep TTS under ~2 min
        ogg_data = await synthesize(tts_text)
        await msg.answer_voice(BufferedInputFile(ogg_data, filename="reply.ogg"))

    except Exception:
        logger.exception("Error processing voice message")
        await status.edit_text("Error processing voice message. Check logs.")
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


# ---------- text handler (for testing without mic) ----------

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(msg: types.Message):
    conv = get_conv(msg.chat.id)

    if not conv["collection"]:
        cols = kb.list_collections()
        if len(cols) == 1:
            conv["collection"] = cols[0]
        elif cols:
            await msg.answer(f"Select a collection: /select <name>\nAvailable: {', '.join(cols)}")
            return
        else:
            await msg.answer("No knowledge bases. Run `ingest.py` first.")
            return

    status = await msg.answer("Thinking...")

    try:
        results = kb.search(msg.text, conv["collection"])
        context = "\n\n---\n\n".join(
            f"[{r['source']}]\n{r['text']}" for r in results
        ) if results else ""

        answer = await ask_llm(msg.text, context, conv["history"])

        conv["history"].append({"role": "user", "content": msg.text})
        conv["history"].append({"role": "assistant", "content": answer})
        if len(conv["history"]) > config.MAX_HISTORY_MESSAGES * 2:
            conv["history"] = conv["history"][-config.MAX_HISTORY_MESSAGES * 2 :]

        display_answer = answer[:3900] + "..." if len(answer) > 3900 else answer
        await status.edit_text(display_answer, parse_mode="Markdown")

    except Exception:
        logger.exception("Error processing text message")
        await status.edit_text("Error processing message. Check logs.")


# ==============================================================
# Startup
# ==============================================================

async def main():
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

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Bot starting ...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
