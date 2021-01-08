from telethon import events, errors

WELCOME = {}

MAIN_WELCOME = (
    'Hi and welcome to the group. Before asking any questions, **please** '
    'read [the docs](https://docs.telethon.dev/). Make sure you are '
    'using the latest version with `pip3 install -U telethon`, since most '
    'problems have already been fixed in newer versions.'
)

WELCOME = {
    -1001109500936: ((MAIN_WELCOME,), {}),
    -1001200633650: ((), {'file': 'hello.webp'}),
}

FAREWELL = {
    -1001200633650: ((), {'file': 'bye.webp'}),
}


async def init(bot):
    last_welcome = {}

    @bot.on(events.ChatAction)
    async def handler(event):
        chat_id = event.chat_id
        joined = event.user_joined or event.user_added
        left = event.user_left or event.user_kicked
        welcome = WELCOME.get(chat_id, None)
        farewell = FAREWELL.get(chat_id, None)
        if not joined and not left:
            return
        if not welcome and not farewell:
            return

        if event.chat_id in last_welcome:
            try:
                await last_welcome[chat_id].delete()
            except errors.MessageDeleteForbiddenError:
                # We believe this happens when trying to delete old messages
                pass

        if joined and welcome:
            args, kwargs = welcome
        if left and farewell:
            args, kwargs = farewell

        await event.reply(*args, **kwargs)
