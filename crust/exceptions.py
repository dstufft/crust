class ResponseError(ValueError):
    """
    The API Response was unexpected.
    """


class ObjectDoesNotExist(Exception):
    """
    The requested object does not exist
    """


class MultipleObjectsReturned(Exception):
    """
    The query returned multiple objects when only one was expected.
    """
