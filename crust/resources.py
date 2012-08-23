from . import six
from .exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from .query import QuerySet
from .utils import subclass_exception


class Options(object):

    def __init__(self, meta):
        self.api = None
        self.meta = meta
        self.resource_name = getattr(meta, "resource_name", None)

    def contribute_to_class(self, cls, name):
        cls._meta = self

        if self.resource_name is None:
            # Determine the resource_name from the class name
            self.resource_name = cls.__name__.lower()

        self.api = self.meta.api


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

        # Add all attributes to the class.
        for obj_name, obj in attrs.items():
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

    def _from_response_dict(self, response_dict):
        for k, v in response_dict.items():
            setattr(self, k, v)
