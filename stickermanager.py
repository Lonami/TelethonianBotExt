import os
import json
import asyncio
from time import time
from io import BytesIO
from pathlib import Path
from html import escape as escape_html
from typing import Union, NamedTuple, Callable, Optional, Tuple

from PIL import Image

from telethon.tl.custom import Message, Button
from telethon.tl.types import (
    InputStickerSetID, InputStickerSetShortName, InputStickerSetItem,
    InputDocument, InputMediaUploadedDocument, InputPeerSelf
)
from telethon.tl.types.messages import StickerSet
from telethon.tl.functions.stickers import CreateStickerSetRequest, AddStickerToSetRequest
from telethon.tl.functions.messages import UploadMediaRequest, GetStickerSetRequest
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.errors import StickersetInvalidError, UserNotParticipantError
from telethon import events, utils, TelegramClient, errors

POLL_TEMPLATE = (
    '<a href="tg://user?id={sender_id}">{sender_name}</a> has suggested this '
    'sticker be added to <a href="{pack_link}">the group\'s sticker pack</a> '
    'with the emoji {emoji}.\n\n'
    '<strong>Current result: {score}</strong>\n'
    'For: {yes}\n'
    'Against: {no}'
)

POLL_FINISHED_TEMPLATE = (
    '<strong>This sticker poll finished with a final score of {score}. {result}</strong>\n\n'
    '<a href="tg://user?id={sender_id}">{sender_name}</a> had suggested this '
    'sticker be added to the group\'s sticker pack with the emoji {emoji}.\n\n'
    'For: {yes}\n'
    'Against: {no}'
)

POLL_DELETED_ANGER = (
    'Wait… who the fu*ck deleted my sticker poll? 3:<'
)

VOTE_TEMPLATE = '<a href="tg://user?id={uid}">{displayname}</a> ({weight})'

RESULT_ADDED = 'The sticker has been added to <a href="{pack_link}">the pack</a>.'
RESULT_REJECTED = 'The sticker was rejected from <a href="{pack_link}">the pack</a>.'

UP = '\U0001f53c'
DOWN = '\U0001f53d'
UP_DAT = b'addsticker/+'
DOWN_DAT = b'addsticker/-'

POLL_TIMEOUT = ADD_COOLDOWN = 24 * 60 * 60

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / 'stickermanager.tsv'
CACHE_FILE = BASE_DIR / 'stickermanager.json'
DATA_FILE_FORMAT: str = 'stickermanager.{ts}.dat'

VoteData = NamedTuple('VoteData', weight=int, displayname=str)
Number = Union[int, float]
Scores = NamedTuple('Scores', sum=Number, yes=Number, no=Number, yes_count=int, no_count=int)

current_vote: Optional[dict] = None
current_vote_lock: asyncio.Lock = asyncio.Lock()
current_vote_status: asyncio.Event = asyncio.Event()
last_accepted: int = 0
sticker_pack = None

with open(CONFIG_FILE) as f:
    WEIGHTS = {
        int(uid) if uid.strip().isnumeric() else uid:
            (0 if weight == '-' else float(weight), None if name == '-' else name)
        for uid, weight, name
        in (line.strip().split('\t', 2)
            for line in f
            if line and not line.startswith('#') and not line.isspace())
    }

    VOTES_REQUIRED = WEIGHTS.pop('votes required')[0]
    DEFAULT_WEIGHT = WEIGHTS.pop('default weight')[0]
    STICKER_PACK_TITLE = WEIGHTS.pop('sticker title')[1]
    STICKER_PACK_SHORT_NAME = WEIGHTS.pop('sticker short')[1]
    ADMIN_USER_ID = int(WEIGHTS.pop('sticker owner')[1])
    ALLOWED_CHATS = [int(gid)
                     for gid in WEIGHTS.pop('allowed chats')[1].split(',')
                     if not gid.isspace()]


def load_cache() -> None:
    global sticker_pack, current_vote, last_accepted
    try:
        with open(CACHE_FILE) as file:
            data = json.load(file)
            sp_data = data['sticker_pack']
            if sp_data:
                sticker_pack = InputStickerSetID(id=sp_data['id'], access_hash=sp_data['access_hash'])
            cv_data = data['current_vote']
            if cv_data:
                current_vote = cv_data
                current_vote['votes'] = {int(uid): VoteData(*data)
                                         for uid, data in cv_data['votes'].items()}
            last_accepted = data['last_accepted'] or 0
    except OSError:
        pass


def save_cache() -> None:
    with open(CACHE_FILE, 'w') as file:
        json.dump({
            'sticker_pack': {
                'id': sticker_pack.id,
                'access_hash': sticker_pack.access_hash
            } if sticker_pack else None,
            'last_accepted': last_accepted,
            'current_vote': current_vote,
        }, file)


