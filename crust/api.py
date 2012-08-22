import copy

from . import requests


class Api(object):

    def __init__(self, url, session=None, *args, **kwargs):
        super(Api, self).__init__(*args, **kwargs)

        if session is None:
            session = requests.session()

        self.url = url
        self.session = session
        self.resources = {}

    def __call__(self, resource):
        cls = copy.deepcopy(resource)
        cls._meta.api = self

        self.resources[resource._meta.resource_name] = cls

        return cls

    def __getattr__(self, name):
        if name in self.resources:
            return self.resources[name]

        raise AttributeError("'{0}' object has no attribute '{1}'".format(self.__class__.__name__, name))
