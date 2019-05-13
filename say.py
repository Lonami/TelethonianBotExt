from telethon import events


async def init(bot):
    @bot.on(events.NewMessage(pattern=r'#say\s+.', from_users=10885151))
    async def handler(event):
        await event.delete()
        await event.respond(event.text[4:], reply_to=event.reply_to_msg_id)
