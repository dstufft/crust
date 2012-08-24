import datetime
import re

from . import six
from .exceptions import FieldError


DATETIME_REGEX = re.compile('^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})(T|\s+)(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}).*?$')


class Field(object):
    """
    Base class for all field types
    """

    # This tracks each time a Field instance is created. Used to retain order.
    creation_counter = 0

    def __init__(self, name=None, serialize=True, *args, **kwargs):
        super(Field, self).__init__(*args, **kwargs)

        self.name = name
        self.serialize = serialize

        self.creation_counter = Field.creation_counter
        Field.creation_counter += 1

    def hydrate(self, value):
        return value

    def dehydrate(self, value):
        return value


class DateTimeField(Field):

    def hydrate(self, value):
        if isinstance(value, six.string_types):
            match = DATETIME_REGEX.search(value)

            if match:
                data = match.groupdict()
                return datetime.datetime(int(data["year"]), int(data["month"]), int(data["day"]), int(data["hour"]), int(data["minute"]), int(data["second"]))
            else:
                raise FieldError("Datetime provided to '%s' field doesn't appear to be a valid datetime string: '%s'" % (self.name, value))

        return value

    def dehydrate(self, value):
        if isinstance(value, datetime.datetime):
            return value.isoformat()

        return value
