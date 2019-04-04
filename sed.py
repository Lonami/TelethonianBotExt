# Adapted from https://github.com/SijmenSchoon/regexbot
import re
from collections import defaultdict, deque

from telethon import events


last_msgs = defaultdict(lambda: deque(maxlen=10))
last_replies = defaultdict(lambda: deque(maxlen=10))

SED_PATTERN = r'^s/((?:\\/|[^/])+)/((?:\\/|[^/])*)(/.*)?'
PREFIX = '?sed?\n'


async def doit(message, match):
    # Don't ignore old messages, we don't fetch them anyway
    fr = match.group(1)
    to = match.group(2)
    to = (to
          .replace('\\/', '/')
          .replace('\\0', '\\g<0>'))
    try:
        fl = match.group(3)
        if fl is None:
            fl = ''
        fl = fl[1:]
    except IndexError:
        fl = ''

    # Build Python regex flags
    count = 1
    flags = 0
    for f in fl:
        if f == 'i':
            flags |= re.IGNORECASE
        elif f == 'm':
            flags |= re.MULTILINE
        elif f == 's':
            flags |= re.DOTALL
        elif f == 'g':
            count = 0
        else:
            await message.reply('unknown flag: {}'.format(f))
            return

    async def substitute(original, msg):
        if original.startswith(PREFIX):
            original = original[len(PREFIX):]

        s, i = re.subn(fr, to, original, count=count, flags=flags)
        if i > 0:
            return await msg.reply(PREFIX + s, parse_mode=None)

    try:
        if message.is_reply:
            msg = await message.get_reply_message()
            original = msg.raw_text
            if original:
                return await substitute(original, msg)

        else:
            for msg in reversed(last_msgs[message.chat_id]):
                original = msg.raw_text
                if original:
                    return await substitute(original, msg)

    except Exception as e:
        await message.reply('owh :(\n' + str(e))


async def init(bot):
    @bot.on(events.NewMessage(pattern=SED_PATTERN))
    async def test(event):
        msg = await doit(event.message, event.pattern_match)
        if msg:
            last_msgs[msg.chat_id].append(msg)

            where = event.chat_id if event.is_channel else None
            last_replies[where].append((event.id, msg.id))
            raise events.StopPropagation

    @bot.on(events.NewMessage(pattern=r'(.*)'))
    async def msg(event):
        last_msgs[event.chat_id].append(event.message)


    @bot.on(events.MessageDeleted)
    async def deleted(event):
        for src, dst in last_replies[event.chat_id]:
            if src in event.deleted_ids:
                await bot.delete_messages(event.chat_id, dst)
