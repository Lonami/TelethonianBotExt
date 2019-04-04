# Adapted from https://github.com/painor/randomkickbot
import asyncio
import datetime
import html
import logging
import random
import time

from telethon import events, utils
from telethon.tl.custom import Button
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights

logging.basicConfig(level=logging.INFO)


GROUP = 'telethonofftopic'
DELAY = 24 * 60 * 60

clicked = asyncio.Event()
chosen = None


async def init(bot):
    async def kick_users():
        global chosen
        while True:
            clicked.clear()
            users = await bot.get_participants(GROUP)
            chosen = random.choice(users)
            chosen.name = html.escape(utils.get_display_name(chosen))
            start = time.time()
            try:
                await kick_user()
            except Exception:
                logging.exception('exception on kick user')

            took = time.time() - start
            wait_after_clicked = 8 * 60 * 60 - took
            if wait_after_clicked > 0:
                await asyncio.sleep(DELAY - took)

    async def kick_user():
        await bot.send_message(
            GROUP,
            '<a href="tg://user?id={}">{}: you have 1 day to click this button or'
            ' you will be automatically kicked</a>'.format(chosen.id, chosen.name),
            buttons=Button.inline('click me to stay', b'alive'), parse_mode='html'
        )

        try:
            await asyncio.wait_for(clicked.wait(), DELAY)
        except asyncio.TimeoutError:
            await bot.send_message(
                GROUP,
                f'<a href="tg://user?id={chosen.id}">{chosen.name} '
                f'was kicked for being inactive</a>', parse_mode='html')

            await bot(EditBannedRequest(GROUP, chosen.id, ChatBannedRights(
                until_date=datetime.timedelta(minutes=1),
                view_messages=True
            )))

    @bot.on(events.CallbackQuery)
    async def save_him(event: events.CallbackQuery.Event):
        if event.data != b'alive':
            return

        if event.sender_id != chosen.id:
            await event.answer('Who are you again?')
            return

        clicked.set()
        await event.answer('Congrats you are saved')
        await event.edit(
            f'<a href="tg://user?id={chosen.id}">Congrats '
            f'{chosen.name} you made it!</a>', parse_mode='html')

    loop = asyncio.get_event_loop()
    loop.create_task(kick_users())
