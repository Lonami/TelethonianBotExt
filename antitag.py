import os

from telethon import events, utils, types

MOST_UNNECESSARILY_REPLIED_TO_PERSON_IN_THE_OFFICIAL_TELETHON_CHAT = 10885151
MURTPITOTC_USERNAME = 'lonami'

PLS_NO_REPLY = (
    f'Please do not reply to {MURTPITOTC_USERNAME}. They really do not like it.'
    ' If you need to quote their messages, use a link, like https://t.me/{}/{}'
)
PLS_NO_TAG = (
    f'Please do not unnecessarily tag {MURTPITOTC_USERNAME}. They really do not like it.'
    f' If you want to mention them in your message, exclude the "@", like "{MURTPITOTC_USERNAME}"'
)

CHAT_USERNAMES = {
    -1001109500936: 'TelethonChat',
    -1001200633650: 'TelethonOfftopic',
}

async def init(bot):
    @bot.on(events.NewMessage)
    async def handler(event):
        m = await event.get_reply_message()
        if m.sender_id == MOST_UNNECESSARILY_REPLIED_TO_PERSON_IN_THE_OFFICIAL_TELETHON_CHAT:
            cu = CHAT_USERNAMES.get(event.chat_id, f'c/{utils.get_peer_id(event.to_id, add_mark=False)}')
            await event.delete()
            await event.respond(PLS_NO_REPLY.format(cu, event.reply_to_msg_id))

        for e, t in event.get_entities_text():
            if (isinstance(e, types.MessageEntityMention) and t.lstrip('@').lower() == MURTPITOTC_USERNAMEO) or (
                    isinstance(e, types.MessageEntityMentionName) and e.user_id == MOST_UNNECESSARILY_REPLIED_TO_PERSON_IN_THE_OFFICIAL_TELETHON_CHAT):
                await event.delete()
                await event.respond(PLS_NO_TAG)
