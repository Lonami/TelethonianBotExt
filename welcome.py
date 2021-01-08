from telethon import events, errors


WELCOME = 'Hi and welcome to the group. Before asking any questions, **please** '\
          'read [the docs](https://docs.telethon.dev/). Make sure you are '\
          'using the latest version with `pip3 install -U telethon`, since most '\
          'problems have already been fixed in newer versions.'


async def init(bot):
    last_welcome = {}

    @bot.on(events.ChatAction)
    async def handler(event):
        if event.user_joined or event.user_added:
            if event.chat_id in last_welcome:
                try:
                    await last_welcome[event.chat_id].delete()
                except errors.MessageDeleteForbiddenError:
                    # We believe this happens when trying to delete old messages
                    pass
            if event.chat_id == -1001109500936:
                last_welcome[event.chat_id] = await event.reply(WELCOME)
            else:
                file = await bot.upload_file('hello.webp')
                last_welcome[event.chat_id] = await event.reply(file=file)
        if event.user_left or event.user_kicked:
            if event.chat_id != -1001109500936:
                file = await bot.upload_file('bye.webp')
                last_welcome[event.chat_id] = await event.reply(file=file)