async def create_sticker_pack(bot: TelegramClient, item: InputStickerSetItem
                              ) -> Tuple[bool, Optional[StickerSet]]:
    try:
        stickerset: StickerSet = await bot(GetStickerSetRequest(
            InputStickerSetShortName(STICKER_PACK_SHORT_NAME)))
        created = False
    except StickersetInvalidError:
        stickerset: StickerSet = await bot(CreateStickerSetRequest(
            user_id=ADMIN_USER_ID,
            title=STICKER_PACK_TITLE,
            short_name=STICKER_PACK_SHORT_NAME,
            stickers=[item]
        ))
        created = True
    global sticker_pack
    sticker_pack = InputStickerSetID(id=stickerset.set.id,
                                     access_hash=stickerset.set.access_hash)
    save_cache()
    return created, stickerset


async def add_sticker_to_pack(bot: TelegramClient) -> Tuple[StickerSet, InputDocument]:
    global sticker_pack
    animated = current_vote['animated']
    if animated:
        file = await bot.upload_file(current_vote['filepath'])
        mime = 'application/x-tgsticker'
    else:
        img = Image.open(current_vote['filepath'])
        w, h = img.size
        if w > h:
            img = img.resize((512, int(h * (512 / w))), Image.ANTIALIAS)
        else:
            img = img.resize((int((w * (512 / h))), 512), Image.ANTIALIAS)
        dat = BytesIO()
        img.save(dat, format='PNG')
        file = await bot.upload_file(dat.getvalue())
        mime = 'image/png'
    os.remove(current_vote['filepath'])
    file = InputMediaUploadedDocument(file, mime, [])
    document = await bot(UploadMediaRequest(InputPeerSelf(), file))
    document = utils.get_input_document(document)
    item = InputStickerSetItem(document=document, emoji=current_vote['emoji'])
    pack: Optional[StickerSet] = None
    added = False
    # TODO add support for animated stickers
    if not sticker_pack:
        added, pack = await create_sticker_pack(bot, item)
    if not added:
        pack = await bot(AddStickerToSetRequest(stickerset=sticker_pack, sticker=item))
    return pack, utils.get_input_document(pack.documents[-1])


def get_template_data() -> dict:
    def format_votes(cond: Callable[[Number], bool]) -> str:
        return ', '.join(VOTE_TEMPLATE.format(uid=uid, displayname=displayname, weight=weight)
                         for uid, (weight, displayname) in current_vote['votes'].items()
                         if cond(weight))

    return {
        **current_vote,
        'votes': '',
        'yes': format_votes(lambda weight: weight > 0) or 'nobody',
        'no': format_votes(lambda weight: weight < 0) or 'nobody',
        'pack_link': f'https://t.me/addstickers/{STICKER_PACK_SHORT_NAME}',
    }


def calculate_scores() -> Scores:
    yes = 0.0
    no = 0.0
    yes_count = 0
    no_count = 0
    for vote in current_vote['votes'].values():
        if vote.weight > 0:
            yes += vote.weight
            yes_count += 1
        else:
            no -= vote.weight
            no_count += 1
    return Scores(fancy_round(yes - no), fancy_round(yes), fancy_round(no), yes_count, no_count)


def fancy_round(val: Number) -> Number:
    if isinstance(val, float) and val.is_integer():
        return int(val)
    return round(val, 2)


