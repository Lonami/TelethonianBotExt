import time
from telethon.tl.types import (
    ChannelParticipantsAdmins,
    MessageEntityEmail,
    MessageEntityMention,
    MessageEntityMentionName,
    MessageEntityTextUrl,
    MessageEntityUrl
)


async def init(bot):
    # utils = modules['utils']
    
    reporting_time = {}  # user id to time they asked
    reporting_delay = 10 * 60

    @bot.on(events.NewMessage(pattern='(?\/|#)report'))
    async def handler(event):
        # mentions = '<a href="tg://user?id={}">{}</a> '.format(
        #     event.sender_id,
        #     utils.get_display(event.sender)
        # )
        delta = time.time() - reporting_time.get(event.sender_id, 0)
        if delta < reporting_delay:
            return

        reply_message = await event.get_reply_message()
        if not reply_message:
            return
        is_link = any(
            isinstance(
                entity, 
                (
                    MessageEntityEmail,
                    MessageEntityMention,
                    MessageEntityMentionName,
                    MessageEntityTextUrl,
                    MessageEntityUrl
                )
            ) for entity in (reply_message.entities or [])
        )
        if not (
            reply_message.media or 
            is_link
        ):
            return
        mentions = 'Reported to admins.'
        async for x in event.client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
            if not x.bot:
                mentions += f"[\u2063](tg://user?id={x.id})"
        await reply_message.reply(mentions)
        reporting_time[event.sender_id] = time.time()
        await event.delete()
