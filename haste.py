import logging, asyncio, re, json
from telethon import events, types


_MAX_MSG_DISTANCE = 10


async def init(bot, modules):
    try:
        import aiohttp
    except ImportError:
        aiohttp = None
        logging.warning("aiohttp module not available; #haste command disabled")
        return

    utils = modules["utils"]

    @bot.on(events.NewMessage(pattern="(?i)#([hp]aste|dog|inu)(bin)?", forwards=False))
    async def handler(event):
        """
        #haste: Replaces the message you reply to with a dogbin link.
        """
        await event.delete()
        if not event.reply_to_msg_id:
            return

        msg = await event.get_reply_message()

        formatter_url = "https://1rctyledh3.execute-api.us-east-1.amazonaws.com/dev"
        payload = {"source": msg.raw_text}
        headers = {"content-type": "application/json"}

        if len(msg.raw_text or "") < 200:
            sent = await event.respond("Not bothering to paste such a short message.")
            await asyncio.sleep(10)
            await sent.delete()
            return

        if event.id - msg.id > _MAX_MSG_DISTANCE:
            sent = await event.respond(
                "The message is too old for a paste to matter now."
            )
            await asyncio.sleep(10)
            await sent.delete()
            return

        sent = await event.respond("Uploading paste…", reply_to=msg.reply_to_msg_id)

        name = utils.get_display(await msg.get_sender())

        text = msg.raw_text
        code = ""
        for _, string in msg.get_entities_text(
            (types.MessageEntityCode, types.MessageEntityPre)
        ):
            code += f"{string}\n"
            text = text.replace(string, "")

        code = code.rstrip()
        if code:
            text = re.sub(r"\s+", " ", text)
        else:
            code = msg.raw_text
            text = ""

        async with aiohttp.ClientSession() as session:
            async with session.post(
                formatter_url, data=json.dumps(payload).encode("utf-8"), headers=headers
            ) as formatter:
                code = (await formatter.json())["formatted_code"]
                if code.startswith("Cannot parse"):
                    await asyncio.gather(
                        await sent.edit(
                            "Cannot parse, are you sure this is the code…?\nUploading to del.dog as is…"
                        ),
                        await asyncio.sleep(1),
                    )

            async with session.post(
                "https://del.dog/documents", data=code.encode("utf-8")
            ) as resp:
                if resp.status >= 300:
                    await sent.edit("Dogbin seems to be down… ( ^^')")
                    return

                haste = (await resp.json())["key"]

        await asyncio.wait(
            [
                msg.delete(),
                sent.edit(
                    f'<a href="tg://user?id={msg.sender_id}">{name}</a> '
                    f"said: {text} del.dog/{haste}.py".replace("  ", " "),
                    parse_mode="html",
                ),
            ]
        )
