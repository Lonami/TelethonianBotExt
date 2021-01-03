from telethon.tl.types import ChannelParticipantsAdmins


async def init(bot):
    # utils = modules['utils']

    @bot.on(events.NewMessage(pattern='\/report'))
    async def handler(event):
        # mentions = '<a href="tg://user?id={}">{}</a> '.format(
        #     event.sender_id,
        #     utils.get_display(event.sender)
        # )
        mentions = 'Reported to admins.'
        async for x in event.client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
            if not x.bot:
                mentions += f"[\u2063](tg://user?id={x.id})"
        if event.reply_to_msg_id:
            reply_message = await event.get_reply_message()
            await reply_message.reply(mentions)
        else:
            await event.reply(mentions)
        await event.delete()