async def init(bot: TelegramClient) -> None:
    @bot.on(events.NewMessage(pattern='#addsticker (.+)', chats=ALLOWED_CHATS))
    async def start_poll(event: Union[events.NewMessage.Event, Message]) -> None:
        if not event.is_reply:
            return
        elif current_vote:
            poll = await bot.get_messages(current_vote['chat'], ids=current_vote['poll'])
            if poll is not None:
                await event.reply('There\'s already an ongoing sticker poll.')
                return
            else:
                # Will attempt to edit the poll and fail with anger so there's
                # no need to send the anger message here.
                await _locked_finish_poll()

        async with current_vote_lock:
            await _locked_start_poll(event)
            save_cache()

    async def _locked_start_poll(event: Union[events.NewMessage.Event, Message]) -> None:
        global current_vote

        if current_vote:
            await event.reply('There\'s already an ongoing sticker poll.')
            return
        elif last_accepted + ADD_COOLDOWN > int(time()):
            await event.reply('Less than 24 hours have passed since the '
                              'previous sticker was added.')
            return

        emoji = event.pattern_match.group(1)
        try:
            _, sender_name = WEIGHTS[event.sender_id]
        except KeyError:
            await event.reply('Please upgrade to a Telethon OffTopic Premium '
                              'Membership to start sticker polls.')
            return
        orig_evt: Message = await event.get_reply_message()
        # TODO add support for animated stickers
        if not orig_evt.photo and (not orig_evt.sticker or
                                   orig_evt.sticker.mime_type == 'application/x-tgsticker'):
            return

        filename = Path(DATA_FILE_FORMAT.format(ts=int(time())))
        await orig_evt.download_media(filename)

        delete_task = asyncio.ensure_future(event.delete(), loop=bot.loop)
        current_vote_status.clear()
        current_vote = {
            'chat': event.chat_id,
            'started_at': int(time()),
            'sender_id': event.sender_id,
            'sender_name': sender_name,
            'score': 0,
            'emoji': emoji,
            'votes': {},
            'filepath': str(filename),
            'animated': orig_evt.sticker and orig_evt.sticker.mime_type == 'application/x-tgsticker'
        }
        reply_evt: Message = await orig_evt.reply(
            POLL_TEMPLATE.format_map(get_template_data()),
            buttons=[Button.inline(UP, UP_DAT), Button.inline(DOWN, DOWN_DAT)],
            parse_mode='html')
        pin_task = asyncio.ensure_future(reply_evt.pin(), loop=bot.loop)
        current_vote['poll'] = reply_evt.id
        asyncio.ensure_future(wait_for_poll(), loop=bot.loop)
        await asyncio.gather(delete_task, pin_task, loop=bot.loop)

    async def wait_for_poll(timeout: int = POLL_TIMEOUT) -> None:
        try:
            await asyncio.wait_for(current_vote_status.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            async with current_vote_lock:
                await _locked_finish_poll()
                save_cache()

    async def _locked_finish_poll() -> bool:
        global current_vote, last_accepted

        if not current_vote:
            return False

        unpin_task = asyncio.ensure_future(bot.pin_message(current_vote['chat'], message=None),
                                           loop=bot.loop)
        accepted = current_vote['score'] >= VOTES_REQUIRED
        result_tpl = RESULT_ADDED if accepted else RESULT_REJECTED
        current_vote['result'] = result_tpl.format_map(get_template_data())

        try:
            await bot.edit_message(current_vote['chat'], current_vote['poll'],
                                   POLL_FINISHED_TEMPLATE.format_map(get_template_data()),
                                   parse_mode='html')
        except errors.MessageIdInvalidError:
            await bot.send_message(current_vote['chat'], POLL_DELETED_ANGER)

        if accepted:
            pack, document = await add_sticker_to_pack(bot)
            await bot.send_file(current_vote['chat'], file=document, reply_to=current_vote['poll'])
            last_accepted = int(time())
        current_vote = None

        try:
            await unpin_task
        except errors.ChatNotModifiedError:
            pass  # either poll was deleted or pin was removed anyhow else

        return accepted

    @bot.on(events.CallbackQuery(chats=ALLOWED_CHATS, data=lambda data: data in (UP_DAT, DOWN_DAT)))
    async def vote_poll(event: events.CallbackQuery.Event) -> None:
        if not current_vote or current_vote['poll'] != event.message_id:
            await event.answer('That poll is closed.')
            return
        async with current_vote_lock:
            await _locked_vote_poll(event)
            save_cache()

    async def _locked_vote_poll(event: events.CallbackQuery.Event) -> None:
        global current_vote

        if not current_vote or current_vote['poll'] != event.message_id:
            await event.answer('That poll is closed.')
            return

        try:
            await bot(GetParticipantRequest(channel=current_vote["chat"],
                                            user_id=event.input_sender))
        except UserNotParticipantError:
            await event.answer('You\'re not participating in the chat.')
            return

        weight, displayname = WEIGHTS.get(event.sender_id, (DEFAULT_WEIGHT, None))
        if weight == 0:
            await event.answer('You don\'t have the permission to vote.')
            return
        if event.data == b'addsticker/-':
            weight = -weight

        displayname = displayname or escape_html((await event.get_sender()).first_name)
        try:
            existing = current_vote['votes'][event.sender_id]
            if existing.weight == weight:
                await event.answer(f'You already voted {weight}')
                return
        except KeyError:
            pass

        current_vote['votes'][event.sender_id] = VoteData(weight=weight, displayname=displayname)

        scores = calculate_scores()
        current_vote['score'] = scores.sum

        if abs(scores.sum) >= VOTES_REQUIRED:
            current_vote_status.set()
            accepted = await _locked_finish_poll()
            res = 'accepted' if accepted else 'rejected'
            await event.answer(f'Successfully voted {fancy_round(weight)},'
                               f' which made the sticker be {res} \U0001f389')
        else:
            await bot.edit_message(current_vote['chat'], current_vote['poll'],
                                   POLL_TEMPLATE.format_map(get_template_data()),
                                   buttons=[Button.inline(f'{UP} ({scores.yes_count})', UP_DAT),
                                            Button.inline(f'{DOWN} ({scores.no_count})', DOWN_DAT)],
                                   parse_mode='html')
            await event.answer(f'Successfully voted {weight}')

    load_cache()
    if current_vote:
        remaining_time = POLL_TIMEOUT - (int(time()) - current_vote['started_at'])
        if remaining_time < 0:
            async with current_vote_lock:
                await _locked_finish_poll()
                save_cache()
        else:
            asyncio.ensure_future(wait_for_poll(remaining_time))
