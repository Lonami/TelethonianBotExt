from telethon.tl import functions, types
from telethon import events


# TODO Load from file
try:
    ADMINS = {admin_id for admin_id in open('ADMIN.txt', 'r').readlines()}
except FileNotFoundError:
    ADMINS = {}
    open('ADMIN.txt', 'w').close()


async def init(bot):
    @bot.on(events.ChatAction)
    async def handler(event):
        if event.user_joined and event.user_id in ADMINS:
            await bot(functions.channels.EditAdminRequest(
                await event.get_input_chat(),
                await event.get_input_user(),
                types.ChatAdminRights(
                    #post_messages=True,
                    #add_admins=True,
                    invite_users=True,
                    change_info=True,
                    ban_users=True,
                    delete_messages=True,
                    pin_messages=True,
                    #invite_link=True,
                    #edit_messages=True
                )
            ))
