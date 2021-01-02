import os

from telethon import events

# Example admins.txt:
#    1234 Lonami
#    5678 Friend of Lonami
#
# (We strip whitespace and split to get only the number)

with open(os.path.join(os.path.dirname(__file__), 'admins.txt'), encoding="utf-8") as f:
    ADMINS = {
        int(line.strip().split()[0]): line.strip().split()[1]
        for line in f
        if not line.isspace()
    }


async def init(bot):
    @bot.on(events.ChatAction)
    async def handler(event):
        if event.user_joined and event.user_id in ADMINS:
            await bot.edit_admin(
                await event.get_input_chat(),
                await event.get_input_user(),
                change_info=False,
                # post_messages=True,
                # edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=False,
                manage_call=True,
            )
