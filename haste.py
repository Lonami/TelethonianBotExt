import logging
import asyncio
from telethon import events, types


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
        if len(msg.raw_text or '') < 200:
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
                                    json={"content": code}) as resp:
                if resp.status >= 300:
                    await sent.edit("Dogbin seems to be down… ( ^^')")
                    return

                haste = (await resp.json())['key']

        await asyncio.wait([
            msg.delete(),
            sent.edit(f'<a href="tg://user?id={msg.sender_id}">{name}</a> '
                      f'said: {text} del.dog/{haste}.py'
                      .replace('  ', ' '), parse_mode='html')
        ])
