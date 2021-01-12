from asyncio import sleep

import logging

from telethon.errors import (
    ChannelInvalidError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    UserAdminInvalidError,
)


async def init(bot):
    ACTIVE_CHATS = [-1001109500936, -1001200633650]

    DELAY = 24 * 60 * 60
    DELAY_BETWEEN_CHATS = 10 * 60

    async def delete():
        while True:
            for chat_id in ACTIVE_CHATS:
                try:
                    input_chat = await bot.get_input_entity(chat_id)
                except ValueError:
                    logging.warning(f"Skipping {chat_id} from cleaning. Chat not found!")
                    continue
                async for participant in bot.iter_participants(input_chat):
                    if participant.deleted:
                        try:
                            kick_message = await bot.kick_participant(
                                input_chat, participant.id
                            )
                            await kick_message.delete()
                        except (ChannelInvalidError,
                                ChannelPrivateError,
                                ChatAdminRequiredError,
                                UserAdminInvalidError,):
                            continue
                await sleep(DELAY_BETWEEN_CHATS)
            await sleep(DELAY)

    bot.loop.create_task(delete())
