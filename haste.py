import logging
import asyncio
import re
from telethon import events, types


_MAX_MSG_DISTANCE = 10


async def init(bot, modules):
    try:
        import aiohttp
    except ImportError:
        aiohttp = None
        logging.warning('aiohttp module not available; #haste command disabled')
        return

    utils = modules['utils']

    @bot.on(events.NewMessage(pattern='(?i)#([hp]aste|dog|inu)(bin)?', forwards=False))
    async def handler(event):
        """
        #haste: Replaces the message you reply to with a dogbin link.
        """
        await event.delete()
        if not event.reply_to_msg_id:
            return

        msg = await event.get_reply_message()
        if msg.photo or msg.document:
            await event.respond('Hey, that\'s not how you send faulty code or an error returned by the library.' \
                               ' Please send a minimal reproducible code.' \
                               '\nWhen sending a code snippet or error use either nekobin.com or any other preferred pastebin website.')
            return
        if len(msg.raw_text or '') < 200:
            sent = await event.respond('Not bothering to paste such a short message.')
            await asyncio.sleep(10)
            await sent.delete()
            return

        if event.id - msg.id > _MAX_MSG_DISTANCE:
            sent = await event.respond('The message is too old for a paste to matter now.')
            await asyncio.sleep(10)
            await sent.delete()
            return

        sent = await event.respond(
            'Uploading paste…', reply_to=msg.reply_to_msg_id)

        name = utils.get_display(await msg.get_sender())

        text = msg.raw_text
        code = ''
        for _, string in msg.get_entities_text((
                types.MessageEntityCode, types.MessageEntityPre)):
            code += f'{string}\n'
            text = text.replace(string, '')

        code = code.rstrip()
        if code:
            text = re.sub(r'\s+', ' ', text)
        else:
            code = msg.raw_text
            text = ''

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://pasty.lus.pm/api/v2/pastes",
                json={"content": code},
                headers={
                    "User-Agent": "TelethonianBot/Version",
                    "Content-Type": "application/json",
                }
            ) as r:
                if r.status >= 300:
                    await sent.edit("pasty seems to be down… ( ^^')")
                    return
                paste = f"pasty.lus.pm/{(await r.json())['id']}"

            await asyncio.gather(
                msg.delete(),
                sent.edit(f'<a href="tg://user?id={msg.sender_id}">{name}</a> '
                        f'said: {text} {paste}'
                        .replace('  ', ' '), parse_mode='html')
            )
