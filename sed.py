import re
from collections import defaultdict, deque

from telethon import events


last_msgs = defaultdict(lambda: deque(maxlen=10))
last_replies = defaultdict(lambda: deque(maxlen=10))

SED_PATTERN = re.compile(r'^s/((?:\\/|[^/])+)/((?:\\/|[^/])*)/?(.*)')
PREFIX = '「sed」\n'


class UnknownFlag(ValueError):
    def __init__(self, flag):
        super().__init__(f'unknown flag: {flag}')
        self.flag = flag


def build_substitute(pattern, repl, flags):
    repl = repl.replace('\\/', '/').replace('\\0', '\\g<0>')

    count = 1
    flags = 0
    for f in (flags or ''):
        if f in 'Gg':
            count = 0
            continue

        try:
            flags |= getattr(re.RegexFlag, f.upper())
        except AttributeError:
            raise UnknownFlag(f) from None

    def substitute(string):
        if string.startswith(PREFIX):
            string = string[len(PREFIX):]

        s, i = re.subn(pattern, repl, string, count=count, flags=flags)
        if i > 0:
            return PREFIX + s

    return substitute


async def init(bot):
    @bot.on(events.NewMessage(pattern=SED_PATTERN))
    async def handler(event):
        if event.is_reply:
            messages = [await event.get_reply_message()]
        else:
            messages = reversed(last_msgs[event.chat_id])

        substitute = build_substitute(*event.pattern_match.groups())
        for message in messages:
            new = substitute(message.raw_text)
            if new is None:
                continue

            try:
                sent = await message.reply(new, parse_mode=None)
            except Exception as e:
                await message.reply('owh :(\n' + str(e))
            else:
                last_msgs[event.chat_id].append(sent)
                where = event.chat_id if event.is_channel else None
                last_replies[where].append((event.id, sent.id))

            break

        raise events.StopPropagation

    @bot.on(events.NewMessage)
    async def handler(event):
        last_msgs[event.chat_id].append(event.message)

    @bot.on(events.MessageDeleted)
    async def handler(event):
        for src, dst in last_replies[event.chat_id]:
            if src in event.deleted_ids:
                await bot.delete_messages(event.chat_id, dst)
