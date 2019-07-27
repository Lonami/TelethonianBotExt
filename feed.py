import asyncio
import html
import itertools
import logging
import sys
import typing
import xml.dom.minidom

UPDATE_INTERVAL = 5 * 60


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


class FeedChecker:
    def __init__(self, host, path):
        self._host = host
        self._request = (
            f'GET {path} HTTP/1.1\r\n'
            f'Host: {host}\r\n'
            f'\r\n'
        ).encode()
        self._seen_ids = set()

    async def _fetch(self):
        # We could use `aiohttp` but this is more fun
        rd, wr = await asyncio.open_connection(self._host, 443, ssl=True)

        # Send HTTP request
        wr.write(self._request)
        await wr.drain()

        # Get response headers
        headers = await rd.readuntil(b'\r\n\r\n')
        if headers[-4:] != b'\r\n\r\n':
            raise ConnectionError('Connection closed')

        # Ensure it's OK
        if headers.startswith(b'HTTP/1.1 200 OK'):
            pass  # StackOverflow puts OK in the first line
        else:
            # GitHub puts OK in 'Status:'
            try:
                index = headers.index(b'Status:') + 8
                status = headers[index:headers.index(b'\r', index)]
            except ValueError:
                logging.warning('Checking %s feed failed: %s', self._host, headers.decode())
                raise

            if headers[index:index + 6] != b'200 OK':
                raise ValueError('Bad status code: {}'.format(status))

        # StackOverflow has 'Content-Length:'
        index = headers.find(b'Content-Length:')
        if index != -1:
            index += 16
            length = int(headers[index:headers.index(b'\r', index)])
            result = await rd.readexactly(length)
        else:
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

    async def poll(self):
        feed = await self._fetch()

        new = []
        for entry in feed.tags('entry'):
            entry_id = entry.tag('id').text
            if entry_id not in self._seen_ids:
                self._seen_ids.add(entry_id)
                new.append(entry)

        return new


def fmt_github(entry):
    link = entry.tag('link')['href']
    commit = link.rsplit('/', maxsplit=1)[-1]
    title = html.escape(entry.tag('title').text)

    author = entry.tag('author')
    name = html.escape(author.tag('name').text)
    uri = author.tag('uri').text

    return f'<b>{title}</b> (<a href="{link}">{commit[:7]}</a> by <a href="{uri}">{name}</a>)'


def fmt_stackoverflow(entry):
    link = entry.tag('id').text
    title = html.escape(entry.tag('title').text)
    return (
        f'<i>New StackOverflow question</i>\n'
        f'<b>{title}</b>\n'
        f'\n'
        f'{link}'
    )


async def init(bot):
    github_feed = FeedChecker(
        host='github.com',
        path='/LonamiWebs/Telethon/commits/master.atom'
    )
    stackoverflow_feed = FeedChecker(
        host='stackoverflow.com',
        path='/feeds/tag?tagnames=telethon&sort=newest'
    )

    # Skip the ones currently in the feed, we already know them
    await github_feed.poll()
    await stackoverflow_feed.poll()

    async def check_feed():
        while bot.is_connected():
            # Wait until we disconnect or a timeout occurs
            try:
                await asyncio.wait_for(
                    bot.disconnected,
                    timeout=UPDATE_INTERVAL,
                    loop=bot.loop
                )
            except asyncio.TimeoutError:
                pass

            # GitHub feed
            try:
                entries = list(await github_feed.poll())[::-1]
            except Exception as e:
                logging.warning('Failed to fetch GitHub RSS feed %s', e)
            else:
                # Each message has 3 entities (bold, link, link)
                # A message can have up to 100 entities.
                # The limit of commits per message is 33.
                commits_per_msg = 33
                while entries:
                    await bot.send_message(
                        'TelethonUpdates',
                        '\n'.join(fmt_github(e) for e in itertools.islice(entries, commits_per_msg)),
                        parse_mode='html',
                        link_preview=False
                    )
                    entries = entries[commits_per_msg:]

            # StackOverflow feed
            try:
                entries = list(await stackoverflow_feed.poll())[::-1]
            except Exception as e:
                logging.warning('Failed to fetch StackOverflow RSS feed %s', e)
            else:
                for entry in entries:
                    await bot.send_message(
                        'TelethonChat',
                        fmt_stackoverflow(entry),
                        parse_mode='html',
                        link_preview=False
                    )

    # TODO This task is not properly terminated on disconnect
    bot.loop.create_task(check_feed())
