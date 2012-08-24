import json
import urllib.parse

from . import requests
from .exceptions import ResponseError


class Api(object):

    resources = {}
    unsupported_methods = []

    def __init__(self, session=None, *args, **kwargs):
        super(Api, self).__init__(*args, **kwargs)

        if session is None:
            session = requests.session()

        self.session = session

        self.unsupported_methods = [method.lower() for method in self.unsupported_methods]

        # Initialize the APIs
        for cls in self.resources.values():
            cls._meta.api = self

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

    def http_resource(self, method, url, params=None, data=None):
        """
        Makes an HTTP request.
        """

        url = urllib.parse.urljoin(self.url, url)
        url = url if url.endswith("/") else url + "/"

        headers = None

        if method.lower() in self.unsupported_methods:
            headers = {"X-HTTP-Method-Override": method.upper()}
            method = "POST"

        r = self.session.request(method, url, params=params, data=data, headers=headers)

        r.raise_for_status()

        return r
