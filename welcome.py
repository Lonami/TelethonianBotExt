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
    -1001200633650: ((), {'file': 'plugins/hello.webp'}),
}

FAREWELL = {
    -1001200633650: ((), {'file': 'plugins/bye.webp'}),
}


async def delete(map, chat_id):
    msg = map.pop(chat_id, None)
    if msg:
        try:
            await msg.delete()
        except errors.MessageDeleteForbiddenError:
            # We believe this happens when trying to delete old messages
            pass


async def init(bot):
    last_welcome = {}
    last_farewell = {}

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

        if joined and welcome:
            args, kwargs = welcome
            last_map = last_welcome
        if left and farewell:
            args, kwargs = farewell
            last_map = last_farewell

        await delete(last_map, chat_id)
        last_map[chat_id] = await event.reply(*args, **kwargs)
