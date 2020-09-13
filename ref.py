import difflib
import re
import sys
import urllib.parse
from types import ModuleType

from telethon import TelegramClient, custom, events
from telethon.extensions import markdown

DOCS = 'TL Reference for [{}](https://lonamiwebs.github.io/Telethon/?q={})'
DOCS_CLIENT = 'https://docs.telethon.dev/en/latest/modules/client.html#'
DOCS_MESSAGE = (
    'https://docs.telethon.dev/en/latest/'
    'modules/custom.html#telethon.tl.custom.message.Message.'
)
DOCS_EVENTS = 'https://docs.telethon.dev/en/latest/modules/events.html#'

COMMON_WORDS = re.compile(
    r'\b('
    r'good|new|first|last|long|great|little|own|other|old|right|big|high|different|small|large|next|early|young|important|few|public|bad|same|able'
    r'|to|of|in|for|on|with|at|by|from|up|about|into|over|after'
    r'|the|and|a|that|I|it|not|he|as|you|this|but|his|they|her|she|or|an|will|my|one|all|would|there|their'
    r')\b', re.IGNORECASE
)

def search_attr(cls, query, threshold=0.6, func=None):
    query = COMMON_WORDS.sub('', query)
    query = re.sub(' {2,}', ' ', query).strip().casefold()
    func = func or (lambda n: not n.startswith('_'))

    seq = difflib.SequenceMatcher(b=query, autojunk=False)
    scores = []
    for n in filter(func, dir(cls)):
        seq.set_seq1(n.casefold())
        scores.append((n, seq.ratio()))

    scores.sort(key=lambda t: t[1], reverse=True)
    if threshold is None:
        return scores[0]
    else:
        return scores[0][0] if scores[0][1] >= threshold else None


def attr_fullname(cls, n):
    m = getattr(cls, n)
    if isinstance(m, property):
        m = m.fget
    cls = sys.modules.get(m.__module__)
    for name in m.__qualname__.split('.')[:-1]:
        cls = getattr(cls, name)
    return cls.__module__ + '.' + cls.__name__ + '.' + m.__name__


def get_docs_message(kind, query):
    kind = kind.lower()

    func = None
    if kind == 'client':
        cls = TelegramClient
    elif kind == 'msg':
        cls = custom.Message
    elif kind == 'event':
        cls = events
        func = func=lambda n: n[0].isupper()

    attr = search_attr(cls, query, func=func)
    if not attr:
        return f'No such name "{query}" :/'

    name = attr
    if kind == 'client':
        attr = attr_fullname(cls, attr)
        url = DOCS_CLIENT
    elif kind == 'msg':
        name = f'Message.{name}'
        url = DOCS_MESSAGE
    elif kind == 'event':
        attr = f'{getattr(cls, attr).__module__}.{attr}'
        name = f'events.{name}'
        url = DOCS_EVENTS
    else:
        return f'No documentation for "{kind}"'

    return f'Documentation for [{name}]({url}{attr})'


async def init(bot):
    @bot.on(events.NewMessage(pattern='(?i)#(client|msg|event) (.+)', forwards=False))
    async def handler(event):
        """#client, #msg or #event query: Looks for the given attribute in RTD."""
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
        m = re.match('(client|msg|event).(.+)', query)
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
        name, score = max(rates, key=lambda t: t[1])
        if score < 0.75:
            return

        if len(name) < 4:
            return  # Short words trigger very commonly (such as "on")

        if name == 'pin_message' and score < 0.85:
            return  # "pin_message" triggers too often; require a higher threshold

        attr = attr_fullname(TelegramClient, name)
        await event.reply(
            f'Documentation for [{name}]({DOCS_CLIENT}{attr})',
            reply_to=event.reply_to_msg_id
        )

        # We have two @client.on, both could fire, stop that
        raise events.StopPropagation
