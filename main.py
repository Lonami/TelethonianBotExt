# Main commands that used to live in the Telethon repository
import asyncio
import urllib.parse

from telethon import events, custom


READ_FULL = (
    'Please read [Accessing the Full API](https://docs.telethon.dev'
    '/en/stable/concepts/full-api.html)'
)

SEARCH = (
    'Remember [search is your friend]'
    '(https://tl.telethon.dev/?q={}&redirect=no)'
)

DOCS = 'TL Reference for [{}](https://tl.telethon.dev/?q={})'
RTD = '[Read The Docs!](https://docs.telethon.dev)'
RTFD = '[Read The F* Docs!](https://docs.telethon.dev)'
UPDATES = (
    'Check out [Working with Updates](https://docs.telethon.dev'
    '/en/stable/basic/updates.html) in the documentation.'
)

SPAM = (
    "Telethon is free software. That means using it is a right: you are "
    "free to use it for absolutely any purpose whatsoever. However, help "
    "and support with using it is a privilege. If you misbehave or want "
    "to do bad things, despite possibly having good intentions, nobody "
    "is obligated to help you."
)

OFFTOPIC = {
    -1001109500936:
    'That is not related to Telethon. '
    'You may continue the conversation in @TelethonOffTopic',
    -1001200633650:
    'That seems to be related to Telethon. Try asking in @TelethonChat'
}

TOPIC = (
    "This group is for **usage questions about Telethon only**, and "
    "occasionally about semi-related topics like MTProto. Anything that does "
    "not directly involve any of the two does not belong here, and questions "
    "regarding general Python knowledge or use of any other libraries do not "
    "belong here. Please use other groups or search online instead."
)

UNKNOWN_OFFTOPIC = (
    "I don't know of any off-topic group for this chat! Maybe you want to "
    "visit the on-topic @TelethonChat, or the off-topic @TelethonOffTopic?"
)

ASK = (
    "Hey, that's not how you ask a question! If you want helpful advice "
    "(or any response at all) [read this first](https://stackoverflow.com"
    "/help/how-to-ask) and then ask again. If you have the time, [How To "
    "Ask Questions The Smart Way](catb.org/~esr/faqs/smart-questions.html)"
    " is another wonderful resource worth reading."
)

LOGGING = '''
**Please enable logging:**
```import logging
logging.basicConfig(level=logging.WARNING)```

If you need more information, use `logging.DEBUG` instead.
'''

ALREADY_FIXED = (
    "This issue has already been fixed, but it's not yet available in PyPi. "
    "You can upgrade now with `pip3 install -U https://github.com/LonamiWebs"
    "/Telethon/archive/master.zip`."
)

GOOD_RESOURCES = (
    "Some good resources to learn Python:\n"
    "• [Official Docs](https://docs.python.org/3/tutorial/index.html).\n"
    "• [Dive Into Python 3](https://rawcdn.githack.com/diveintomark/"
    "diveintopython3/master/table-of-contents.html).\n"
    "• [Learn Python](https://www.learnpython.org/).\n"
    "• [Project Python](http://projectpython.net/).\n"
    "• [Computer Science Circles](https://cscircles.cemc.uwaterloo.ca/).\n"
    "• [MIT OpenCourse](https://ocw.mit.edu/courses/electrical-engineering-"
    "and-computer-science/6-0001-introduction-to-computer-science-and-progr"
    "amming-in-python-fall-2016/).\n"
    "• [Hitchhiker’s Guide to Python](https://docs.python-guide.org/).\n"
    "• The @PythonRes Telegram Channel.\n"
    "• Corey Schafer videos for [beginners](https://www.youtube.com/watch?v="
    "YYXdXT2l-Gg&list=PL-osiE80TeTskrapNbzXhwoFUiLCjGgY7) and in [general]"
    "(https://www.youtube.com/watch?v=YYXdXT2l-Gg&list=PL-osiE80TeTt2d9bfV"
    "yTiXJA-UTHn6WwU)."
)

LEARN_PYTHON = (
    "That issue is no longer related with Telethon, and this group is not "
    "meant to be a group for learning Python. " + GOOD_RESOURCES
)

BUG_REPORT = (
    "If you believe you have found a bug in the library and you are pretty "
    "sure that the issue is not in your code, please [report it in GitHub]"
    "(https://github.com/LonamiWebs/Telethon/issues/new/choose). This group "
    "is only intended to help people with Telethon, it is __not__ the right "
    "place to report bugs.\n\n"
    "Before reporting in GitHub, **please make sure to provide**:\n"
    "• A small, self-contained snippet of code that reproduces the issue. "
    "Pasting several hundred lines of messy code is unlikely to get any help "
    "soon.\n"
    "• Description of the environment. Does it happen with users, bots, in "
    "private chats, groups, megagroups, broadcast channels, with proxy, with "
    "certain messages, media, datacenters… You get the idea. Include "
    "everything that may be relevant, and even provide the media / message / "
    "link if possible.\n"
    "• [Search for your issue first](https://github.com/LonamiWebs/Telethon/"
    "issues). It might already have been fixed.\n"
    "• Make sure you __truly__ are using the latest version. Run your code "
    "with `import telethon; print(telethon.__version__)` to verify this."
)


