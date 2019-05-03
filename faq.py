import json
import re

from telethon import events

# TODO Make this better
template = "The cause of this error is most likely {cause}. To fix it you need to {solution}"
with open("faq.json", "r", encoding="utf-8") as out:
    errors = json.load(out)


async def init(bot):
    @bot.on(events.ChatAction)
    async def handler(event):
        for error in errors:
            if re.search(error["pattern"], event.raw_text, flags=re.IGNORECASE):
                await event.reply(template.format(cause=error["cause"], solution=error["solution"]))
                break
