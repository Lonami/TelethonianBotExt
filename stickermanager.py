import os
import json
import asyncio
from time import time
from io import BytesIO
from string import Template
from html import escape as escape_html
from typing import Union, NamedTuple, Callable, Optional, Tuple

from PIL import Image

from telethon.tl.custom import Message, Button
from telethon.tl.types import (InputStickerSetID, InputStickerSetItem, InputDocument,
                               InputMediaUploadedDocument, InputPeerSelf, DocumentAttributeAnimated)
from telethon.tl.types.messages import StickerSet
from telethon.tl.functions.stickers import CreateStickerSetRequest, AddStickerToSetRequest
from telethon.tl.functions.messages import UploadMediaRequest
from telethon import events, utils, TelegramClient

POLL_TEMPLATE = Template(
    '<a href="tg://user?id=$sender_id">$sender_name</a> has suggested this sticker be added to the '
    'group\'s sticker pack with the emoji $emoji.\n\n'
    '<strong>Current result: $score</strong>\n'
    'For: $yes\n'
    'Against: $no')

POLL_FINISHED_TEMPLATE = Template(
    '<strong>This sticker poll finished with a final score of $score. $result</strong>\n\n'
    '<a href="tg://user?id=$sender_id">$sender_name</a> had suggested this sticker be added to the '
    'group\'s sticker pack with the emoji $emoji.\n\n'
    'For: $yes\n'
    'Against: $no')

VOTE_TEMPLATE = Template('<a href="tg://user?id=$uid">$displayname</a> ($weight)')

RESULT_ADDED = 'The sticker has been added to the pack.'
RESULT_REJECTED = 'The sticker was rejected from the pack.'

UP = '\U0001f53c'
DOWN = '\U0001f53d'

VoteData = NamedTuple('VoteData', weight=int, displayname=str)
Scores = NamedTuple('Scores', sum=int, yes=int, no=int)

current_vote: Optional[dict] = None
sticker_pack = None

with open(os.path.join(os.path.dirname(__file__), 'stickermanager.tsv')) as f:
    WEIGHTS = {
        int(uid) if uid.strip().isnumeric() else uid:
            (0 if weight == '-' else float(weight), None if name == '-' else name)
        for uid, weight, name
        in (line.strip().split('\t', 2)
            for line in f
            if len(line) > 0 and not line[0] == '#' and not line.isspace())
    }

    VOTES_REQUIRED = WEIGHTS.pop('votes required')[0]
    DEFAULT_WEIGHT = WEIGHTS.pop('default weight')[0]
    STICKER_PACK_TITLE = WEIGHTS.pop('sticker title')[1]
    STICKER_PACK_SHORT_NAME = WEIGHTS.pop('sticker short')[1]
    ADMIN_USER_ID = int(WEIGHTS.pop('sticker owner')[1])
    ALLOWED_CHATS = [int(gid.strip())
                     for gid in WEIGHTS.pop('allowed chats')[1].split(',')
                     if not gid.isspace()]


async def create_sticker_pack(bot: TelegramClient, item: InputStickerSetItem
                              ) -> Tuple[bool, Optional[StickerSet]]:
    global sticker_pack
    try:
        with open(os.path.join(os.path.dirname(__file__), 'stickermanager.json')) as file:
            sp_data = json.load(file)
            sticker_pack = InputStickerSetID(id=sp_data['id'], access_hash=sp_data['access_hash'])
        return False, None
    except (FileNotFoundError, KeyError) as e:
        stickerset: StickerSet = await bot(CreateStickerSetRequest(
            user_id=ADMIN_USER_ID,
            title=STICKER_PACK_TITLE,
            short_name=STICKER_PACK_SHORT_NAME,
            stickers=[item]
        ))
        sticker_pack = InputStickerSetID(id=stickerset.set.id,
                                         access_hash=stickerset.set.access_hash)
        with open(os.path.join(os.path.dirname(__file__), 'stickermanager.json'), 'w') as file:
            json.dump({
                'id': stickerset.set.id,
                'access_hash': stickerset.set.access_hash
            }, file)
        return True, stickerset


