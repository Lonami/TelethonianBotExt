import asyncio
import importlib
import os
import warnings
import logging
import time
import inspect


async def init(bot):
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.ERROR)

    plugins = [
        # Dynamically import
        importlib.import_module(f'.', f'{__name__}.{file[:-3]}')

        # All the files in the current directory
        for file in os.listdir(os.path.dirname(__file__))

        # If they start with a letter and are Python files
        if file[0].isalpha() and file.endswith('.py')
    ]

    # Keep a mapping of module name to module for easy access inside the plugins
    modules = {m.__name__: m for m in plugins}

    # All kwargs provided to get_init_args are those that plugins may access
    to_init = (get_init_args(plugin, bot=bot, modules=modules) for plugin in plugins)

    # Plugins may not have a valid init so those need to be filtered out
    await asyncio.gather(*(filter(None, to_init)))


def get_init_args(plugin, **kwargs):
    p_init = getattr(plugin, 'init', None)
    if not callable(p_init):
        return

    result_kwargs = {}
    sig = inspect.signature(p_init)
    for param in sig.parameters:
        if param.name in kwargs:
            result_kwargs[param.name] = kwargs[param.name]
        else:
            logging.error('Plugin %s has unknown init parameter %s', plugin.__name__, param.__name__)
            return

    return plugin, result_kwargs


async def _init_plugin(plugin, kwargs):
    try:
        logging.warning(f'Loading plugin {plugin.__name__}…')
        start = time.time()
        await plugin.init(**kwargs)
        took = time.time() - start
        logging.warning(f'Loaded plugin {plugin.__name__} (took {took:.2f}s)')
    except Exception:
        logging.exception(f'Failed to load plugin {plugin}')


async def start_plugins(bot, plugins):
    await asyncio.gather(*(_init_plugin(bot, plugin) for plugin in plugins))
