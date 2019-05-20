import asyncio
import io
import sys

from telethon import functions

URI = b'telegramdesktop/tdesktop/dev/Telegram/Resources/scheme.tl'
SEND_TO = 'TelethonOffTopic'
UPDATE_INTERVAL = 24 * 60 * 60
MESSAGE = '@lonami, [a new layer is available](https://github.com' \
          '/telegramdesktop/tdesktop/blob/dev/Telegram/Resources/scheme.tl)'


async def fetch():
    # We could use `aiohttp` but this is more fun
    rd, wr = await asyncio.open_connection('raw.githubusercontent.com', 443, ssl=True)

    # Send HTTP request
    wr.write(
        b'GET /' + URI + b' HTTP/1.1\r\n'
        b'Host: raw.githubusercontent.com\r\n'
        b'\r\n'
    )
    await wr.drain()

    # Get response headers
    headers = await rd.readuntil(b'\r\n\r\n')
    if headers[-4:] != b'\r\n\r\n':
        raise ConnectionError('Connection closed')

    # Ensure it's OK
    if not headers.startswith(b'HTTP/1.1 200 OK'):
        raise ValueError('Bad status code: {}'.format(headers[:headers.index(b'\r\n')]))

    # Figure out Content-Length to read
    index = headers.index(b'Content-Length:') + 16
    length = int(headers[index:headers.index(b'\r', index)])
    result = await rd.readexactly(length)

    # Properly close the writer
    wr.close()
    if sys.version_info >= (3, 7):
        await wr.wait_closed()

    return result


async def init(bot):
    last_hash = hash(await fetch())

    async def check_feed():
        nonlocal last_hash
        while bot.is_connected():
            contents = await fetch()
            if hash(contents) != last_hash:
                file = io.BytesIO(contents)
                file.name = 'scheme.txt'
                message = await bot.send_file(SEND_TO, file, caption=MESSAGE)
                await bot(functions.messages.UpdatePinnedMessageRequest(SEND_TO, message.id, silent=True))
                last_hash = hash(contents)

            # Wait until we disconnect or a timeout occurs
            try:
                await asyncio.wait_for(
                    bot.disconnected,
                    timeout=UPDATE_INTERVAL,
                    loop=bot.loop
                )
            except asyncio.TimeoutError:
                pass

    # TODO This task is not properly terminated on disconnect
    bot.loop.create_task(check_feed())
