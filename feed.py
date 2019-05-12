import asyncio
import html
import sys
import typing
import xml.dom.minidom

REPOSITORY = b'LonamiWebs/Telethon'
SEND_TO = 'TelethonUpdates'
UPDATE_INTERVAL = 5 * 60
MAX_COMMITS_PER_MESSAGE = 3  # >33 breaks (>100 entities in a single message)


# Using XML with Python's builtin modules is *terrible*!
class XML:
    def __init__(self, elem):
        self.elem = elem

    @classmethod
    def from_string(cls, string) -> 'XML':
        return cls(xml.dom.minidom.parseString(string))

    def __getitem__(self, item) -> str:
        return self.elem.attributes[item].value

    def tag(self, name) -> 'XML':
        return next(self.tags(name), None)

    def tags(self, name) -> typing.Generator['XML', None, None]:
        return (XML(elem) for elem in self.elem.getElementsByTagName(name))

    @property
    def text(self) -> str:
        return ''.join(
            node.data
            for node in self.elem.childNodes
            if node.nodeType == node.TEXT_NODE
        ).strip()


async def fetch_feed() -> XML:
    # We could use `aiohttp` but this is more fun
    rd, wr = await asyncio.open_connection('github.com', 443, ssl=True)

    # Send HTTP request
    wr.write(
        b'GET /' + REPOSITORY + b'/commits/master.atom HTTP/1.1\r\n'
        b'Host: github.com\r\n'
        b'\r\n'
    )
    await wr.drain()

    # Get response headers
    headers = await rd.readuntil(b'\r\n\r\n')
    if headers[-4:] != b'\r\n\r\n':
        raise ConnectionError('Connection closed')

    # Ensure it's OK
    index = headers.index(b'Status:') + 8
    status = headers[index:headers.index(b'\r', index)]
    if headers[index:index + 6] != b'200 OK':
        raise ValueError('Bad status code: {}'.format(status))

    # GitHub uses "Transfer-Encoding: chunked", so no Content-Length
    result = b''
    while True:
        length = int(await rd.readline(), 16)
        if length == 0:
            break

        result += await rd.readexactly(length)
        await rd.readline()

    # Properly close the writer
    wr.close()
    if sys.version_info >= (3, 7):
        await wr.wait_closed()

    return XML.from_string(result.decode('utf-8'))


def get_commit_hash(entry):
    return entry.tag('link')['href'].rsplit('/', maxsplit=1)[-1]


async def init(bot):
    last_commit = get_commit_hash((await fetch_feed()).tag('entry'))

    async def check_feed():
        nonlocal last_commit
        while bot.is_connected():
            feed = await fetch_feed()
            new = []
            for entry in feed.tags('entry'):
                commit = get_commit_hash(entry)
                if commit == last_commit:
                    break

                link = entry.tag('link')['href']
                title = html.escape(entry.tag('title').text)

                author = entry.tag('author')
                name = html.escape(author.tag('name').text)
                uri = author.tag('uri').text

                new.append(f'<b>{title}</b> (<a href="{link}">{commit[:7]}</a> by <a href="{uri}">{name}</a>)')

            new = new[::-1]
            while new:
                await bot.send_message(
                    SEND_TO,
                    '\n'.join(new[:MAX_COMMITS_PER_MESSAGE]),
                    parse_mode='html',
                    link_preview=False
                )
                new = new[MAX_COMMITS_PER_MESSAGE:]

            # Update the last commit to not re-send it
            last_commit = get_commit_hash(feed.tag('entry'))

            # Wait until we disconnect or a timeout occurs
            try:
                await asyncio.wait_for(bot.disconnected, timeout=UPDATE_INTERVAL, loop=bot.loop)
            except asyncio.TimeoutError:
                pass

    # TODO This task is not properly terminated on disconnect
    bot.loop.create_task(check_feed())
