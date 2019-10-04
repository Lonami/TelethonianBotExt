import os
import time
import json
import asyncio
from string import Template
from html import escape as escape_html
from typing import Union, NamedTuple, Callable, Optional

from telethon.tl.custom import Message, Button
from telethon.tl.types import InputStickerSetID, InputStickerSetItem
from telethon.tl.types.messages import StickerSet
from telethon.tl.functions.stickers import CreateStickerSetRequest, AddStickerToSetRequest
from telethon import events, TelegramClient

POLL_TEMPLATE = Template(""""
<a href="tg://user?id=$sender_id">$sender_name</a> has suggested this sticker
be added to the group's sticker pack with the emoji $emoji.

<strong>Current result: $score</strong>
For: $yes
Against: $no
""".strip())

POLL_FINISHED_TEMPLATE = Template("""
<strong>This sticker poll is finished with a final score of $score. $result</strong>

<a href="tg://user?id=$sender_id">$sender_name</a> had suggested this sticker
be added to the group's sticker pack with the emoji $emoji.

For: $yes
Against: $no
""".strip())

VOTE_TEMPLATE = Template("<a href='tg://user?id=$uid'>$displayname</a>")

RESULT_ADDED = "The sticker has been added to the pack."
RESULT_REJECTED = "The sticker was rejected from the pack."

with open(os.path.join(os.path.dirname(__file__), "stickermanager.tsv")) as f:
    WEIGHTS = {
        int(uid): (0 if weight == "-" else float(weight), name)
        for uid, weight, name
        in (line.strip().split("\t", 2)
            for line in f
            if len(line) > 0 and not line[0] == "#" and not line.isspace())
    }

    VOTES_REQUIRED = WEIGHTS.pop("votes required")[0]
    DEFAULT_WEIGHT = WEIGHTS.pop("default weight")[0]
    STICKER_PACK_TITLE = WEIGHTS.pop("sticker title")[1]
    STICKER_PACK_SHORT_NAME = WEIGHTS.pop("sticker short")[1]
    ADMIN_USER_ID = WEIGHTS.pop("sticker owner")[0]
    ALLOWED_CHATS = [int(gid.strip())
                     for gid in WEIGHTS.pop("allowed chats")[1].split(",")
                     if not gid.isspace()]


async def create_sticker_pack(bot: TelegramClient) -> InputStickerSetID:
    try:
        with open(os.path.join(os.path.dirname(__file__), "stickermanager.json")) as file:
            sp_data = json.load(file)
            sp = InputStickerSetID(id=sp_data["id"], access_hash=sp_data["access_hash"])
    except (FileNotFoundError, KeyError):
        stickerset: StickerSet = await bot(CreateStickerSetRequest(
            user_id=ADMIN_USER_ID,
            title=STICKER_PACK_TITLE,
            short_name=STICKER_PACK_SHORT_NAME,
            stickers=[]
        ))
        sp = InputStickerSetID(id=stickerset.set.id, access_hash=stickerset.set.access_hash)
        with open(os.path.join(os.path.dirname(__file__), "stickermanager.json")) as file:
            json.dump({
                "id": sp.id,
                "access_hash": sp.access_hash
            }, file)
    return sp


UP = "\U0001f53c"
DOWN = "\U0001f53d"

VoteData = NamedTuple("VoteData", weight=int, displayname=str)
Scores = NamedTuple("Scores", sum=int, yes=int, no=int)

current_vote = {}
stickerpack: Optional[InputStickerSetID] = None


async def add_sticker_to_pack(bot: TelegramClient) -> None:
    file = await bot.upload_file(current_vote["_filename"])
    document = file  # TODO
    item = InputStickerSetItem(document=document, emoji=current_vote["emoji"])
    await bot(AddStickerToSetRequest(stickerset=stickerpack, sticker=item))


def get_template_data() -> dict:
    def format_votes(cond: Callable[[int], bool]) -> str:
        return ", ".join(VOTE_TEMPLATE.substitute(uid=uid, displayname=displayname, weight=weight)
                         for uid, (weight, displayname) in current_vote["votes"].items()
                         if cond(weight))

    return {
        **current_vote,
        "yes": format_votes(lambda weight: weight > 0) or "nobody",
        "no": format_votes(lambda weight: weight < 0) or "nobody"
    }


def calculate_scores() -> Scores:
    yes = 0
    no = 0
    for vote in current_vote.values():
        if vote.weight > 0:
            yes += vote.weight
        else:
            no -= vote.weight
    return Scores(round(yes - no, 2), round(yes, 2), round(no, 2))


async def init(bot: TelegramClient) -> None:
    global stickerpack
    stickerpack = await create_sticker_pack(bot)

    @bot.on(events.NewMessage(pattern="#addsticker(?: (.+))?", chats=ALLOWED_CHATS))
    async def start_poll(event: Union[events.NewMessage.Event, Message]) -> None:
        global current_vote

        if not event.is_reply:
            return
        emoji = event.pattern_match.group(1) or "\u2728"
        try:
            sender_name, _ = WEIGHTS[event.sender_id]
        except KeyError:
            return
        orig_evt: Message = await event.get_reply_message()
        if not orig_evt.sticker:
            return

        if current_vote:
            await event.reply("There's already an ongoing sticker poll.")
            return

        filename = os.path.join(os.path.dirname(__file__), f"stickermanager.{int(time.time())}.dat")
        await orig_evt.download_media(filename)
        asyncio.ensure_future(event.delete(), loop=bot.loop)
        current_vote = {
            "chat": event.chat_id,
            "sender_id": event.sender_id,
            "sender_name": sender_name,
            "emoji": emoji,
            "votes": {},
            "_filename": filename,
        }
        reply_evt: Message = await orig_evt.reply(
            POLL_TEMPLATE.safe_substitute(**get_template_data()),
            buttons=[Button.inline(UP, b"+"), Button.inline(DOWN, b"-")])
        current_vote["poll"] = reply_evt.id
        await reply_evt.pin(notify=True)

    @bot.on(events.CallbackQuery(chats=ALLOWED_CHATS, data=lambda data: data in (b"+", b"-")))
    async def vote_poll(event: events.CallbackQuery.Event) -> None:
        global current_vote

        if current_vote["poll"] != event.message_id:
            await event.answer("That poll is closed.")
            return

        weight, displayname = WEIGHTS.get(event.sender_id, (DEFAULT_WEIGHT, None))
        if weight == 0:
            await event.answer("You don't have the permission to vote.")
            return
        if event.data == "-":
            weight = -weight

        displayname = displayname or escape_html((await event.get_sender()).first_name)
        current_vote[event.sender_id] = VoteData(weight=weight, displayname=displayname)

        scores = calculate_scores()
        current_vote["score"] = scores.sum

        if scores.sum > VOTES_REQUIRED:
            current_vote["result"] = RESULT_ADDED
            await bot.edit_message(current_vote["chat"], current_vote["poll"],
                                   POLL_FINISHED_TEMPLATE.safe_substitute(**get_template_data()))
            await add_sticker_to_pack(bot)
            current_vote = None
        else:
            await bot.edit_message(current_vote["chat"], current_vote["poll"],
                                   POLL_TEMPLATE.safe_substitute(**get_template_data()),
                                   buttons=[Button.inline(f"{UP} ({scores.yes})", b"+"),
                                            Button.inline(f"{DOWN} ({scores.no})", b"-")])
