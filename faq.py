import json
import re
import os

from telethon import events

# TODO Make this better
template = "The cause of this error is most likely {cause}. To fix it you need to {solution}"
with open(os.path.join(os.path.dirname(__file__), "faq.json"), "r", encoding="utf-8") as file:
    errors = json.load(file)


async def init(bot):
    @bot.on(events.NewMessage)
    async def handler(event):
        for error in errors:
            if re.search(error["pattern"], event.raw_text, flags=re.IGNORECASE):
                await event.reply(template.format(cause=error["cause"], solution=error["solution"]))
                break
