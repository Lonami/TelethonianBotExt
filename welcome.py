from telethon import events, errors


WELCOME = {
    -1001109500936:
    'Hi and welcome to the group. Before asking any questions, **please** '
    'read [the docs](https://docs.telethon.dev/). Make sure you are '
    'using the latest version with `pip3 install -U telethon`, since most '
    'problems have already been fixed in newer versions.',

    -1001200633650:
    'Welcome to the off-topic group. Feel free to talk, ask or test anything '
    'here, politely. Check the description if you need to test more spammy '
    '"features" of your or other people\'s bots (sed commands too).'
}


async def init(bot):
    last_welcome = {}


    @bot.on(events.ChatAction)
    async def handler(event):
        if event.user_joined:
            if event.chat_id in last_welcome:
                try:
                    await last_welcome[event.chat_id].delete()
                except errors.MessageDeleteForbiddenError:
                    # We believe this happens when trying to delete old messages
                    pass

            last_welcome[event.chat_id] = await event.reply(WELCOME[event.chat_id])
