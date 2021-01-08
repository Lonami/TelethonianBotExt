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
        joined = event.user_joined or event.user_added
        left = event.user_left or event.user_kicked
        chat_id = event.chat_id

        if not joined and not left:
            return
        if event.chat_id in last_welcome:
            try:
                await last_welcome[chat_id].delete()
            except errors.MessageDeleteForbiddenError:
                # We believe this happens when trying to delete old messages
                pass

        file = None
        text = None

        if joined and chat_id in WELCOME:
            text = WELCOME[chat_id][0][0]
            extra = WELCOME[chat_id][1]
            if extra:
                # Get extra values from the dict and pass them to event.reply [ex files, parameters]
                file = extra.get('file', None)
        if left and chat_id in FAREWELL.keys():
            text = FAREWELL[chat_id][0][0]
            extra = FAREWELL[chat_id][1]
            if extra:
                # Get extra values from the dict and pass them to event.reply [ex files, parameters]
                file = extra.get('file', None)

        if file:
            file = await bot.upload_file(file)

        last_welcome[event.chat_id] = await event.reply(text, file=file)