from telethon import events
from telethon.errors.rpcerrorlist import MessageDeleteForbiddenError
from telethon.tl.types import PeerChannel
from telethon.utils import resolve_id

CHATS = [resolve_id(i)[0] for i in [-1001109500936, -1001200633650]]


async def init(bot):
    @bot.on(events.NewMessage)
    async def handler(event):
        chat_id, _ = resolve_id(event.chat_id)
        if isinstance(event.peer_id, PeerChannel):
            if event.peer_id.channel_id not in CHATS:
                try:
                    await event.delete()
                except MessageDeleteForbiddenError:
                    pass
