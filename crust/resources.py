from collections import OrderedDict

from . import six
from .exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from .fields import Field
from .query import QuerySet
from .utils import subclass_exception


class Options(object):

    def __init__(self, meta):
        self.api = None
        self.meta = meta
        self.resource_name = getattr(meta, "resource_name", None)
        self.fields = OrderedDict()

    def contribute_to_class(self, cls, name):
        cls._meta = self

        if self.resource_name is None:
            # Determine the resource_name from the class name
            self.resource_name = cls.__name__.lower()

        self.api = self.meta.api

        # Create the fields that are specified as strings
        for fieldname in getattr(self.meta, "fields", []):
            self.add_field(Field(name=fieldname))

    def add_field(self, field):
        _fields = list(self.fields.items())
        _fields.append((field.name, field))
        _fields.sort(key=lambda x: x[1].creation_counter)
        self.fields = OrderedDict(_fields)


class ResourceBase(type):
    """
    Metaclass for all Resources.
    """

    def __new__(cls, name, bases, attrs):
        super_new = super(ResourceBase, cls).__new__

        # six.with_metaclass() inserts an extra class called 'NewBase' in the
        # inheritance tree: Model -> NewBase -> object. Ignore this class.
        parents = [b for b in bases if isinstance(b, ResourceBase) and not (b.__name__ == 'NewBase' and b.__mro__ == (b, object))]

        if not parents:
            # If this isn't a subclass of Resource, don't do anything special.
            return super_new(cls, name, bases, attrs)

        # Create the class
        module = attrs.pop("__module__")
        new_class = super_new(cls, name, bases, {"__module__": module})

        attr_meta = attrs.pop("Meta", None)

        if not attr_meta:
            meta = getattr(new_class, "Meta", None)
        else:
            meta = attr_meta

        new_class.add_to_class("_meta", Options(meta))

        new_class.add_to_class(
                    "DoesNotExist",
                    subclass_exception(
                        str("DoesNotExist"),
                        tuple(x.DoesNotExist for x in parents if hasattr(x, "_meta")) or (ObjectDoesNotExist,),
                        module,
                        attached_to=new_class
                    )
                )
        new_class.add_to_class(
                    "MultipleObjectsReturned",
                    subclass_exception(
                        str("MultipleObjectsReturned"),
                        tuple(x.MultipleObjectsReturned for x in parents if hasattr(x, "_meta")) or (MultipleObjectsReturned,),
                        module,
                        attached_to=new_class
                    )
                )

        new_class = new_class._meta.api.bind(new_class)

        # Add all non-field attributes to the class.
        for obj_name, obj in attrs.items():
            if isinstance(obj, Field):
                obj.name = obj_name
                new_class._meta.add_field(obj)
            else:
                new_class.add_to_class(obj_name, obj)

        if not hasattr(new_class, "objects"):
            new_class.objects = QuerySet(new_class)

        return new_class

    def add_to_class(cls, name, value):
        if hasattr(value, "contribute_to_class"):
            value.contribute_to_class(cls, name)
        else:
            setattr(cls, name, value)


class Resource(six.with_metaclass(ResourceBase, object)):

    def __init__(self, resource_uri=None, *args, **kwargs):
        field_kwargs = dict([(k, v) for k, v in kwargs.items() if k in self._meta.fields])
        kwargs = dict([(k, v) for k, v in kwargs.items() if k not in self._meta.fields])

        super(Resource, self).__init__(*args, **kwargs)

        self.resource_uri = resource_uri

        for name, field in self._meta.fields.items():
            val = field_kwargs.pop(name, None)
            setattr(self, name, field.hydrate(val))

    def __repr__(self):
        try:
            u = six.text_type(self)
        except (UnicodeEncodeError, UnicodeDecodeError):
            u = "[Bad Unicode data]"
        return "<%s: %s>" % (self.__class__.__name__, u)

    def __str__(self):
        if not six.PY3 and hasattr(self, "__unicode__"):
            return self.encode("utf-8")
        return "%s object" % self.__class__.__name__

    def save(self, force_insert=False, force_update=False):
        """
        Saves the current instance. Override this in a subclass if you want to
        control the saving process.

        The 'force_insert' and 'force_update' parameters can be used to insist
        that the "save" must be a POST or PUT respectively. Normally, they
        should not be set.
        """
        if force_insert and force_update:
            raise ValueError("Cannot force both insert and updating in resource saving.")

        data = {}

        for name, field in self._meta.fields.items():
            if field.serialize:
                data[name] = field.dehydrate(getattr(self, name, None))

        insert = True if force_insert or self.resource_uri is None else False

        if insert:
            r = self._meta.api.http_resource("POST", self._meta.resource_name, data=self._meta.api.resource_serialize(data))
        else:
            r = self._meta.api.http_resource("PUT", self.resource_uri, data=self._meta.api.resource_serialize(data))

        if "Location" in r.headers:
            r = self._meta.api.http_resource("GET", r.headers["Location"])

        data = self._meta.api.resource_deserialize(r.text)

        # Update local values from the API Response
        self.__init__(**data)
