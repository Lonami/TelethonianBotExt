# Adapted from https://github.com/painor/randomkickbot
import asyncio
import datetime
import logging
import os
import random
import time

from telethon import events, utils, errors
from telethon.tl.custom import Button
from telethon.tl.types import ChatBannedRights

logging.basicConfig(level=logging.INFO)


GROUP = 'telethonofftopic'
DELAY = 24 * 60 * 60
TARGET_FILE = os.path.join(os.path.dirname(__file__), 'randomkick.target')

utils = None
chosen = None
last_talked = {}


class Chosen:
    def __init__(self, user):
        self.id = user.id
        self.name = utils.get_display(user)
        self._clicked = asyncio.Event()

    async def wait_save(self, delay):
        await asyncio.wait_for(self._clicked.wait(), delay)

    def clicked_save(self):
        self._clicked.set()


def pick_target_file(users):
    try:
        with open(TARGET_FILE) as fd:
            target_id, due = map(int, fd)

        user = next((u for u in users if u.id == target_id), None)
        return user, due - time.time()
    except FileNotFoundError:
        pass
    except Exception:
        logging.exception('exception loading previous to-kick')

    return None, None


def save_target_file(user, delay):
    try:
        with open(TARGET_FILE, 'w') as fd:
            fd.write('{}\n{}\n'.format(user.id, int(time.time() + delay)))
    except Exception:
        logging.exception('could not save target file')


def remove_target_file():
        try:
            os.unlink(TARGET_FILE)
        except FileNotFoundError:
            pass
        except OSError:
            logging.exception('could not remove target file')


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


async def init(bot, modules):
    global last_talked, utils
    utils = modules['utils']

    self_id = await bot.get_peer_id('me')

    @bot.on(events.NewMessage(GROUP))
    async def h(e):
        last_talked[e.sender_id] = time.time()

    async def kick_users():
        while True:
            users = await bot.get_participants(GROUP)

            # Delete people who talked before but have left the group
            left = last_talked.keys() - {x.id for x in users}
            for x in left:
                del last_talked[x]

            user, delay = pick_target_file(users)
            if user is None:
                warn = True
                user, delay = pick_random(users)
                save_target_file(user, delay)
            else:
                warn = False

            global chosen
            try:
                chosen = Chosen(user)
                await kick_user(delay, warn=warn)
            except Exception:
                logging.exception('exception on kick user')
            finally:
                chosen = None
                remove_target_file()

            await asyncio.sleep(8 * 60 * 60)

    async def kick_user(delay, *, warn):
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
            await chosen.wait_save(delay)
        except asyncio.TimeoutError:
            try:
                await bot.kick_participant(GROUP, chosen.id)
            except errors.UserAdminInvalidError:
                await bot.send_message(
                    GROUP,
                    f'Guess I cannot kick <a href="tg://user?id={chosen.id}">{chosen.name}</a>'
                    f' for being inactive… Darned admin priviledges. You should talk more!',
                    parse_mode='html')
            else:
                await bot.send_message(
                    GROUP,
                    f'<a href="tg://user?id={chosen.id}">{chosen.name} '
                    f'was kicked for being inactive</a>', parse_mode='html')

    @bot.on(events.CallbackQuery)
    async def save_him(event: events.CallbackQuery.Event):
        if not chosen or event.data != b'alive':
            return

        if event.sender_id != chosen.id:
            await event.answer('Who are you again?')
            return

        await event.answer('Congrats you are saved')
        await edit_save(event)

    async def edit_save(event):
        # Edits the kick "event" or message and updates the clicked/last talked time
        #
        # When this is clicked `kick_user` should stop waiting without timeout and
        # finally after it's donen chosen / target file be cleared.
        chosen.clicked_save()
        last_talked[chosen.id] = time.time()

        await event.edit(
            f'<a href="tg://user?id={chosen.id}">Congrats '
            f'{chosen.name} you made it!</a>', buttons=None, parse_mode='html')

    # TODO This task is not properly terminated on disconnect
    bot.loop.create_task(kick_users())
