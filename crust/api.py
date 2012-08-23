from . import requests


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
