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
    
    reporting_time = {}  # chat_id to time of report
    REPORT_DELAY = 10 * 60

    @bot.on(events.NewMessage(pattern='(?\/|#)report'))
    async def handler(event):
        delta = time.time() - reporting_time.get(event.chat_id, 0)
        if delta < REPORT_DELAY:
            return

        reply_message = await event.get_reply_message()
        if not reply_message:
            return
        has_links = any(isinstance(entity, (
            MessageEntityEmail,
            MessageEntityMention,
            MessageEntityMentionName,
            MessageEntityTextUrl,
            MessageEntityUrl,
        )) for entity in (reply_message.entities or ()))
        if not reply_message.media and not has_links:
            return
        mentions = 'Reported to admins.'
        async for x in event.client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
            if not x.bot:
                mentions += f"[\u2063](tg://user?id={x.id})"
        await reply_message.reply(mentions)
        reporting_time[event.chat_id] = time.time()
        await event.delete()
