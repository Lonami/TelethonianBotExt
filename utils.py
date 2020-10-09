from telethon import utils


def get_display(entity):
    """
    Returns the display name of entity, safe to use in HTML strings.
    """
    if not entity:
        return "A user"

    return (
        utils.get_display_name(entity).strip()
        or f"{entity.__class__.__name__} {entity.id}"
    )
