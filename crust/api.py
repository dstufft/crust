import json
import posixpath

from . import requests
from . import six
from .exceptions import ResponseError


class Api(object):

    resources = {}

    def __init__(self, session=None, *args, **kwargs):
        super(Api, self).__init__(*args, **kwargs)

        if session is None:
            session = requests.session()

        self.session = session

    def __getattr__(self, name):
        if name in self.resources:
            return self.resources[name]

        raise AttributeError("'{0}' object has no attribute '{1}'".format(self.__class__.__name__, name))

    @classmethod
    def bind(cls, resource):
        instance = resource()
        cls.resources[instance._meta.resource_name] = resource

        return resource

    @staticmethod
    def resource_serialize(o):
        """
        Returns JSON serialization of given object.
        """
        return json.dumps(o)

    @staticmethod
    def resource_deserialize(s):
        """
        Returns dict deserialization of a given JSON string.
        """

        try:
            return json.loads(s)
        except ValueError:
            raise ResponseError("The API Response was not valid.")

    def url_for(self, *args):
        args = [str(arg) for arg in args]
        path = posixpath.join(*args)
        return "/".join([self.url, path]) + "/"

    def http_resource(self, method, resource, url=None, params=None, data=None):
        """
        Makes an HTTP request.
        """

        if isinstance(resource, six.string_types):
            resource = [resource]

        url = url or self.url_for(*resource)
        r = self.session.request(method, url, params=params, data=data)

        r.raise_for_status()

        return r
