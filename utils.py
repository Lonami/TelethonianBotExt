import unidecode
from telethon import utils
import re


def get_display(entity):
    """
    Returns the display name of entity, safe to use in HTML strings.
    """
    if not entity:
        return 'A user'

    return re.sub(
        r'[^ -~]+',
        ' ',
        unidecode.unidecode(utils.get_display_name(entity))
    ).strip() or f'{entity.__class__.__name__} {entity.id}'
