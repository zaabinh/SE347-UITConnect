from app.core.exceptions import ApplicationError


def require_found(entity, name):
    if entity is None:
        raise ApplicationError(404, f'{name} not found.')
    return entity


def require_unreported(duplicate):
    if duplicate is not None:
        raise ApplicationError(409, 'You already reported this comment.')
