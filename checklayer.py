import asyncio
import logging
import urllib.parse
import json
import os
from typing import Optional, Mapping
from dataclasses import dataclass


class Info:
    def __init__(self, path):
        self._path = path
        self._info = None
        self._orig = None

    def __enter__(self):
        try:
            with open(self._path, 'rb') as fd:
                self._orig = json.load(fd)
        except OSError:
            self._orig = {
                'etag': None,
                'last-modified': None,
                'sha': None
            }
        self._info = dict(self._orig)
        return self._info

    def __exit__(self, *e):
        if self._info != self._orig:
            with open(self._path, 'w', encoding='utf-8') as fd:
                json.dump(self._info, fd)
        self._info = None
        self._orig = Noen


@dataclass
class Response:
    etag: str
    last_modified: str
    body: Optional[dict]


MSG_WHO = 10885151
REPO_OWNER = 'telegramdesktop'
REPO_NAME = 'tdesktop'
TL_PATH = 'Telegram/Resources/tl/api.tl'
CHECK_INTERVAL = 24 * 60 * 60
INFO = Info(os.path.join(os.path.dirname(__file__), 'latest-tl.json'))


async def https_get(url: str, headers: Mapping[str, str]) -> (Mapping[str, str], Optional[bytes]):
    url = urllib.parse.urlparse(url)
    rd, wr = await asyncio.open_connection(url.hostname, 443, ssl=True)
    try:
        wr.write('\r\n'.join((
            f'GET {url.path} HTTP/1.1',
            f'Host: {url.hostname}',
            f'User-Agent: Mozilla/5.0',
            f'Connection: close',
            *(f'{header}: {value}' for header, value in headers.items()),
            '',
            ''
        )).encode('ascii'))
        await wr.drain()

        headers = await rd.readuntil(b'\r\n\r\n')
        if headers[-4:] != b'\r\n\r\n':
            raise ConnectionError(f'Connection closed from {url.hostname}')
        headers = headers.decode('ascii').splitlines()

        status = headers.pop(0)
        try:
            status = int(status.split()[1])
        except ValueError:
            raise ValueError(f'Valid status code not found for {url.hostname}: {status}')
        if status in (304, 412):
            return headers, None
        elif status != 200:
            raise ValueError('Bad status code for {}: {}'.format(url.hostname, status))

        headers = {header.lower(): value for header, value in (line.split(': ', maxsplit=1) for line in headers if line)}
        if headers.get('transfer-encoding') == 'chunked':
            body = b''
            while True:
                length = int(await rd.readline(), 16)
                if length == 0:
                    break
                body += await rd.readexactly(length)
                await rd.readline()
        elif length := headers.get('content-length'):
            body = await rd.readexactly(length)
        else:
            raise ValueError(f'Don\'t know how to read response from {url.hostname}')

        return headers, body
    finally:
        wr.close()
        await wr.wait_closed()


async def gh_get_repository_content(
    owner: str,
    repo: str,
    path: str,
    *,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
):
    """
    https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#get-repository-content
    """
    headers = {}
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    headers, body = await https_get(f'https://api.github.com/repos/{owner}/{repo}/contents/{path}', headers)
    if body:
        body = json.loads(body)
    return Response(
        etag=headers['etag'],
        last_modified=['last-modified'],
        body=body,
    )


async def init(bot):
    async def check_sha():
        while bot.is_connected():
            try:
                resp = await gh_get_repository_content(REPO_OWNER, REPO_NAME, TL_PATH)
            except Exception as e:
                logging.warning('Failed to fetch api.tl: %s', e)
                resp = None

            with INFO as info:
                if resp is None:
                    if info['sha'] is None:
                        await bot.send_message(MSG_WHO, f'Failed to initialize SHA for `api.tl`')
                else:
                    if info['sha'] is None:
                        await bot.send_message(MSG_WHO, f'Initialized SHA for `api.tl`')
                    elif resp.body['sha'] != info['sha']:
                        await bot.send_message(MSG_WHO, f'New SHA for `api.tl` (likely [new layer]({resp.body["html_url"]}))')

                    info['etag'] = resp.etag
                    info['last-modified'] = resp.last_modified
                    info['sha'] = resp.body['sha']

            try:
                await asyncio.wait_for(
                    bot.disconnected,
                    timeout=CHECK_INTERVAL
                )
            except asyncio.TimeoutError:
                pass

    # TODO This task is not properly terminated on disconnect
    asyncio.create_task(check_sha())


async def main():
    """
    For testing purposes.
    """
    logging.basicConfig(level=logging.DEBUG)
    print(await gh_get_repository_content(REPO_OWNER, REPO_NAME, TL_PATH))


if __name__ == '__main__':
    asyncio.run(main())
