from __future__ import annotations


def ensure_list(e) -> list:
    """
    Ensure that the given item is a list
    :param e: Object to check
    :return: e as a list if e is a list, tuple or set or a new list with e as single element
    """
    if e is None:
        return []
    elif isinstance(e, (list, tuple, set)):
        return list(e)
    else:
        return [e]
