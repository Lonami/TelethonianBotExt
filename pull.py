import html
import logging
import os
import subprocess
import time

from telethon import events

MAGIC_FILE = os.path.join(os.path.dirname(__file__), 'self-update.lock')


async def init(bot):
    @bot.on(events.NewMessage(pattern=r'#pull(\s+force)?', from_users=10885151))
    async def handler(event):
        await event.delete()
        m = await event.respond('Checking for plugin updates…')

        if 'force' in event.raw_text:
            await m.edit('Running git reset…')
            result = subprocess.run(['git', '-C', os.path.dirname(__file__), 'reset --hard HEAD'])
            await m.edit(f'git reset returned: {result.returncode}')

        result = subprocess.run(
            ['git', '-C', os.path.dirname(__file__), 'pull'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if result.returncode != 0:
            await m.edit(
                'Cannot update:\n'
                '<pre>{}</pre>\n\n'
                'Run again with "force" to reset first.'
                .format(html.escape(result.stderr.decode('utf-8'))),
                parse_mode='html'
            )
            return

        if result.stdout == b'Already up to date.\n':
            await m.edit('Nothing to update.')
            return

        try:
            with open(MAGIC_FILE, 'w') as fd:
                fd.write('{}\n{}\n'.format(m.chat_id, m.id))

            await m.edit('Plugins updated. Restarting…')
        except OSError:
            await m.edit('Plugins updated. Will not notify after restart. Restarting…')

        logging.warning('Disconnecting bot to restart plugins')
        try:
            start = time.time()
            await bot.disconnect()
            took = time.time() - start
            logging.warning(f'Restarting via disconnect success (took {took:.2f}s)')
        except Exception:
            logging.exception('Error on disconnect, this is a bug')

    try:
        with open(MAGIC_FILE) as fd:
            chat_id, msg_id = map(int, fd)
            await bot.edit_message(chat_id, msg_id, 'Plugins updated.')

        os.unlink(MAGIC_FILE)
    except OSError:
        pass
