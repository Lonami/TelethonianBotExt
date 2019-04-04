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

try:
    import pickle
    chosen = pickle.loads(open('CHOSEN.pd', 'rb').read())
except FileNotFoundError:
    pickle.dump(None, open('CHOSEN.pd', 'wb'))
    chosen = None


async def init(bot):
    async def kick_users():
        global chosen
        while True:
            clicked.clear()
            users = await bot.get_participants(GROUP)
            start = time.time()
            if chosen is None or not (user for user in users if chosen.id == user.id):
                bot_user = await bot.get_me()
                chosen = bot_user
                while chosen == bot_user or chosen.bot:
                    chosen = random.choice(users)
                chosen.name = html.escape(utils.get_display_name(chosen))
                pickle.dump(chosen, open('CHOSEN.pd', 'wb'))
                try:
                    await kick_user()
                except Exception:
                    logging.exception('exception on kick user')
                    took = time.time() - start
                    wait_after_clicked = 8 * 60 * 60 - took
                    if wait_after_clicked > 0:
                        await asyncio.sleep(DELAY - took)


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
        global chosen
        if event.data != b'alive':
            return

        if chosen is None or event.sender_id != chosen.id:
            await event.answer('Who are you again?')
            return
        chosen = None
        pickle.dump(None, open('CHOSEN.pd', 'wb'))
        clicked.set()
        await event.answer('Congrats you are saved')
        await event.edit(
            f'<a href="tg://user?id={chosen.id}">Congrats '
            f'{chosen.name} you made it!</a>', parse_mode='html')

    loop = asyncio.get_event_loop()
    loop.create_task(kick_users())
