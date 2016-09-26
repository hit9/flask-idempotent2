# coding=utf8

"""
    flask-idempotent2
    ~~~~~~~~~~~~~~~~~

    Redis based idempotent support for sqlalchemy based flask applications.

    :copyright: (c) 2016 by Chao Wang (hit9).
    :license: BSD, see LICENSE for more details.
"""

import hashlib
import functools

from flask import g, request, session
from sqlalchemy import event
from sqlalchemy.inspection import inspect


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
    """The idempotent object implements idempotent support for sqlalchemy based
    flask applications. It acts as a central registry for idempotent view
    functions. Example::

        from flask import Flask
        import redis
        from .models import Session

        app = Flask(__name__)
        redis_client = redis.StrictRedis()
        idempotent = Idempotent(app, redis_client, Session)

        @app.route('/resource', methods=['PUT'])
        @idempotent
        def create_or_update():
            pass

    :param app: A flask application object to work with.
    :param redis: A redis client constructed by `redis-py`.
    :param session_factory: A sqlalchemy session factory.
    :param default_timeout: The redis cache timeout, or expiration in
       seconds, for all view functions by default. Default to `20`.
    :param default_keyfunc: `keyfunc` for all view functions by default.
       Default to ``gen_keyfunc()``.
    :param redis_key_prefix: The key prefix string to use in redis. Default to
       ``'idempotent:'``.
    """

    def __init__(self, app, redis, session_factory, default_timeout=20,
                 default_keyfunc=None, redis_key_prefix='idempotent:'):
        self.app = app
        self.redis = redis
        self.session_factory = session_factory
        self.default_timeout = default_timeout
        self.default_keyfunc = default_keyfunc or gen_keyfunc()
        # Register sqlalchemy events.
        self.register_sqlalchemy_events()

    ###
    # Decoration
    ###

    def __call__(self, func):
        """Decorate given `func` to be an idempotent interface. Example::

            @app.route('/api', methods=['PUT'])
            @idempotent
            def api():
                pass

        """
        return self.wrap_view_func(func, timeout=None, keyfunc=None)

    def parametrize(self, timeout=None, keyfunc=None):
        """Produce a decorator to wrap view function to be an idempotent
        interface. Example::

            @app.route('/api', methods=['PUT'])
            @idempotent.parametrize(timeout=5)
            def api():
                pass

        :param timeout: Idempotent cache expiration in redis, in seconds. If
           passed, it will be used instead of `default_timeout`.
        :param keyfunc: `keyfunc` to distinguish requests. Which can be
           generated by `gen_keyfunc`. If passed, it will be used instead of
           `default_keyfunc`.

        """

        def decorator(func):
            return self.wrap_view_func(func, timeout=timeout, keyfunc=keyfunc)
        return decorator

    def auto_register(self, http_methods=None, reserved_endpoints=None):
        """Register view function with given `http_methods` as idempotent
        interfaces. Example::

            idempotent = Idempotent(app, redis_client, Session)
            idempotent.auto_register()

        :param http_methods: The http methods to discover view functions.
           Default to ``['GET', 'PUT', 'DELETE']``.
        :param reserved_endpoints: List of endpoints to be reserved. Default to
           ``['static']``.

        """
        if http_methods is None:
            http_methods = ['GET', 'PUT', 'DELETE']
        if reserved_endpoints is None:
            reserved_endpoints = ['static']

        for endpoint, view_func in app.view_functions.items():
            if endpoint in reserved_endpoints:
                continue
            self.wrap_view_func(view_func)

    def wrap_view_func(self, func, timeout=None, keyfunc=None):
        """Wrap a flask `view_func` to be idempotent.

        :param timeout: Idempotent cache expiration in redis, in seconds. If
           passed, it will be used instead of `default_timeout`.
        :param keyfunc: `keyfunc` to distinguish requests. Which can be
           generated by `gen_keyfunc`. If passed, it will be used instead of
           `default_keyfunc`.

        """
        if timeout is None:
            timeout = self.default_timeout
        if keyfunc is None:
            keyfunc = self.default_keyfunc

        @functools.wrap(func)
        def wrapped_view_function(*args, **kwargs):
            # Do something..
            return func(*args, **kwargs)
        return wrapped_view_function

    ###
    # SQLAlchemy Events
    ###

    def register_sqlalchemy_events(self):
        """Register sqlalchemy event listeners.
        """
        event.listen(self.session_factory, 'before_flush',
                     self.record_changed_instances)
        event.listen(self.session_factory, 'before_commit',
                     self.record_changed_instances)
        event.listen(self.session_factory, 'after_rollback',
                     self.clear_changed_instances)
        event.listen(self, session_factory, 'after_commit',
                     self.record_committed_changes)

    def record_changed_instances(self, session, flush_context, instances):
        """Record changed resource instances to ``flask.g`` before sqlalchemy
        session flush or commit. The ``flask.g`` is request scoped, it's new
        for each request.

        Note that the ``after_commit()`` hook is not per-flush, that is, the
        Session can emit SQL to the database many times within the scope of a
        transaction.
        """
        if not hasattr(g, '_idempotent_changes'):
            g._idempotent_changes = []
        # New instances.
        for instance in session.new:
            g._idempotent_changes.append(instance)
        # Dirty instances.
        for instance in session.dirty:
            g._idempotent_changes.append(instance)
        # Deleted instances.
        for instance in session.deleted:
            g._idempotent_changes.append(instance)

    def get_instance_primary_key(self, inst):
        """Get instance primary key value. Note that the first primary key
        will be used. Returns ``None`` if given `inst` has no primary key
        value yet.
        """
        pk = inspect(inst.__class__).primary_key[0]
        return getattr(inst, pk, None)

    def clear_changed_instances(self, session):
        """Clear changed instances after sqlalchemy session rollback.
        """
        g._idempotent_changes = []
        g._idempotent_committed_changes = []

    def record_committed_changes(self, session):
        """Record committed changes to ``flask.g`` after sqlalchemy session
        commit.
        """
        changes = getattr(g, '_idempotent_changes', None)
        if changes:
            g._idempotent_committed_changes = changes
            g._idempotent_changes = []
