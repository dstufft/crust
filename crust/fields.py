import datetime
import importlib
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


class RelatedField(Field):

    def __init__(self, resource, lazy=True, *args, **kwargs):
        super(RelatedField, self).__init__(*args, **kwargs)

        self.lazy = lazy
        self._resource = resource

    @property
    def resource_class(self):
        if isinstance(self._resource, six.string_types):
            modname, class_name = self._resource.rsplit(".", 1)
            mod = importlib.import_module(modname)
            self._resource = getattr(mod, class_name)

        return self._resource


class ToOneField(RelatedField):

    def hydrate(self, value):
        if value is None:
            return value

        if isinstance(value, self.resource_class):
            return value

        if self.lazy:
            from .resources import LazyResource
            return LazyResource(self.resource_class, value)
        else:
            r = self.resource_class._meta.api.http_resource("GET", value)
            data = self.resource_class._meta.api.resource_deserialize(r.text)
            return self.resource_class(**data)

    def dehydrate(self, value):
        from .resources import LazyResource

        if value is None:
            return value

        if isinstance(value, LazyResource):
            return value._lazy_state["url"]

        if value.resource_uri is None:
            raise FieldError("Cannot dehydrate a resource without a resource_uri")

        return value.resource_uri


class ToManyField(RelatedField):

    def hydrate(self, value):
        if value is None:
            return value

        if self.lazy:
            from .resources import LazyResource
            return [LazyResource(self.resource_class, url) for url in value]
        else:
            hydrated = []

            for url in value:
                r = self.resource_class._meta.api.http_resource("GET", url)
                data = self.resource_class._meta.api.resource_deserialize(r.text)
                hydrated.append(self.resource_class(**data))

            return hydrated

    def dehydrate(self, value):
        from .resources import LazyResource

        if value is None:
            return value

        dehydrated = []

        for item in value:
            if isinstance(item, LazyResource):
                dehydrated.append(item._lazy_state["url"])
            else:
                if item.resource_uri is None:
                    raise FieldError("Cannot dehydrate a resource without a resource_uri")
                dehydrated.append(item.resource_uri)

        return dehydrated
