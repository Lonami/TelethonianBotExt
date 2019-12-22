import multiprocessing
import re
from collections import defaultdict, deque

from telethon import events

last_msgs = defaultdict(lambda: deque(maxlen=10))
last_replies = defaultdict(lambda: deque(maxlen=10))

SED_PATTERN = re.compile(r'^s/((?:\\/|[^/])+)/((?:\\/|[^/])*)/?(.*)')
PREFIX = '「sed」\n'


class UnknownFlag(ValueError):
    def __init__(self, flag):
        super().__init__(f'unknown flag: {flag}')
        self.flag = flag


def timeout(func, n, *args):
    def proc(pf, po, *pa):
        try:
            po.send((pf(*pa), None))
        except BaseException as e:
            po.send((None, e))

    inp, out = multiprocessing.Pipe()
    p = multiprocessing.Process(target=proc, args=(func, out, *args))
    p.start()
    p.join(n)
    if p.is_alive():
        p.terminate()
        p.join()
        raise TimeoutError('Process {} timed out after {}'.format(func, n))
    elif inp.poll(n):
        res, err = inp.recv()
        if err:
            raise err
        else:
            return res
    else:
        raise ChildProcessError('Process exited without sending data')


def build_substitute(pattern, repl, flag_str):
    repl = repl.replace('\\/', '/').replace('\\0', '\\g<0>')

    count = 1
    flags = 0
    for f in (flag_str or ''):
        if f in 'Gg':
            count = 0
            continue

        try:
            flags |= getattr(re.RegexFlag, f.upper())
        except AttributeError:
            raise UnknownFlag(f) from None

    def substitute(string):
        if string.startswith(PREFIX):
            string = string[len(PREFIX):]

        s, i = re.subn(pattern, repl, string, count=count, flags=flags)
        if i > 0:
            return PREFIX + s

    return substitute


async def init(bot):
    @bot.on(events.NewMessage(pattern=SED_PATTERN))
    async def handler(event):
        if event.is_reply:
            messages = [await event.get_reply_message()]
        else:
            messages = reversed(last_msgs[event.chat_id])

        try:
            substitute = build_substitute(*event.pattern_match.groups())
        except UnknownFlag as e:
            await event.reply(str(e))
            return

        for message in messages:
            try:
                new = timeout(substitute, 0.2, message.raw_text)
            except TimeoutError:
                await message.reply('are you… trying to DoS me?')
                break
            except Exception as e:
                string = str(e).strip()
                if string:
                    await message.reply('you caused a {}, dummy'.format(type(e).__name__))
                else:
                    await message.reply('you caused "{}", dummy'.format(string))

            if new is None:
                continue

            try:
                sent = await message.reply(new, parse_mode=None)
            except Exception as e:
                await message.reply('owh :(\n' + str(e))
            else:
                last_msgs[event.chat_id].append(sent)
                where = event.chat_id if event.is_channel else None
                last_replies[where].append((event.id, sent.id))

            break

        raise events.StopPropagation

    @bot.on(events.NewMessage)
    async def handler(event):
        last_msgs[event.chat_id].append(event.message)

    @bot.on(events.MessageDeleted)
    async def handler(event):
        for src, dst in last_replies[event.chat_id]:
            if src in event.deleted_ids:
                await bot.delete_messages(event.chat_id, dst)
