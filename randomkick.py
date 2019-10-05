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
last_talked = {}


async def init(bot):
    global last_talked

    self_id = await bot.get_peer_id('me')

    @bot.on(events.NewMessage(GROUP))
    async def h(e):
        last_talked[e.sender_id] = time.time()

    async def kick_users():
        global chosen
        while True:
            clicked.clear()
            users = await bot.get_participants(GROUP)

            # Delete people who talked before but have left the group
            left = last_talked.keys() - {x.id for x in users}
            for x in left:
                del last_talked[x]

            lo = min(last_talked.values(), default=0)
            hi = time.time()
            delta = hi - lo
            if delta <= 0.0:
                chosen = random.choice(users)
            else:
                weights = (1 - ((last_talked.get(x.id, lo) - lo) / delta) for x in users)
                chosen = random.choices(users, weights)[0]

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
        event = await bot.send_message(
            GROUP,
            '<a href="tg://user?id={}">{}: you have 1 day to click this button or'
            ' you will be automatically kicked</a>'.format(chosen.id, chosen.name),
            buttons=Button.inline('click me to stay', b'alive'), parse_mode='html'
        )

        if chosen.id == self_id:
            await asyncio.sleep(random.randint(10, 20))
            await edit_save(event)
            async with bot.action(GROUP, 'typing'):
                await asyncio.sleep(random.randint(7, 10))
            await bot.send_message(GROUP, 'Oh darn! That was close 😅')

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

        await event.answer('Congrats you are saved')
        await edit_save(event)

    async def edit_save(event):
        # Edits the kick "event" or message and updates the clicked/last talked time
        clicked.set()
        last_talked[chosen.id] = time.time()
        await event.edit(
            f'<a href="tg://user?id={chosen.id}">Congrats '
            f'{chosen.name} you made it!</a>', parse_mode='html')

    # TODO This task is not properly terminated on disconnect
    bot.loop.create_task(kick_users())
