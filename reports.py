import time
from typing import Dict, Union, Deque
from collections import deque

from telethon import TelegramClient
from telethon.errors import UserIsBlockedError
from telethon.events import NewMessage
from telethon.tl.custom import Message
from telethon.tl.types import (Channel, ChannelParticipantsAdmins, Chat,
                               MessageEntityEmail, MessageEntityMention,
                               MessageEntityMentionName, MessageEntityTextUrl,
                               MessageEntityUrl, User)


class ReportedMessages:
    def __init__(self):
        self.reported_messages: Deque[int] = deque()
        self.last_time: float = 0.0

    def add(self, msg_id: int):
        self.reported_messages.append(msg_id)
        self.last_time = time.time()

    def is_index_at_max(self, msg_id: int, max_index: int):
        try:
            self.reported_messages.index(msg_id, 0, max_index)
        except ValueError:
            return False
        return True


async def init(bot: TelegramClient):
    COOLDOWN = 10 * 60
    REPORTS: Dict[int, ReportedMessages] = {}
    MAX_N_REPORTS = 5

    @bot.on(NewMessage(
        pattern=r"^(#|\/)report",
        func=lambda e: not e.is_private and e.is_reply
    ))
    async def report(event: Message):
        reports: Union[ReportedMessages, None] = REPORTS.get(event.chat_id, None)
        reply_message: Message = await event.get_reply_message()

        if not (event.file or any(isinstance(entity, (
            MessageEntityEmail,
            MessageEntityMention,
            MessageEntityMentionName,
            MessageEntityTextUrl,
            MessageEntityUrl,
        )) for entity in (reply_message.entities or ()))):
            await event.delete()
            return

        if reports:
            if (time.time() - reports.last_time) < COOLDOWN:
                await event.delete()
                return
            if reports.is_index_at_max(reply_message.id, MAX_N_REPORTS):
                await event.delete()
                return
            reports.add(reply_message.id)
            REPORTS[event.chat_id] = reports
        else:
            reports = ReportedMessages()
            reports.add(reply_message.id)
            REPORTS[event.chat_id] = reports

        sender: User = await event.get_sender()
        chat: Union[Chat, Channel] = await event.get_chat()

        async for admin in bot.iter_participants(
                event.chat_id, filter=ChannelParticipantsAdmins
        ):
            admin: User
            if not admin.bot:
                try:
                    await bot.send_message(
                        admin.id,
                        f"[{sender.first_name}](t.me/{sender.id}) reported a [message](t.me/{chat.username}/{reply_message.id}) in [{chat.title}](t.me/{chat.username})",
                    )
                except (UserIsBlockedError, ValueError):
                    pass
        await reply_message.reply(
            f"[{sender.first_name}](t.me/{sender.id}) reported this message to admins"
        )
