# coding=utf8

"""
    flask-idempotent2
    ~~~~~~~~~~~~~~~~~

    Redis based idempotent support for flask and sqlalchemy applications.

    :copyright: (c) 2016 by Chao Wang (hit9).
    :license: BSD, see LICENSE for more details.
"""

import hashlib

from flask import request, session


__version__ = '0.0.1'


def gen_keyfunc(endpoint=True, http_method=True, url_rule=True, view_args=True,
                request_json=True, request_headers=None, flask_session=True,
                remote_addr=True):
    """Generate a `keyfunc` that distinguishes requests on different
    dimensions.

    :param endpoint: Defaults to ``True``. When ``True``, idempotent requests
       will be distinguished by request endpoint.
    :param http_method: Defaults to ``True``. When ``True``, idempotent
       requests will be distinguished by request http method.
    :param url_rule: Defaults to ``True``. When ``True``, idempotent requests
       will be distinguished by `url_rule`, actually by the flask
       ``str(request.url_rule)``, e.g. `/<int:id>''.
    :param view_args: Defaults to ``True``. When ``True``, idempotent requests
       will be distinguished by `view_args`, actually by the flask
       ``request.view_args`.
    :param request_json: Defaults to ``True``. When ``True``, idempotent
       requests will be distinguished by request json body, actually by the
       flask ``request.get_json()``.
    :param request_headers: An optional dictionary of request headers to
       distinguish idempotent requests.
    :param flask_session: Defaults to ``True``. When ``True``, idempotent
       requests will be distinguished by `flask.session`.
    :param remote_addr: Defaults to ``True``. When ``True``, idempotent
       requests will be distinguished by client remote address. The
       `remote_addr` to use is either `X-Forwarded-For` in headers or flask
       ``request.remote_addr``.

    """

    def keyfunc():
        dimensions = {}
        if endpoint:
            dimensions['endpoint'] = request.endpoint
        if http_method:
            dimensions['http_method'] = request.method
        if url_rule:
            dimensions['url_rule'] = str(request.url_rule)
        if view_args:
            data = request.view_args
            if data is None:
                dimensions['view_args'] = 'None'
            else:
                dimensions['view_args'] = str(sorted(data.items()))
        if request_json:
            data = request.get_json()
            if data is None:
                dimensions['request_json'] = 'None'
            else:
                dimensions['request_json'] = str(sorted(data.items()))
        if request_headers:
            data = {}
            for name in request_headers:
                data[name] = request.headers.get(name, None)
            dimensions['request_headers'] = str(sorted(data.items()))
        if flask_session:
            dimensions['flask_session'] = str(sorted(session.items()))
        if remote_addr:
            dimensions['remote_addr'] = request.headers.get(
                'X-Forwarded-For',
                request.remote_addr)
        # Use hashed stringify dimensions
        origin_key = str(dimensions)
        sha = hashlib.sha1()
        sha.update(origin_key)
        return sha.hexdigest()
    return keyfunc


class Idempotent(object):
    """Idempotent implementation for flask and sqlalchemy applications.
    Example::

        from flask import Flask
        import redis
        from .models import Session

        app = Flask(__name__)
        redis_client = redis.StrictRedis()
        idempotent = Idempotent(app, redis_client, Session)
    """

    def __init__(self, app, redis, session_factory, default_timeout=20,
                 default_keyfunc=None):
        self.app = app
        self.redis = redis
        self.session_factory = session_factory
        self.default_timeout = default_timeout
        self.default_keyfunc = default_keyfunc or gen_keyfunc()

    def __call__(self, func):
        pass

    def parametrize(self, **kws):
        pass