async def init(bot):
    @bot.on(events.NewMessage(pattern='#full', forwards=False))
    async def handler(event):
        """#full: Advises to read "Accessing the full API" in the docs."""
        await asyncio.wait([
            event.delete(),
            event.respond(READ_FULL, reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='#search (.+)', forwards=False))
    async def handler(event):
        """#search query: Searches for "query" in the method reference."""
        query = urllib.parse.quote(event.pattern_match.group(1))
        await asyncio.wait([
            event.delete(),
            event.respond(SEARCH.format(query), reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#ref (.+)', forwards=False))
    async def handler(event):
        """#ref query: Like #search but shows the query."""
        q1 = event.pattern_match.group(1)
        q2 = urllib.parse.quote(q1)
        await asyncio.wait([
            event.delete(),
            event.respond(DOCS.format(q1, q2), reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='#(?:rt(f)?d|docs)', forwards=False))
    async def handler(event):
        """#docs or #rtd: Tells the user to please read the docs."""
        rtd = RTFD if event.pattern_match.group(1) else RTD
        await asyncio.wait([
            event.delete(),
            event.respond(rtd, reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='#(updates|events)', forwards=False))
    async def handler(event):
        """#updates: Advices the user to read "Working with Updates"."""
        await asyncio.wait([
            event.delete(),
            event.respond(UPDATES, reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#(ask|question)', forwards=False))
    async def handler(event):
        """#ask or #question: Advices the user to ask a better question."""
        await asyncio.wait([
            event.delete(),
            event.respond(
                ASK, reply_to=event.reply_to_msg_id, link_preview=False)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#spam(mer|ming)?', forwards=False))
    async def handler(event):
        """#spam, #spammer, #spamming: Informs spammers that they are not welcome here."""
        await asyncio.wait([
            event.delete(),
            event.respond(SPAM, reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#(ot|offtopic)', forwards=False))
    async def handler(event):
        """#ot, #offtopic: Tells the user to move to @TelethonOffTopic."""
        await asyncio.wait([
            event.delete(),
            event.respond(OFFTOPIC.get(event.chat_id, UNKNOWN_OFFTOPIC), reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#topic', forwards=False))
    async def handler(event):
        """#topic: Explains the topic of the group to the user."""
        await asyncio.wait([
            event.delete(),
            event.respond(TOPIC, reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#log(s|ging)?', forwards=False))
    async def handler(event):
        """#log, #logs or #logging: Explains how to enable logging."""
        await asyncio.wait([
            event.delete(),
            event.respond(LOGGING, reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#master', forwards=False))
    async def handler(event):
        """#master: The bug has been fixed in the `master` branch."""
        await asyncio.wait([
            event.delete(),
            event.respond(ALREADY_FIXED, reply_to=event.reply_to_msg_id)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#(learn|python)', forwards=False))
    async def handler(event):
        """#learn or #python: Tells the user to learn some Python first."""
        await asyncio.wait([
            event.delete(),
            event.respond(
                LEARN_PYTHON, reply_to=event.reply_to_msg_id, link_preview=False)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#bugs?', forwards=False))
    async def handler(event):
        """#bug or #bugs: Advices the user to report bugs in GitHub."""
        await asyncio.wait([
            event.delete(),
            event.respond(
                BUG_REPORT, reply_to=event.reply_to_msg_id, link_preview=False)
        ])


    @bot.on(events.NewMessage(pattern='(?i)#(list|help)', forwards=False))
    async def handler(event):
        await event.delete()
        text = 'Available commands:\n'
        for callback, handler in bot.list_event_handlers():
            if isinstance(handler, events.NewMessage) and callback.__doc__:
                text += f'\n{callback.__doc__.strip()}'
        text += '\n\nYou can suggest new commands [here](https://docs.google.com/'\
                'spreadsheets/d/12yWwixUu_vB426_toLBAiajXxYKvR2J1DD6yZtQz9l4/edit).'

        message = await event.respond(text, link_preview=False)
        await asyncio.sleep(1 * text.count(' '))  # Sleep ~1 second per word
        await message.delete()


    @bot.on(events.InlineQuery)
    async def handler(event):
        builder = event.builder
        result = None
        query = event.text.lower()
        if query == 'ping':
            result = builder.article('Pong!', text='This bot works inline')
        elif query == 'group':
            result = builder.article(
                'Move to the right group!',
                text='Try moving to the [right group](t.me/TelethonChat)',
                buttons=custom.Button.url('Join the group!', 't.me/TelethonChat'),
                link_preview=False
            )
        elif query in ('python', 'learn'):
            result = builder.article(
                'Resources to Learn Python',
                text=GOOD_RESOURCES,
                link_preview=False
            )

        # NOTE: You should always answer, but we want plugins to be able to answer
        #       too (and we can only answer once), so we don't always answer here.
        if result:
            await event.answer([result])
