# Adapted from https://github.com/painor/randomkickbot
import asyncio
import datetime
import html
import logging
import os
import random
import time

from telethon import events, utils
from telethon.tl.custom import Button
from telethon.tl.types import ChatBannedRights

logging.basicConfig(level=logging.INFO)


GROUP = 'telethonofftopic'
DELAY = 24 * 60 * 60
TARGET_FILE = os.path.join(os.path.dirname(__file__), 'randomkick.target')

clicked = asyncio.Event()
chosen = None
last_talked = {}


def pick_target_file(users):
    try:
        with open(TARGET_FILE) as fd:
            target_id, due = map(int, fd)

        os.unlink(TARGET_FILE)
        user = next((u for u in users if u.id == target_id), None)
        return user, due - time.time()

    except OSError:
        pass
    except Exception:
        logging.exception('exception loading previous to-kick')

    return None, None


def pick_random(users):
    lo = min(last_talked.values(), default=0)
    hi = time.time()
    delta = hi - lo
    if delta <= 0.0:
        user = random.choice(users)
    else:
        weights = (1 - ((last_talked.get(x.id, lo) - lo) / delta) for x in users)
        user = random.choices(users, weights)[0]

    return user, DELAY


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

            chosen, delay = pick_target_file(users)
            if chosen is None:
                warn = True
                chosen, delay = pick_random(users)
            else:
                warn = False

            chosen.name = html.escape(utils.get_display_name(chosen))
            start = time.time()
            try:
                await kick_user(delay, warn=warn)
            except Exception:
                logging.exception('exception on kick user')
            finally:
                # This may or may not fix a bug where we spam "kicked inactive"
                # UPDATE: it doesn't fix the bug
                chosen = None

            took = time.time() - start
            wait_after_clicked = 8 * 60 * 60 - took
            if wait_after_clicked > 0:
                # It's OK if it's negative, will sleep(0)
                await asyncio.sleep(delay - took)

    async def kick_user(delay, *, warn):
        with open(TARGET_FILE, 'w') as fd:
            fd.write('{}\n{}\n'.format(chosen.id, int(time.time() + delay)))

        if warn:
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
            await asyncio.wait_for(clicked.wait(), delay)
        except asyncio.TimeoutError:
            await bot.send_message(
                GROUP,
                f'<a href="tg://user?id={chosen.id}">{chosen.name} '
                f'was kicked for being inactive</a>', parse_mode='html')

            await bot.kick_participant(GROUP, chosen.id)

    @bot.on(events.CallbackQuery)
    async def save_him(event: events.CallbackQuery.Event):
        if event.data != b'alive' or not chosen:
            return

        if event.sender_id != chosen.id:
            await event.answer('Who are you again?')
            return

        await event.answer('Congrats you are saved')
        await edit_save(event)

    async def edit_save(event):
        # Edits the kick "event" or message and updates the clicked/last talked time
        clicked.set()
        try:
            os.unlink(TARGET_FILE)
        except OSError:
            pass

        last_talked[chosen.id] = time.time()
        await event.edit(
            f'<a href="tg://user?id={chosen.id}">Congrats '
            f'{chosen.name} you made it!</a>', buttons=None, parse_mode='html')

    # TODO This task is not properly terminated on disconnect
    bot.loop.create_task(kick_users())
