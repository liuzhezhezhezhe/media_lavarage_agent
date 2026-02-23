"""All Telegram command and message handlers."""
import asyncio
import logging
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import monotonic
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import db
from config import settings
from bot.auth import auth
from bot import formatter
from bot.file_parser import parse_file
from agent.llm import get_llm_client
from agent.modules.analyze import analyze
from agent.modules.route import route
from agent.modules.rewrite import rewrite
from agent.prompts import chat as chat_prompts

logger = logging.getLogger(__name__)

# ConversationHandler states
WAITING_CONTENT = 1
CHATTING = 2

_RATE_LIMIT_WINDOW_SECONDS = settings.rate_limit_window_seconds
_RATE_LIMIT_PIPELINE_PER_WINDOW = settings.rate_limit_pipeline_per_window
_RATE_LIMIT_CHAT_PER_WINDOW = settings.rate_limit_chat_per_window

_GENERIC_PIPELINE_ERR = "❌ Processing failed. Please try again shortly."
_GENERIC_FILE_ERR = "❌ File parsing failed. Please try again later."
_GENERIC_CHAT_ERR = "❌ Chat failed temporarily. Please try again later."

_rate_limit_buckets: dict[tuple[int, str], deque[float]] = {}


@asynccontextmanager
async def _typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Sends TYPING chat action repeatedly until the block exits.

    Telegram expires the indicator after ~5 s, so we refresh every 4 s.
    """
    stop = asyncio.Event()

    async def _loop():
        while not stop.is_set():
            try:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop.wait(), timeout=4)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(_loop())
    try:
        yield
    finally:
        stop.set()
        await asyncio.gather(task, return_exceptions=True)

_UNAUTHORIZED_MSG = (
    "You don't have access to this bot.\n\n"
    "Your Telegram ID: `{user_id}`\n\n"
    "Send this ID to the admin to request access.\n"
    "Use /whoami at any time to see your ID."
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _uid(update: Update) -> int:
    return update.effective_user.id


def _cid(update: Update) -> int:
    return update.effective_chat.id


def _is_auth(update: Update) -> bool:
    return auth.is_authorized(_uid(update))


def _check_rate_limit(user_id: int, action: str, limit: int) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds) for user-action pair."""
    now = monotonic()
    key = (user_id, action)
    bucket = _rate_limit_buckets.setdefault(key, deque())
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS

    while bucket and bucket[0] <= window_start:
        bucket.popleft()

    if len(bucket) >= limit:
        retry_after = int(_RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])) + 1
        return False, max(retry_after, 1)

    bucket.append(now)
    return True, 0


async def _deny_rate_limit(update: Update, retry_after_seconds: int) -> None:
    await update.message.reply_text(
        f"⏳ Too many requests. Please retry in about {retry_after_seconds}s."
    )