async def add_sticker_to_pack(bot: TelegramClient) -> Tuple[StickerSet, InputDocument]:
    global sticker_pack
    if current_vote['animated']:
        file = await bot.upload_file(current_vote['filepath'])
        mime = 'application/x-tgsticker'
    else:
        img = Image.open(current_vote['filepath'])
        w, h = img.size
        if w > 512 or h > 512:
            img.thumbnail((512, 512), Image.ANTIALIAS)
        else:
            if w > h:
                img = img.resize((512, int(h * (512 / w))), Image.ANTIALIAS)
            elif w < h:
                img = img.resize((int((w * (512 / h))), 512), Image.ANTIALIAS)
            else:
                img = img.resize((512, 512), Image.ANTIALIAS)
        dat = BytesIO()
        img.save(dat, format='PNG')
        file = await bot.upload_file(dat.getvalue())
        mime = 'image/png'
    os.remove(current_vote['filepath'])
    file = InputMediaUploadedDocument(file, mime, [DocumentAttributeAnimated()])
    document = await bot(UploadMediaRequest(InputPeerSelf(), file))
    document = utils.get_input_document(document)
    item = InputStickerSetItem(document=document, emoji=current_vote['emoji'])
    pack: Optional[StickerSet] = None
    added = False
    if not sticker_pack:
        added, pack = await create_sticker_pack(bot, item)
    if not added:
        pack = await bot(AddStickerToSetRequest(stickerset=sticker_pack, sticker=item))
    return pack, utils.get_input_document(pack.documents[-1])


def get_template_data() -> dict:
    def format_votes(cond: Callable[[int], bool]) -> str:
        return ', '.join(VOTE_TEMPLATE.substitute(uid=uid, displayname=displayname, weight=weight)
                         for uid, (weight, displayname) in current_vote['votes'].items()
                         if cond(weight))

    return {
        **current_vote,
        'votes': '',
        'yes': format_votes(lambda weight: weight > 0) or 'nobody',
        'no': format_votes(lambda weight: weight < 0) or 'nobody'
    }


def calculate_scores() -> Scores:
    yes = 0
    no = 0
    for vote in current_vote['votes'].values():
        if vote.weight > 0:
            yes += vote.weight
        else:
            no -= vote.weight
    return Scores(round(yes - no, 2), round(yes, 2), round(no, 2))


async def init(bot: TelegramClient) -> None:
    @bot.on(events.NewMessage(pattern='#addsticker(?: (.+))?', chats=ALLOWED_CHATS))
    async def start_poll(event: Union[events.NewMessage.Event, Message]) -> None:
        global current_vote

        if not event.is_reply:
            return
        emoji = event.pattern_match.group(1) or '\u2728'
        try:
            _, sender_name = WEIGHTS[event.sender_id]
        except KeyError:
            return
        orig_evt: Message = await event.get_reply_message()
        # TODO add support for adding animated stickers to a separate pack
        if not orig_evt.photo or (not orig_evt.sticker or orig_evt.sticker.mime_type == 'application/x-tgsticker'):
            return

        if current_vote:
            await event.reply('There\'s already an ongoing sticker poll.')
            return

        filename = os.path.join(os.path.dirname(__file__), f'stickermanager.{int(time())}.dat')
        await orig_evt.download_media(filename)

        asyncio.ensure_future(event.delete(), loop=bot.loop)
        current_vote = {
            'chat': event.chat_id,
            'sender_id': event.sender_id,
            'sender_name': sender_name,
            'score': 0.0,
            'emoji': emoji,
            'votes': {},
            'filepath': filename,
            'animated': orig_evt.document and orig_evt.document.mime_type == 'application/x-tgsticker'
        }
        reply_evt: Message = await orig_evt.reply(
            POLL_TEMPLATE.safe_substitute(**get_template_data()),
            buttons=[Button.inline(UP, b'+'), Button.inline(DOWN, b'-')],
            parse_mode='html')
        current_vote['poll'] = reply_evt.id
        asyncio.ensure_future(reply_evt.pin(notify=True), loop=bot.loop)

    @bot.on(events.CallbackQuery(chats=ALLOWED_CHATS, data=lambda data: data in (b'+', b'-')))
    async def vote_poll(event: events.CallbackQuery.Event) -> None:
        global current_vote

        if not current_vote or current_vote['poll'] != event.message_id:
            await event.answer('That poll is closed.')
            return

        weight, displayname = WEIGHTS.get(event.sender_id, (DEFAULT_WEIGHT, None))
        if weight == 0:
            await event.answer('You don\'t have the permission to vote.')
            return
        if event.data == b'-':
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

        if scores.sum >= VOTES_REQUIRED:
            current_vote['result'] = RESULT_ADDED
            await bot.edit_message(current_vote['chat'], current_vote['poll'],
                                   POLL_FINISHED_TEMPLATE.safe_substitute(**get_template_data()),
                                   parse_mode='html')
            pack, document = await add_sticker_to_pack(bot)
            current_vote = None
            await event.answer(f'Successfully voted {weight},'
                               ' which made the sticker be accepted \U0001f389')
            await event.respond(file=document)
        else:
            await bot.edit_message(current_vote['chat'], current_vote['poll'],
                                   POLL_TEMPLATE.safe_substitute(**get_template_data()),
                                   buttons=[Button.inline(f'{UP} ({scores.yes})', b'+'),
                                            Button.inline(f'{DOWN} ({scores.no})', b'-')],
                                   parse_mode='html')
            await event.answer(f'Successfully voted {weight}')
