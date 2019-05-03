import asyncio
from . import autoadmin, randomkick, sed,faq


# TODO Autodetect modules and init them all
# TODO Warn about errors if any fails to init
def init(bot):
    asyncio.get_event_loop().run_until_complete(asyncio.wait([
        autoadmin.init(bot),
        randomkick.init(bot),
        sed.init(bot),
        faq.init(bot)
    ]))
