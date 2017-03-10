# coding=utf8

"""
    flask-idempotent2
    ~~~~~~~~~~~~~~~~~

    Redis based idempotent support for sqlalchemy based flask applications.

    :copyright: (c) 2016 by Chao Wang (hit9).
    :license: BSD, see LICENSE for more details.
"""

import functools
import hashlib
import pickle

from flask import g, request, session as flask_session, Response, \
    _app_ctx_stack
from sqlalchemy import event
from sqlalchemy.inspection import inspect


__version__ = '0.0.3'


def gen_keyfunc(path=True, method=True, query_string=True, data=True,
                headers=None, session=True, content_type=True,
                content_length=True, remote_addr=True, use_checksum=True):
    """Generate a `keyfunc` that distinguishes requests on different
    dimensions.

    :param path: Defaults to ``True``. When ``True``, idempotent requests will
       be distinguished by ``request.path``.
    :param method: Defaults to ``True``. When ``True``, idempotent requests
       will be distinguished by ``request.method``.
    :param query_string: Defaults to ``True``. When ``True``, idempotent
       requests be distinguished by ``request.query_string``.
    :param data: Defaults to ``True``. When ``True``, idempotent requests will
       be distinguished by ``request.data``.
    :param headers: An optional list of requets headers to distinguish
       idemptent requests.
    :param session: Defaults to ``True``. When ``True``, idempotent
       requests will be distinguished by ``flask.session``.
    :param content_type: Defaults to ``True``. When ``True``, idempotent
       requests will be distinguished by ``request.content_type``.
    :param content_length: Defaults to ``True``. When ``True``, idempotent
       requests will be distinguished by ``request.content_length.
    :param remote_addr: Defaults to ``True``. When ``True``, idempotent
       requests will be distinguished by client remote address. The
       `remote_addr` to use is either `X-Forwarded-For` in headers or flask
       ``request.remote_addr``.
    :param use_checksum: Defaults to ``True``. When ``True``, use checksum
       string instead of original key.
    """

    def keyfunc():
        dimensions = {}
        if path:
            dimensions['path'] = request.path
        if method:
            dimensions['method'] = request.method
        if query_string:
            dimensions['query_string'] = request.query_string
        if data:
            dimensions['data'] = request.data
        if headers:
            d = {}
            for name in headers:
                d[name] = request.headers.get(name, None)
            dimensions['headers'] = str(sorted(d.items()))
        if session:
            dimensions['session'] = str(sorted(flask_session.items()))
        if content_type:
            dimensions['content_type'] = request.content_type
        if content_length:
            dimensions['content_length'] = request.content_length
        if remote_addr:
            dimensions['remote_addr'] = request.headers.get(
                'X-Forwarded-For',
                request.remote_addr)
        origin_key = str(sorted(dimensions.items()))
        if use_checksum:
            # Use hashed stringify dimensions
            sha = hashlib.sha1()
            sha.update(origin_key.encode('utf8'))
            return sha.hexdigest()
        return origin_key
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
       seconds, for all view functions by default. Default to `30`.
    :param default_keyfunc: `keyfunc` for all view functions by default.
       Default to ``gen_keyfunc()``.
    :param redis_key_prefix: The key prefix string to use in redis. Default to
       ``'idempotent'``.
    :param enable_idempotent_lock: Default to ``True``. When ``True``, redis
       idempotent lock will be enabled. This lock makes concurrent idempotent
       requests to be executed one by one.
    :param g_: The global context to use, defaults to be ``None``. Setting to
       ``None`` means ``flask.g``.
    """

    def __init__(self, app, redis, session_factory, default_timeout=30,
                 default_keyfunc=None, redis_key_prefix='idempotent',
                 enable_idempotent_lock=True, g_=None):
        self.app = app
        self.redis = redis
        self.session_factory = session_factory
        self.default_timeout = default_timeout
        self.default_keyfunc = default_keyfunc or gen_keyfunc()
        self.redis_key_prefix = redis_key_prefix
        self.enable_idempotent_lock = enable_idempotent_lock
        self.g_ = g_ or g
        # Register sqlalchemy events.
        self.register_sqlalchemy_events()

    ###
    # Public API
    ###

    def __call__(self, func):
        """Decorate given `func` to be an idempotent interface. Example::

            @app.route('/api', methods=['PUT'])
            @idempotent
            def api():
                pass

        :param func: Flask view function to wrap.

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

        for url_rule in self.app.url_map.iter_rules():
            if url_rule.endpoint in reserved_endpoints:
                continue
            for http_method in url_rule.methods:
                if http_method in http_methods:
                    view_function = self.app.view_functions[url_rule.endpoint]
                    if getattr(view_function, '_idempotent_forget', False):
                        continue  # Skip forgetted funcs
                    self.app.view_functions[url_rule.endpoint] = \
                        self.wrap_view_func(view_function)

    def forget(self, func):
        """Do not register given view function as idempotent when use
        ``auto_register``. Example::

            @app.route('/api', methods=['PUT'])
            @idempotent.forget
            def forget_me():
                pass

        :param func: Flask view function to wrap.

        """
        func._idempotent_forget = True
        return func

    ###
    # SQLAlchemy Events
    ###

    def register_sqlalchemy_events(self):
        """Register sqlalchemy event listeners.

        Note that registered hook functions will be called only if current
        invoked view function is marked as idempotent.
        """
        event.listen(self.session_factory, 'before_flush',
                     self.record_changed_instances)
        event.listen(self.session_factory, 'before_commit',
                     self.record_changed_instances)
        event.listen(self.session_factory, 'after_rollback',
                     self.clear_changed_instances)
        event.listen(self.session_factory, 'after_commit',
                     self.record_committed_changes)

    def should_call_sqlalchemy_hook(self):
        """Returns ``True`` if current invoked view function is marked as
        idempotent.
        Returns ``False`` if current progress is out side flask request
        context.
        """
        if _app_ctx_stack.top is None:  # Outside flask
            return False
        view_function = self.app.view_functions.get(request.endpoint, None)
        return view_function and getattr(view_function, '_idempotent_wrapped',
                                         False)

    def record_changed_instances(self, session, flush_context=None,
                                 instances=None):
        """Record changed resource instances to ``self.g_`` before sqlalchemy
        session flush or commit. The ``self.g_`` is request scoped, it's new
        for each request.

        Note that the ``after_commit()`` hook is not per-flush, that is, the
        Session can emit SQL to the database many times within the scope of a
        transaction.
        """
        if not self.should_call_sqlalchemy_hook():
            return
        if not hasattr(self.g_, '_idempotent_changes'):
            self.g_._idempotent_changes = []
        # New instances.
        for instance in session.new:
            self.g_._idempotent_changes.append(instance)
        # Dirty instances.
        for instance in session.dirty:
            self.g_._idempotent_changes.append(instance)
        # Deleted instances.
        for instance in session.deleted:
            self.g_._idempotent_changes.append(instance)

    def clear_changed_instances(self, session):
        """Clear changed instances after sqlalchemy session rollback.
        """
        if not self.should_call_sqlalchemy_hook():
            return
        self.g_._idempotent_changes = []
        self.g_._idempotent_committed_changes = []

    def record_committed_changes(self, session):
        """Record committed changes to ``self.g_`` after sqlalchemy session
        commit.
        """
        if not self.should_call_sqlalchemy_hook():
            return
        changes = getattr(self.g_, '_idempotent_changes', None)
        if changes:
            self.g_._idempotent_committed_changes = changes
            self.g_._idempotent_changes = []

    ###
    # Idempotent Cache
    ###

    def wrap_view_func(self, func, timeout=None, keyfunc=None):
        """Wrap a flask `view_func` to be idempotent.

        Notes:

            1. A view function won't be wrapped again if it's already wrapped.
            2. A view function won't be wraped if it's marked to forget.

        :param timeout: Idempotent cache expiration in redis, in seconds. If
           passed, it will be used instead of `default_timeout`.
        :param keyfunc: `keyfunc` to distinguish requests. Which can be
           generated by `gen_keyfunc`. If passed, it will be used instead of
           `default_keyfunc`.

        """
        if getattr(func, '_idempotent_forget', False):
            return func

        if getattr(func, '_idempotent_wrapped', False):
            # Register only once.
            return func

        if timeout is None:
            timeout = self.default_timeout
        if keyfunc is None:
            keyfunc = self.default_keyfunc

        @functools.wraps(func)
        def wrapped_view_function(*args, **kwargs):
            idempotent_id = keyfunc()
            cached_response = self.get_cached_response(idempotent_id)
            if cached_response is not None:
                return cached_response
            response = func(*args, **kwargs)
            self.set_response_cache(idempotent_id, response, timeout)
            return response
        wrapped_view_function._idempotent_wrapped = True
        return wrapped_view_function

    def format_redis_key(self, origin_key):
        """Format `origin_key` with redis prefix and app name.

        :param origin_key: The original key without prefix.
        """
        return '{0}:{1}:{2}'.format(self.redis_key_prefix, self.app.name,
                                    origin_key)

    def loads_cached_value(self, value):
        """Loads cached value into flask response and list of resource
        instances. Returns a tuple in format of `(response, instances)`.

        :param value: String value read from redis.
        """
        return pickle.loads(value)

    def dumps_response_and_changed_instances(self, response):
        """Dumps response and changed instances into string to used as redis
        cached value. The serialization is based on ``pickle``. Returns a
        tuple in format of `(picked, instance_strings)`.

        :param response: The `flask.Response` instance to be dump as string.
        """
        data = []

        # Given `response` may be a ``string``, ``tuple`` or ``Response``.
        if isinstance(response, Response):
            # Freeze response instances before ``pickle``.
            response.freeze()
        data.append(response)

        instances = set()

        # Committed instances, in format of ``[string, ...]``. Each
        # ``instance_str`` is constructed by resource name and primary key
        # value, e.g. ``'User:1'``.
        for instance in getattr(self.g_, '_idempotent_committed_changes', []):
            instance_state = inspect(instance)
            if instance_state.persistent:
                cls = instance_state.class_
                name = cls.__name__  # resource name
                pk_column = inspect(cls).primary_key[0]  # pk name
                pk = getattr(instance, pk_column.name, None)
                instance_str = '{0}:{1}'.format(name, pk)
            instances.add(instance_str)

        data.append(instances)
        return pickle.dumps(data), instances

    def get_cached_response(self, idempotent_id):
        """Get idempotent request cache before view function is called. Returns
        ``None`` on cache miss.

        :param idempotent_id: Idempotent reuqest string id produced by
           `keyfunc`.
        """
        # Get cached response and affected instances.
        key = self.format_redis_key(idempotent_id)
        value = self.redis.get(key)
        if not value:
            return  # Miss

        # Get affected instances and validate
        response, instances = self.loads_cached_value(value)
        if instances:
            keys = [self.format_redis_key(k) for k in instances]
            values = self.redis.mget(keys)
            for value in values:
                if value.decode('utf8') != idempotent_id:
                    self.redis.delete(key)
                    return  # Miss
        return response  # Hit

    def set_response_cache(self, idempotent_id, response, timeout):
        """Set idempotent request cache after view function is actually called.

        :param response: The response to cache.
        :param timeout: Cache expiration in seconds.
        :param idempotent_id: Idempotent reuqest string id produced by
           `keyfunc`.
        """
        pipeline = self.redis.pipeline()
        value, instances = self.dumps_response_and_changed_instances(response)

        # Cache response by `idempotent_id`.
        key = self.format_redis_key(idempotent_id)
        pipeline.setex(key, timeout, value)

        # Cache affected instances.
        for instance_str in instances:
            pipeline.setex(self.format_redis_key(instance_str), timeout,
                           idempotent_id)

        pipeline.execute()
