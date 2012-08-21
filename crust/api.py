from . import requests


class Api(object):

    def __init__(self, url, session=None, *args, **kwargs):
        super(Api, self).__init__(*args, **kwargs)

        if session is None:
            session = requests.session()

        self.url = url
        self.session = session
