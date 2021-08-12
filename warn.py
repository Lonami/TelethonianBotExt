import os
from collections import defaultdict

from telethon import events

WARN_MESSAGES = [
    "Hey {name}, don't do that again{what} or I will ban you. You have been warned.",
    "{name}, this is the second warning. Stop doing that{what} or I will ban you.",
    "Sorry {name}, this is the last time you do that{what}; I've had enough."
]

FAREWELL_MESSAGE = 'Farewell!'

WARNED_FILE = os.path.join(os.path.dirname(__file__), 'warned-people.txt')

# TODO figure out a way to share stuff between autoadmin.py and here
with open(os.path.join(os.path.dirname(__file__), 'admins.txt'), encoding="utf-8") as f:
    ADMINS = {
        int(line.strip().split()[0]): line.strip().split()[1]
        for line in f
        if not line.isspace()
    }


warned_people = defaultdict(int)  # {id: stage (warn message index)}

try:
    with open(WARNED_FILE, encoding='utf-8') as fd:
        for line in fd:
            k, v = map(int, line.split())
            warned_people[k] = v
except OSError:
    pass


async def init(bot, modules):
    utils = modules['utils']

    @bot.on(events.NewMessage(pattern='#warn', from_users=set(ADMINS)))
    async def handler(event):
        await event.delete()
        if not event.is_reply:
            return

        reply = await event.get_reply_message()
        if reply.sender_id in ADMINS:
            return

        await reply.delete()

        name = '<a href="tg://user?id={}">{}</a>'.format(
            reply.sender_id,
            utils.get_display(reply.sender)
        )

        what = event.raw_text.split(maxsplit=1)
        what = '' if len(what) < 2 else f' ({what[1]})'

        stage = warned_people[reply.sender_id]
        await reply.respond(WARN_MESSAGES[stage].format(name=name, what=what), parse_mode='html')
        stage += 1
        if stage < len(WARN_MESSAGES):
            warned_people[reply.sender_id] = stage
        else:
            await bot.edit_permissions(
                reply.input_chat,
                reply.input_sender,
                view_messages=False
            )
            del warned_people[reply.sender_id]
            await reply.respond(FAREWELL_MESSAGE)

        with open(WARNED_FILE, 'w', encoding='utf-8') as fd:
            for kv in warned_people.items():
                fd.write('{} {}\n'.format(*kv))
