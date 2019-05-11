import os

from telethon.tl import functions, types
from telethon import events

# Example admins.txt:
#    1234 Lonami
#    5678 Friend of Lonami
#
# (We strip whitespace and split to get only the number)

with open(os.path.join(os.path.dirname(__file__), 'admins.txt')) as f:
    ADMINS = {
        int(line.strip().split()[0])
        for line in f
        if not line.isspace()
    }


async def init(bot):
    @bot.on(events.ChatAction)
    async def handler(event):
        if event.user_joined and event.user_id in ADMINS:
            await bot(functions.channels.EditAdminRequest(
                await event.get_input_chat(),
                await event.get_input_user(),
                types.ChatAdminRights(
                    # post_messages=True,
                    # add_admins=True,
                    invite_users=True,
                    change_info=True,
                    ban_users=True,
                    delete_messages=True,
                    pin_messages=True,
                    # invite_link=True,
                    # edit_messages=True
                )
            ))
