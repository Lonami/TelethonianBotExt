import asyncio
import importlib
import os
import warnings
import logging
import time


def init(bot):
    bot.loop.run_until_complete(start_plugins(bot, [
        # Dynamically import
        importlib.import_module(f'.', f'{__name__}.{file[:-3]}')

        # All the files in the current directory
        for file in os.listdir(os.path.dirname(__file__))

        # If they start with a letter and are Python files
        if file[0].isalpha() and file.endswith('.py')
    ]))


async def _init_plugin(bot, plugin):
    p_init = getattr(plugin, 'init', None)
    if callable(p_init):
        try:
            logging.warning(f'Loading plugin {plugin.__name__}…')
            start = time.time()
            await p_init(bot)
            took = time.time() - start
            logging.warning(f'Loaded plugin {plugin.__name__} (took {took:.2f}s)')
        except Exception:
            logging.exception(f'Failed to load plugin {plugin}')


async def start_plugins(bot, plugins):
    await asyncio.gather(*(_init_plugin(bot, plugin) for plugin in plugins))
