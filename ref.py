import difflib
import re
import sys
import urllib.parse

from telethon import TelegramClient, custom, events
from telethon.extensions import markdown

DOCS = 'TL Reference for [{}](https://lonamiwebs.github.io/Telethon/?q={})'
DOCS_CLIENT = 'https://telethon.readthedocs.io/en/latest/modules/client.html#'
DOCS_MESSAGE = (
    'https://telethon.readthedocs.io/en/latest/'
    'modules/custom.html#telethon.tl.custom.message.Message.'
)


def search_attr(cls, query, threshold=0.6):
    seq = difflib.SequenceMatcher(b=query, autojunk=False)
    scores = []
    for n in dir(cls):
        if not n.startswith('_'):
            seq.set_seq1(n)
            scores.append((n, seq.ratio()))

    scores.sort(key=lambda t: t[1], reverse=True)
    if threshold is None:
        return scores[0]
    else:
        return scores[0][0] if scores[0][1] >= threshold else None


def attr_fullname(cls, n):
    m = getattr(cls, n)
    cls = sys.modules.get(m.__module__)
    for name in m.__qualname__.split('.')[:-1]:
        cls = getattr(cls, name)
    return cls.__module__ + '.' + cls.__name__ + '.' + m.__name__


def get_docs_message(kind, query):
    kind = kind.lower()
    cls = {'client': TelegramClient, 'msg': custom.Message}[kind]

    attr = search_attr(cls, query.lower())
    if not attr:
        return f'No such method "{query}" :/'

    name = attr
    if kind == 'client':
        attr = attr_fullname(cls, attr)
        url = DOCS_CLIENT
    elif kind == 'msg':
        name = f'Message.{name}'
        url = DOCS_MESSAGE
    else:
        return f'No documentation for "{kind}"'

    return f'Documentation for [{name}]({url}{attr})'


async def init(bot):
    @bot.on(events.NewMessage(pattern='(?i)#(client|msg) (.+)', forwards=False))
    async def handler(event):
        """#client or #msg query: Looks for the given attribute in RTD."""
        await event.delete()

        await event.respond(
            get_docs_message(kind=event.pattern_match.group(1),
                             query=event.pattern_match.group(2)),
            reply_to=event.reply_to_msg_id
        )

    @bot.on(events.NewMessage(pattern='(?i)#summary (.+)', forwards=False))
    async def handler(event):
        """#summary what: Send summary link for client, events or objects."""
        await event.delete()
        what = event.pattern_match.group(1).lower()
        if what not in ('client', 'events', 'objects'):
            return

        await event.respond(
            f'See the [reference summary for "{what}"](https://docs.telethon.dev/'
            f'en/latest/quick-references/{what}-reference.html)',
            reply_to=event.reply_to_msg_id
        )

    @bot.on(events.InlineQuery)
    async def handler(event):
        builder = event.builder
        result = None
        query = event.text.lower()
        m = re.match('(client|msg).(.+)', query)
        if m:
            text = get_docs_message(m.group(1), m.group(2))
            query = markdown.parse(text)[0]
            result = builder.article(query, text=text)
        else:
            m = re.match('ref.(.+)', query)
            if m:
                query = m.group(1)
                text = DOCS.format(query, urllib.parse.quote(query))
                result = builder.article(query, text=text)

        await event.answer([result] if result else None)

    @bot.on(events.NewMessage(pattern=r'(?i)how (.+?)[\W]*$', forwards=False))
    @bot.on(events.NewMessage(pattern=r'(.+?)[\W]*?\?+', forwards=False))
    async def handler(event):
        words = event.pattern_match.group(1).split()
        rates = [
            search_attr(TelegramClient, ' '.join(words[-i:]), threshold=None)
            for i in range(1, 4)
        ]
        what = max(rates, key=lambda t: t[1])
        if what[1] < 0.75:
            return

        name = what[0]
        if len(name) < 4:
            return  # Short words trigger very commonly (such as "on")

        attr = attr_fullname(TelegramClient, name)
        await event.reply(
            f'Documentation for [{name}]({DOCS_CLIENT}{attr})',
            reply_to=event.reply_to_msg_id
        )

        # We have two @client.on, both could fire, stop that
        raise events.StopPropagation
