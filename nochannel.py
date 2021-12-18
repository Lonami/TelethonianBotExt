from telethon import events
from telethon.errors.rpcerrorlist import MessageDeleteForbiddenError
from telethon.tl.types import PeerChannel
from telethon.utils import resolve_id

CHATS = [-1001109500936, -1001200633650]


async def init(bot):
    @bot.on(events.NewMessage(chats=CHATS))
    async def handler(event):
        if isinstance(event.from_id, PeerChannel):
            if event.from_id.channel_id not in CHATS:
                try:
                    await event.delete()
                except MessageDeleteForbiddenError:
                    pass
