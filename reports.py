import time
from typing import List, Union

from telethon import TelegramClient
from telethon.errors import UserIsBlockedError
from telethon.events import NewMessage
from telethon.tl.custom import Message
from telethon.tl.types import (
    Channel,
    ChannelParticipantsAdmins,
    Chat,
    MessageEntityEmail,
    MessageEntityMention,
    MessageEntityMentionName,
    MessageEntityTextUrl,
    MessageEntityUrl,
    User,
)


class ReportedMessage:
    def __init__(
        self, msg_id: int, reported_by: int, reported_in: int, report_time: float
    ):
        self.msg_id: int = msg_id
        self.reported_by: int = reported_by
        self.reported_in: int = reported_in
        self.report_time: float = report_time


REPORTS: List[ReportedMessage] = []


async def init(bot: TelegramClient):
    COOLDOWN = 10 * 60
    MAX_N_REPORTED = 1

    @bot.on(
        NewMessage(
            pattern=r"^(#|\/)report", func=lambda e: not e.is_private and e.is_reply
        )
    )
    async def report(event: Message):
        global REPORTS

        reply_message: Message = await event.get_reply_message()

        if REPORTS:
            reported_chat: List[ReportedMessage] = [
                x for x in REPORTS if x.reported_in == event.chat_id
            ]
            reported_messages: List[ReportedMessage] = [
                x for x in REPORTS if x.msg_id == reply_message.id
            ]
            if reported_chat:
                if (time.time() - reported_chat[0].report_time) < COOLDOWN:
                    await event.delete()
                    return
                elif len(reported_messages) >= MAX_N_REPORTED:
                    await event.delete()
                    return
                else:
                    REPORTS = [x for x in REPORTS if x.reported_in != event.chat_id]

        if not (
            any(
                isinstance(
                    entity,
                    (
                        MessageEntityEmail,
                        MessageEntityMention,
                        MessageEntityMentionName,
                        MessageEntityTextUrl,
                        MessageEntityUrl,
                    ),
                )
                for entity in (reply_message.entities or ())
            )
            and not bool(event.file)
        ):
            await event.delete()
            return
        if bool([x for x in REPORTS if x.msg_id == reply_message.id]):
            await event.delete()
            return

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
                except UserIsBlockedError:
                    pass
        await reply_message.reply(
            f"[{sender.first_name}](t.me/{sender.id}) reported this message to admins"
        )
        REPORTS.append(
            ReportedMessage(
                reply_message.id, event.sender_id, event.chat_id, time.time()
            )
        )
