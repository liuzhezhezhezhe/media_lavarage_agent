"""Media Leverage Agent - Telegram Bot entry point."""
import logging
import sys
from urllib.parse import urlparse

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

import db
from config import settings
from bot.handlers import (
    cmd_start,
    cmd_help,
    cmd_status,
    cmd_whoami,
    cmd_tag,
    cmd_analyze,
    cmd_history,
    cmd_show,
    handle_plain_message,
    build_conversation,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def _set_commands(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("chat",    "Explore ideas with AI"),
        BotCommand("process", "Process content (paste text or upload a file)"),
        BotCommand("analyze", "Analyze accumulated messages (chat uses current session)"),
        BotCommand("tag",     "Place a marker at the current position"),
        BotCommand("history", "Last 10 processed records"),
        BotCommand("show",    "View full record by ID"),
        BotCommand("status",  "Show bot status"),
        BotCommand("help",    "Show all commands"),
        BotCommand("whoami",  "Show your Telegram ID"),
        BotCommand("cancel",  "Exit current mode"),
    ])


def _maybe_copilot_device_flow() -> None:
    """If using Copilot provider without GITHUB_TOKEN set, run device flow.

    On success the token is written back to .env as GITHUB_TOKEN so
    subsequent startups skip this step entirely.
    """
    if settings.llm_provider.lower() != "copilot":
        return
    if settings.github_token:
        return

    from agent.llm.copilot_client import CopilotClient
    logger.info("GITHUB_TOKEN not set. Starting Copilot device flow...")
    CopilotClient.run_device_flow()
    logger.info("Device flow complete. GITHUB_TOKEN saved to .env.")


def main() -> None:
    # Initialize DB
    db.init_db()
    logger.info("Database initialized.")

    # Handle Copilot device flow before bot starts (terminal interaction)
    _maybe_copilot_device_flow()

    # Build the application
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_set_commands)
        .build()
    )

    # Register ConversationHandler first (higher priority)
    app.add_handler(build_conversation())

    # Register command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CommandHandler("tag", cmd_tag))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("show", cmd_show))

    # Plain text messages (store silently for authorized users)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plain_message)
    )

    if settings.webhook_url:
        url_path = urlparse(settings.webhook_url).path or "/bot"
        logger.info("Webhook mode: %s (listening on port %d)", settings.webhook_url, settings.webhook_port)
        app.run_webhook(
            listen=settings.webhook_listen,
            port=settings.webhook_port,
            url_path=url_path,
            secret_token=settings.webhook_secret or None,
            webhook_url=settings.webhook_url,
            drop_pending_updates=True,
        )
    else:
        logger.info("Polling mode (set WEBHOOK_URL in .env to switch to webhook).")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
