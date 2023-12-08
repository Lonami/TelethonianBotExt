# This module aimes to provide a response for common question about load speeds.
import re

from telethon import TelegramClient, custom, events
from telethon.extensions import markdown

RESPONSE = (
    "If you want to increase up/down speed, you can install `cryptg` via pip.\n"
    "This module aims to provide a better encryption/decryption algorithm for Telegram clients.\n"
    "If you want to increase speed even further, you can use "
    "[this snippet](https://gist.github.com/painor/7e74de80ae0c819d3e9abcf9989a8dd6)\n"
    "Be cautious while using it, "
    "because it can lead to `FloodWait` error, as it uses multiple simultaneous connections."
)


def init(bot: TelegramClient):
    @bot.on(
        events.NewMessage(
            pattern=re.compile(
                r".*((speed|slow|fast).*(up|down)load|(up|down)load.*(speed|slow|fast)).*",
                flags=re.DOTALL | re.IGNORECASE,
            ),
            forwards=False,
            outgoing=False,
        )
    )
    async def handler(event):
        """Respond to messages like 'speed up my downloads'"""
        await event.reply(RESPONSE)

    @bot.on(
        events.NewMessage(
            pattern=re.compile(
                r"#(speed|upload|download)", flags=re.DOTALL | re.IGNORECASE
            ),
            forwards=False,
        )
    )
    async def handler(event):
        """Respond to messages like '#speed'"""
        await event.delete()
        await event.respond(RESPONSE)
