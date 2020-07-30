import time
from telethon import events, types
from dataclasses import dataclass
from typing import Optional


def extract_command(message):
    for (ent, txt) in message.get_entities_text():
        if ent.offset != 0:
            break

        if isinstance(ent, types.MessageEntityBotCommand):
            return txt


async def init(bot):
    me = None

    waiting_question = set()  # user ids waiting for a question
    question_to_user = {}  # question msg id to user id who asked
    ask_time = {}  # user id to time they asked

    question_delay = 10 * 60

    @bot.on(events.NewMessage(pattern=r'/start', func=lambda e: e.is_private))
    async def _(event):
        nonlocal me
        if me is None:
            me = await bot.get_me()

        await event.respond(
            f'Hi, my name is {me.first_name} and I am the assistant bot used in the '
            '[Telethon group](https://t.me/TelethonChat). You can send "#help" without quotes '
            'to view the available commands you may use in the group to help other people.\n\n'
            'If your country is restricted and does not allow you to speak in the group, send '
            '/ask here to ask a question. I will forward it to the group for you so others can '
            'answer it.',
            link_preview=False
        )
        raise events.StopPropagation

    @bot.on(events.NewMessage(pattern=r'/ask', func=lambda e: e.is_private))
    async def _(event):
        delta = time.time() - ask_time.get(event.sender_id, 0)
        if delta < question_delay:
            await event.respond(
                'You already asked a few moments ago. Please wait for longer before asking again.'
            )
            return

        await event.respond(
            'Send me your question and I will forward it to the [Telethon group]'
            '(https://t.me/TelethonChat) for others to be able to help you. I will forward '
            'replies to your last question back here for a while.\n\n'
            'If you need to share code, please use a paste service like pastebin.com, '
            'hastebin.com or del.dog (I will not forward media).\n\n'
            'You may also send /cancel to avoid asking.',
            link_preview=False
        )
        ask_time.pop(event.sender_id, None)
        waiting_question.add(event.sender_id)
        raise events.StopPropagation

    @bot.on(events.NewMessage(func=lambda e: e.is_private))
    async def _(event):
        if event.sender_id not in waiting_question:
            return

        if event.media and not event.web_preview:
            await event.respond(
                'Please do not use media. If you need to share code use a paste service '
                'like pastebin.com, hastebin.com or del.dog.'
            )
            return

        waiting_question.remove(event.sender_id)

        cmd = extract_command(event)
        if cmd == '/cancel':
            await event.respond('Okay, question cancelled.')
        elif cmd:
            await event.respond(
                'Please send your question, not a command. If you no longer want to send '
                'a question, use the /cancel command.'
            )
        else:
            message = await event.forward_to('TelethonChat')
            question_to_user[message.id] = event.sender_id
            ask_time[event.sender_id] = time.time()
            await event.respond(
                f'[I have sent your question](https://t.me/TelethonChat/{message.id}), and I '
                'forward replies to it here for a while.'
            )

    @bot.on(events.NewMessage('TelethonChat', func=lambda e: e.mentioned and e.is_reply))
    async def _(event):
        user = question_to_user.get(event.reply_to_msg_id)
        if user:
            await event.forward_to(user)
