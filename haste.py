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
        if msg.photo:
            await event.respond('Don\'t send photos with your code or errors. Paste the content in del.dog instead.')
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
            async with session.post('https://del.dog/documents',
                                    data=code.encode('utf-8')) as resp:
                if resp.status >= 300:
                    async with session.post(
                        "https://nekobin.com/api/documents", json={"content": code}) as r:
                        if r.status >= 300:
                            await sent.edit("Both del.dog and nekobin.com seem to be down… ( ^^')")
                            return
                        paste = f"nekobin.com/{(await r.json())['result']['key']}.py"
                else:
                    paste = f"del.dog/{(await resp.json())['key']}.py"

        await asyncio.wait([
            msg.delete(),
            sent.edit(f'<a href="tg://user?id={msg.sender_id}">{name}</a> '
                      f'said: {text} {paste}'
                      .replace('  ', ' '), parse_mode='html')
        ])