async def _deny(update: Update) -> None:
    uid = _uid(update)
    await update.message.reply_text(
        _UNAUTHORIZED_MSG.format(user_id=uid),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _run_pipeline(
    content: str,
    source: str,
    user_id: int,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """Core pipeline: analyze → route → rewrite → save → send."""
    status_msg = await update.message.reply_text("🔍 Analyzing, please wait…")

    try:
        llm = get_llm_client()
        cid = _cid(update)

        # LLM call #1: analyze
        async with _typing(context, cid):
            analysis = await analyze(content, llm)

        # Route: decide candidate platforms by type/novelty
        candidate_platforms = route(analysis)
        platform_assessments = analysis.get("platform_assessments")
        platform_decisions: dict[str, bool] = {}
        platform_assessment_map: dict[str, dict] = {}

        if isinstance(platform_assessments, list):
            normalized_assessments = []
            for item in platform_assessments:
                if not isinstance(item, dict):
                    continue
                platform = str(item.get("platform", "")).strip().lower()
                if not platform:
                    continue
                publishable = bool(item.get("publishable", False))
                reason = str(item.get("reason", "")).strip()
                novelty_score = int(item.get("novelty_score") or 0)
                clarity_score = int(item.get("clarity_score") or 0)
                risk_level = str(item.get("risk_level", "unknown")).strip().lower() or "unknown"
                summary = str(item.get("summary", "")).strip()
                key_points = item.get("key_points")
                if not isinstance(key_points, list):
                    key_points = []
                normalized_key_points = [str(p).strip() for p in key_points if str(p).strip()]

                platform_decisions[platform] = publishable
                platform_assessment_map[platform] = {
                    "platform": platform,
                    "novelty_score": novelty_score,
                    "clarity_score": clarity_score,
                    "publishable": publishable,
                    "risk_level": risk_level,
                    "summary": summary,
                    "key_points": normalized_key_points,
                    "reason": reason,
                }
                normalized_assessments.append({
                    "platform": platform,
                    "novelty_score": novelty_score,
                    "clarity_score": clarity_score,
                    "publishable": publishable,
                    "risk_level": risk_level,
                    "summary": summary,
                    "key_points": normalized_key_points,
                    "reason": reason,
                })
            if normalized_assessments:
                analysis["platform_assessments"] = normalized_assessments

        # Global publishability is a coarse gate; platform_assessments refines it.
        if not analysis.get("publishable"):
            platforms: list[str] = []
        elif platform_decisions:
            platforms = []
            for platform in candidate_platforms:
                allowed = platform_decisions.get(platform)
                # Backward compatible: missing key keeps the candidate platform.
                if allowed is False:
                    continue
                platforms.append(platform)
        else:
            platforms = candidate_platforms

        analysis["recommended_platforms"] = platforms
        analysis["publishable"] = bool(platforms)

        # Non-publishable (global or all platforms filtered out): save and skip rewrite
        if not platforms:
            thought_id = db.save_thought(user_id, content, source, analysis)
            await status_msg.delete()
            analysis_msg = formatter.format_analysis(analysis, thought_id)
            await update.message.reply_text(analysis_msg, parse_mode=ParseMode.MARKDOWN_V2)
            return True

        # LLM call #2+: rewrite for each platform
        platform_outputs: dict[str, str] = {}
        for platform in platforms:
            platform_analysis = dict(analysis)
            platform_assessment = platform_assessment_map.get(platform)
            if platform_assessment:
                platform_analysis["novelty_score"] = platform_assessment.get("novelty_score", platform_analysis.get("novelty_score"))
                platform_analysis["clarity_score"] = platform_assessment.get("clarity_score", platform_analysis.get("clarity_score"))
                platform_analysis["risk_level"] = platform_assessment.get("risk_level", platform_analysis.get("risk_level"))
                platform_analysis["summary"] = platform_assessment.get("summary") or platform_analysis.get("summary", "")
                platform_analysis["key_points"] = platform_assessment.get("key_points") or platform_analysis.get("key_points", [])

            async with _typing(context, cid):
                platform_outputs[platform] = await rewrite(content, platform, platform_analysis, llm)

        # Save to DB
        thought_id = db.save_thought(user_id, content, source, analysis)
        for platform, output_content in platform_outputs.items():
            db.save_output(thought_id, platform, output_content)

        # Delete status message
        await status_msg.delete()

        # Send analysis message
        analysis_msg = formatter.format_analysis(analysis, thought_id)
        await update.message.reply_text(analysis_msg, parse_mode=ParseMode.MARKDOWN_V2)

        # Send each platform output
        for platform in platforms:
            output_content = platform_outputs.get(platform, "")
            msg_text, _ = formatter.format_platform_output(platform, output_content, thought_id)
            await update.message.reply_text(msg_text, parse_mode=ParseMode.MARKDOWN_V2)

        return True

    except Exception as exc:
        logger.exception("Pipeline error")
        await status_msg.edit_text(_GENERIC_PIPELINE_ERR)
        return False


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Welcome to *Media Leverage Agent*\n\n"
        "Turn your raw ideas and conversations into publishable content\\.\n\n"
        "Send /help to see all available commands\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── /help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 *Commands*\n\n"
        "*Content*\n"
        "/chat \\- Explore ideas with AI \\(use /analyze afterward to publish\\)\n"
        "/process \\- Process mode \\(paste text or upload a file\\)\n"
        "/analyze \\- Analyze accumulated messages \\(chat uses current session\\)\n"
        "/tag \\[label\\] \\- Place a marker at the current position\n\n"
        "*Records*\n"
        "/history \\- Last 10 processed records\n"
        "/show \\<id\\> \\- View full analysis and platform outputs for a record\n\n"
        "*Other*\n"
        "/status \\- Show bot status and configuration\n"
        "/whoami \\- Show your Telegram ID\n"
        "/cancel \\- Exit current mode"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


# ── /status ───────────────────────────────────────────────────────────────────

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from config import settings

    provider = settings.llm_provider.lower()
    model_map = {
        "anthropic": settings.anthropic_model,
        "openai": settings.openai_model,
        "copilot": settings.copilot_model,
        "custom": settings.openai_model,
    }
    model = model_map.get(provider, "unknown")

    uid = _uid(update)
    authorized = auth.is_authorized(uid)
    auth_icon = "✅ Authorized" if authorized else "❌ Unauthorized"
    count = db.get_thought_count(uid)

    text = (
        "⚙️ *Bot Status*\n\n"
        f"🤖 LLM: `{formatter.escape(provider)}` / `{formatter.escape(model)}`\n"
        f"📊 Your records: `{count}`\n"
        f"👤 Access: {auth_icon}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


# ── /whoami ───────────────────────────────────────────────────────────────────

async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _uid(update)
    authorized = auth.is_authorized(uid)
    status = "✅ Authorized" if authorized else "❌ Unauthorized"
    text = (
        f"Your Telegram ID: `{uid}`\n"
        f"Status: {status}\n\n"
        "Share this ID with the admin to request access."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── /tag ──────────────────────────────────────────────────────────────────────

async def cmd_tag(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_auth(update):
        await _deny(update)
        return

    uid = _uid(update)
    cid = _cid(update)
    label = " ".join(context.args) if context.args else None

    db.save_tag(uid, cid, label)

    label_str = f'"{label}"' if label else "(no label)"
    await update.message.reply_text(
        f"🏷 Marker placed {label_str}\n"
        "Use /analyze to process all messages after this marker."
    )


# ── /analyze ──────────────────────────────────────────────────────────────────

async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_auth(update):
        await _deny(update)
        return

    uid = _uid(update)
    cid = _cid(update)
    session_start = context.user_data.get("chat_session_start")

    allowed, retry_after = _check_rate_limit(uid, "pipeline", _RATE_LIMIT_PIPELINE_PER_WINDOW)
    if not allowed:
        await _deny_rate_limit(update, retry_after)
        return

    tag = db.get_latest_tag(uid, cid)
    if session_start:
        messages = db.get_messages_since_tag(uid, cid, session_start)
        source_desc = "from the current /chat session"
    elif tag:
        messages = db.get_messages_since_tag(uid, cid, tag["created_at"])
        tag_label = tag.get("label") or "(no label)"
        source_desc = f'after marker "{tag_label}"'
    else:
        messages = db.get_today_messages(uid, cid)
        source_desc = "from today"

    if not messages:
        await update.message.reply_text(
            f"⚠️ No messages found {source_desc}.\n"
            "Send some plain messages first, or use /process to paste content directly."
        )
        return

    content = "\n\n".join(m["content"] for m in messages)
    last_message_time = messages[-1]["created_at"]
    await update.message.reply_text(
        f"🔍 Reading {len(messages)} message(s) {source_desc}…"
    )

    analyze_source = "chat_session" if session_start else "tag_analyze"
    pipeline_ok = await _run_pipeline(content, analyze_source, uid, update, context)

    if not pipeline_ok:
        await update.message.reply_text(
            "⚠️ Analyze failed; retained messages so you can retry /analyze."
        )
        return

    # Clean up consumed data so a subsequent /analyze starts fresh.
    if session_start:
        db.delete_messages_since(uid, cid, session_start)
        context.user_data.pop("chat_session_start", None)
        context.user_data.pop("chat_history", None)
        return

    if tag:
        db.delete_tag(tag["id"])
    db.delete_messages_up_to(uid, cid, last_message_time)


# ── /process (ConversationHandler) ───────────────────────────────────────────

async def cmd_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_auth(update):
        await _deny(update)
        return ConversationHandler.END

    await update.message.reply_text(
        "Send the content you want to analyze:\n\n"
        "• Paste plain text\n"
        "• Upload a file (.txt / .md / .json / .csv, max 20 MB)\n\n"
        "Send /cancel to exit."
    )
    return WAITING_CONTENT


async def process_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_auth(update):
        await _deny(update)
        return ConversationHandler.END

    content = update.message.text.strip()
    if not content:
        await update.message.reply_text("Content is empty, please try again.")
        return WAITING_CONTENT

    uid = _uid(update)
    allowed, retry_after = _check_rate_limit(uid, "pipeline", _RATE_LIMIT_PIPELINE_PER_WINDOW)
    if not allowed:
        await _deny_rate_limit(update, retry_after)
        return WAITING_CONTENT

    await _run_pipeline(content, "text", uid, update, context)
    return ConversationHandler.END


async def process_file_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_auth(update):
        await _deny(update)
        return ConversationHandler.END

    document = update.message.document
    if not document:
        await update.message.reply_text("No file detected. Please upload a file or paste text.")
        return WAITING_CONTENT

    filename = document.file_name or "upload.txt"
    file_size = document.file_size or 0

    if file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ File exceeds the 20 MB limit. Please compress it and try again.")
        return WAITING_CONTENT

    status_msg = await update.message.reply_text(f"📂 Parsing {filename}…")

    try:
        tg_file = await document.get_file()
        data = await tg_file.download_as_bytearray()
        content = parse_file(bytes(data), filename)
    except ValueError as e:
        await status_msg.edit_text(f"❌ {e}")
        return WAITING_CONTENT
    except Exception as e:
        logger.exception("File download/parse error")
        await status_msg.edit_text(_GENERIC_FILE_ERR)
        return WAITING_CONTENT

    await status_msg.delete()

    uid = _uid(update)
    allowed, retry_after = _check_rate_limit(uid, "pipeline", _RATE_LIMIT_PIPELINE_PER_WINDOW)
    if not allowed:
        await _deny_rate_limit(update, retry_after)
        return WAITING_CONTENT

    await _run_pipeline(content, "file", uid, update, context)
    return ConversationHandler.END


async def process_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Please send text or upload a file, or send /cancel to exit."
    )
    return WAITING_CONTENT


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _discard_chat_session(update, context)
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ── /history ──────────────────────────────────────────────────────────────────

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_auth(update):
        await _deny(update)
        return

    uid = _uid(update)
    records = db.get_history(uid, limit=10)
    msg = formatter.format_history(records)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


# ── /show <id> ────────────────────────────────────────────────────────────────

async def cmd_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_auth(update):
        await _deny(update)
        return

    if not context.args:
        await update.message.reply_text("Usage: /show <id>")
        return

    try:
        thought_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID must be a number.")
        return

    uid = _uid(update)
    result = db.get_thought_with_outputs(thought_id, uid)
    if not result:
        await update.message.reply_text(f"❌ Record #{thought_id} not found (or no permission).")
        return

    messages = formatter.format_full_record(result["thought"], result["outputs"])
    for msg in messages:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


# ── plain text (store, no reply) ──────────────────────────────────────────────

async def handle_plain_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Store message silently. Unauthorized users receive a whoami hint."""
    if not update.message or not update.message.text:
        return

    uid = _uid(update)
    if not auth.is_authorized(uid):
        await update.message.reply_text(
            f"You don't have access.\nYour Telegram ID: `{uid}`\n"
            "Share this ID with the admin to request access.\nUse /whoami to check.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    cid = _cid(update)
    mid = update.message.message_id
    content = update.message.text.strip()
    if content:
        db.save_chat_message(uid, cid, mid, content)
    # Silent: no reply


# ── /chat (interactive idea exploration) ──────────────────────────────────────

async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_auth(update):
        await _deny(update)
        return ConversationHandler.END

    context.user_data["chat_session_start"] = datetime.now(timezone.utc).isoformat()
    context.user_data["chat_history"] = []
    await update.message.reply_text(
        "💬 Chat mode active. Explore your ideas freely.\n\n"
        "Use /analyze when done — it processes the conversation and exits.\n"
        "Use /tag to mark and exit. Use /cancel to discard and exit."
    )
    return CHATTING


async def chat_handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_auth(update):
        await _deny(update)
        return ConversationHandler.END

    user_text = update.message.text.strip()
    if not user_text:
        return CHATTING

    uid = _uid(update)
    cid = _cid(update)
    mid = update.message.message_id

    allowed, retry_after = _check_rate_limit(uid, "chat", _RATE_LIMIT_CHAT_PER_WINDOW)
    if not allowed:
        await _deny_rate_limit(update, retry_after)
        return CHATTING

    # Store to DB so /analyze can access this conversation later
    db.save_chat_message(uid, cid, mid, f"User: {user_text}")

    history: list[dict] = context.user_data.setdefault("chat_history", [])
    history.append({"role": "user", "content": user_text})

    try:
        llm = get_llm_client()
        async with _typing(context, cid):
            response = await llm.chat(chat_prompts.SYSTEM, history)
        reply = response.content
    except Exception as exc:
        logger.exception("Chat LLM error")
        await update.message.reply_text(_GENERIC_CHAT_ERR)
        return CHATTING

    history.append({"role": "assistant", "content": reply})
    bot_message = await update.message.reply_text(reply)
    db.save_chat_message(uid, cid, bot_message.message_id, f"Assistant: {reply}")
    return CHATTING


# ── conversation helpers ──────────────────────────────────────────────────────

def _discard_chat_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete DB messages accumulated since the chat session started.

    Called on any exit that is NOT /analyze, so discarded messages are never
    picked up by a future /analyze call.
    """
    session_start = context.user_data.pop("chat_session_start", None)
    context.user_data.pop("chat_history", None)
    if session_start:
        db.delete_messages_since(_uid(update), _cid(update), session_start)


# ── state-transition handlers ─────────────────────────────────────────────────

async def _chat_to_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """CHATTING → WAITING_CONTENT: discard chat session, enter process mode."""
    _discard_chat_session(update, context)
    return await cmd_process(update, context)


async def _process_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """WAITING_CONTENT → CHATTING: enter chat mode."""
    return await cmd_chat(update, context)


# ── exit handlers ─────────────────────────────────────────────────────────────

async def _exit_tag_from_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _discard_chat_session(update, context)
    await cmd_tag(update, context)
    return ConversationHandler.END


async def _exit_analyze_from_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # /analyze is the only exit that keeps the data — do not discard.
    await cmd_analyze(update, context)
    return ConversationHandler.END


async def _exit_tag_from_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await cmd_tag(update, context)
    return ConversationHandler.END


async def _exit_analyze_from_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await cmd_analyze(update, context)
    return ConversationHandler.END


# ── build ConversationHandler ─────────────────────────────────────────────────

def build_conversation() -> ConversationHandler:
    """Single ConversationHandler for both /process and /chat modes.

    A unified handler allows direct state switching between modes (/process
    inside chat enters process mode immediately, and vice versa) and ensures
    /cancel and /analyze behave consistently regardless of which mode is active.
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler("process", cmd_process),
            CommandHandler("chat",    cmd_chat),
        ],
        states={
            WAITING_CONTENT: [
                CommandHandler("chat",    _process_to_chat),
                CommandHandler("tag",     _exit_tag_from_process),
                CommandHandler("analyze", _exit_analyze_from_process),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text_input),
                MessageHandler(filters.Document.ALL,            process_file_input),
                MessageHandler(~filters.COMMAND,                process_invalid_input),
            ],
            CHATTING: [
                CommandHandler("process", _chat_to_process),
                CommandHandler("tag",     _exit_tag_from_chat),
                CommandHandler("analyze", _exit_analyze_from_chat),
                MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handle_message),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )
