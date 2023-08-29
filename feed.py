import asyncio
import html
import itertools
import logging
import sys
import typing
import xml.dom.minidom
from dataclasses import dataclass
from telethon import events

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


def _header(headers, name):
    index = headers.find(name)
    if index != -1:
        index += len(name) + 1
        return headers[index:headers.index(b'\r', index)].decode()


class FeedChecker:
    def __init__(self, host, path):
        self._host = host
        self._path = path
        self._etag = None
        self._last_modified = None
        self._seen_ids = set()

    def _request(self, *, use_cache):
        req = [f'GET {self._path} HTTP/1.1',
               f'Host: {self._host}',
               f'User-Agent: Mozilla/5.0',  # StackOverflow returns 403 otherwise :(
               f'Connection: close',]
        if use_cache and self._etag:
            req.append(f'If-None-Match: {self._etag}')
        if use_cache and self._last_modified:
            req.append(f'If-Modified-Since: {self._last_modified}')

        req.extend(('', ''))
        return '\r\n'.join(req).encode()

    async def _fetch(self, *, force):
        # We could use `aiohttp` but this is more fun
        rd, wr = await asyncio.open_connection(self._host, 443, ssl=True)

        # Send HTTP request
        req = self._request(use_cache=not force)
        logging.debug('Sending to %s: %s', self._host, req)
        wr.write(req)
        await wr.drain()

        # Get response headers
        headers = await rd.readuntil(b'\r\n\r\n')
        if headers[-4:] != b'\r\n\r\n':
            raise ConnectionError('Connection closed')

        logging.debug('Answer from %s: %s', self._host, headers)

        # Ensure it's OK
        try:
            status = int(headers[9:12])  # Skip 'HTTP/1.1 '
        except ValueError:
            logging.warning('Checking %s feed failed: %s', self._host, headers.decode())
            raise ValueError('Valid status code not found')

        if status in (304, 412):
            logging.info('Feed %s has not changed: %d', self._host, status)
            return

        if status != 200:
            raise ValueError('Bad status code for {}: {}'.format(self._host, status))

        # StackOverflow has 'Content-Length:'
        content_len = _header(headers, b'Content-Length:')
        if content_len:
            length = int(content_len)
            logging.debug('Reading exactly %d', length)
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

        logging.debug('Closing writer')

        # Properly close the writer
        wr.close()
        if sys.version_info >= (3, 7):
            await wr.wait_closed()

        xml = XML.from_string(result.decode('utf-8'))

        # Find ETag (GitHub) and last modified (StackOverflow) on success
        self._etag = _header(headers, b'etag:')
        self._last_modified = _header(headers, b'last-modified:')

        return xml

    def set_stale(self, ids):
        self._etag = None
        self._last_modified = None
        self._seen_ids -= ids

    async def poll(self, *, force=False):
        feed = await self._fetch(force=force)

        new = []
        if feed is None:  # not modified
            return new

        for entry in feed.tags('entry'):
            entry_id = entry.tag('id').text
            if force or entry_id not in self._seen_ids:
                self._seen_ids.add(entry_id)
                new.append(entry)

        return new


@dataclass
class GitHubEntry:
    id: str
    title: str
    link: str
    commit: str
    uri: str
    name: str


def parse_github(entry):
    id = entry.tag('id').text

    link = entry.tag('link')['href']
    commit = link.rsplit('/', maxsplit=1)[-1]
    title = html.escape(entry.tag('title').text)

    author = entry.tag('author')
    name = html.escape(author.tag('name').text)
    uri = author.tag('uri').text

    return GitHubEntry(id, title, link, commit, uri, name)


def fmt_github(entry):
    parsed = parse_github(entry)

    return f'<b>{parsed.title}</b> (<a href="{parsed.link}">{parsed.commit[:7]}</a> by <a href="{parsed.uri}">{parsed.name}</a>)'


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
        path='/LonamiWebs/Telethon/commits/v1.atom'
    )
    stackoverflow_feed = FeedChecker(
        host='stackoverflow.com',
        path='/feeds/tag?tagnames=telethon&sort=newest'
    )

    # Skip the ones currently in the feed, we already know them
    try:
        await github_feed.poll()
        await stackoverflow_feed.poll()
    except Exception as e:
        logging.error('Failed to initialize feeds %s', e)
        await bot.send_message(
            10885151,
            f'Feed could not be initialized ({type(e).__name__}): <pre>{html.escape(str(e))}</pre>'
        )
        raise

    fetch_now = asyncio.Event()

    @bot.on(events.NewMessage(pattern='#feed ([a-fA-F\d]+)', from_users=10885151))
    async def handler(event):
        last_hash = event.pattern_match.group(1)
        m = await event.respond(f'Forcibly fetching feed until {last_hash}...')
        ids = set()
        commits = []
        all_entries = await github_feed.poll(force=True)
        for entry in map(parse_github, all_entries):
            if entry.commit.startswith(last_hash):
                break
            ids.add(entry.id)
            commits.append(entry.commit[:7])

        github_feed.set_stale(ids)
        await m.edit(f'Marked {len(commits)} commits as stale: {", ".join(commits)}')
        fetch_now.set()

    async def check_feed():
        while bot.is_connected():
            # Wait until we disconnect or a timeout occurs
            fetch_now_task = asyncio.create_task(fetch_now.wait())
            try:
                _, pending = await asyncio.wait_for(
                    asyncio.wait((
                        bot.disconnected,
                        fetch_now_task
                    ), return_when=asyncio.FIRST_COMPLETED),
                    timeout=UPDATE_INTERVAL
                )
                for task in pending:
                    task.cancel()
                    await task
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

    return asyncio.create_task(check_feed())


async def main():
    """
    For testing purposes.
    """
    logging.basicConfig(level=logging.DEBUG)
    github_feed = FeedChecker(
        host='github.com',
        path='/LonamiWebs/Telethon/commits/v1.atom'
    )
    stackoverflow_feed = FeedChecker(
        host='stackoverflow.com',
        path='/feeds/tag?tagnames=telethon&sort=newest'
    )

    # Skip the ones currently in the feed, we already know them
    logging.info('Checking GitHub')
    gh_entries = await github_feed.poll()
    logging.info('Checking StackOverflow')
    so_entries = await stackoverflow_feed.poll()

    # Remove one entry to pretend we didn't have it
    github_feed._seen_ids.remove(gh_entries[0].tag('id').text)
    github_feed._etag = github_feed._last_modified = None
    stackoverflow_feed._seen_ids.remove(so_entries[0].tag('id').text)
    stackoverflow_feed._etag = stackoverflow_feed._last_modified = None
    logging.info('Sleeping...')
    await asyncio.sleep(10)

    logging.info('Checking GitHub')
    for entry in await github_feed.poll():
        logging.info('GitHub entry: %s', fmt_github(entry))

    logging.info('Checking StackOverflow')
    for entry in await stackoverflow_feed.poll():
        logging.info('StackOverflow entry: %s', fmt_stackoverflow(entry))


if __name__ == '__main__':
    asyncio.run(main())
