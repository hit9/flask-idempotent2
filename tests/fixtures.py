# coding=utf8

import json
import sys
import random

from flask import Flask, _app_ctx_stack, request, jsonify
from sqlalchemy import create_engine, Column, String, Integer, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from flask_idempotent2 import Idempotent
import redis
import pytest


###
# Redis
###

@pytest.fixture(scope='session')
def redis_client():
    return redis.StrictRedis()


@pytest.fixture(scope='function')
def redis_clear(redis_client):
    yield
    redis_client.flushdb()


###
# DB
###

engine = create_engine(
    'postgresql+psycopg2://localhost/flask_idempotent2_unittesting')
DBSession = scoped_session(sessionmaker(bind=engine, autocommit=False,
                                        expire_on_commit=False))
DeclarativeBase = declarative_base()


class User(DeclarativeBase):
    __tablename__ = 't_user'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)


@pytest.fixture(scope='session')
def db_tables():
    DeclarativeBase.metadata.drop_all(engine)
    DeclarativeBase.metadata.create_all(engine)


@pytest.fixture(scope='function')
def db_clear(db_tables):
    yield
    # Truncate tables
    for table in DeclarativeBase.metadata.sorted_tables:
        sql = text('TRUNCATE TABLE {};'.format(table.name))
        DBSession.execute(sql)
        DBSession.commit()
    # Remove session after db related test case
    DBSession.remove()


###
# APP
###

@pytest.fixture(scope='function')
def app(db_clear, redis_client, redis_clear):
    Session = scoped_session(sessionmaker(bind=engine,
                                          autocommit=False,
                                          expire_on_commit=False),
                             scopefunc=_app_ctx_stack.__ident_func__)
    app = Flask(__name__)
    idempotent = Idempotent(app, redis_client, Session)

    def defer_commit(func):
        def wrapped(*args, **kwargs):
            ret = func(*args, **kwargs)
            session = Session()
            try:
                session.flush()
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                raise exc
            return ret
        return wrapped

    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_exc(exc):
        return jsonify(message='database error'), 500

    @app.teardown_request
    def close_session(exc):
        Session.remove()

    @app.route('/user', methods=['PUT'])
    @idempotent.parametrize(timeout=1)
    @defer_commit
    def create_user():
        data = request.get_json()
        user = User(email=data['email'], password=data['password'])
        Session().add(user)
        return jsonify(email=user.email, password=user.password)

    @app.route('/user/<int:id>', methods=['GET'])
    @idempotent.parametrize(timeout=1)
    def get_user(id):
        return Session().query(User).get(id)

    @app.route('/random', methods=['GET'])
    @idempotent.parametrize(timeout=1)
    def get_random():
        return jsonify(result=random.randint(1, 1000))

    app.secret_key = 'secret'
    return app


@pytest.fixture(scope='function')
def auto_registered_app(db_clear, redis_client, redis_clear):
    Session = scoped_session(sessionmaker(bind=engine,
                                          autocommit=False,
                                          expire_on_commit=False),
                             scopefunc=_app_ctx_stack.__ident_func__)
    app = Flask(__name__)
    idempotent = Idempotent(app, redis_client, Session)

    def defer_commit(func):
        def wrapped(*args, **kwargs):
            ret = func(*args, **kwargs)
            session = Session()
            try:
                session.flush()
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                raise exc
            return ret
        return wrapped

    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_exc(exc):
        return jsonify(message='database error'), 500

    @app.teardown_request
    def close_session(exc):
        Session.remove()

    @app.route('/user', methods=['PUT'])
    @defer_commit
    def create_user():
        data = request.get_json()
        user = User(email=data['email'], password=data['password'])
        Session().add(user)
        return jsonify(email=user.email, password=user.password)

    @app.route('/user/<int:id>', methods=['GET'])
    def get_user(id):
        return Session().query(User).get(id)

    app.secret_key = 'secret'
    idempotent.auto_register()
    return app


@pytest.fixture(scope='function')
def with_forget_app(db_clear, redis_client, redis_clear):
    Session = scoped_session(sessionmaker(bind=engine,
                                          autocommit=False,
                                          expire_on_commit=False),
                             scopefunc=_app_ctx_stack.__ident_func__)
    app = Flask(__name__)
    idempotent = Idempotent(app, redis_client, Session)

    def defer_commit(func):
        def wrapped(*args, **kwargs):
            ret = func(*args, **kwargs)
            session = Session()
            try:
                session.flush()
                session.commit()
            except SQLAlchemyError as exc:
                session.rollback()
                raise exc
            return ret
        return wrapped

    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_exc(exc):
        return jsonify(message='database error'), 500

    @app.teardown_request
    def close_session(exc):
        Session.remove()

    @app.route('/user', methods=['PUT'])
    @defer_commit
    def create_user():
        data = request.get_json()
        user = User(email=data['email'], password=data['password'])
        Session().add(user)
        return jsonify(email=user.email, password=user.password)

    @app.route('/user/<int:id>', methods=['GET'])
    @idempotent.forget
    def get_user(id):
        return Session().query(User).get(id)

    app.secret_key = 'secret'
    idempotent.auto_register()
    return app


def patch_client(c):
    c._open = c.open

    def open(*args, **kws):
        if kws.get('data', None) is not None:
            kws['data'] = json.dumps(kws['data'])
            kws['content_type'] = 'application/json'
        r = c._open(*args, **kws)
        r.json = None
        if r.data:
            if sys.version_info.major == 3:
                data = str(r.data, 'utf8')
            else:
                data = r.data
            r.json = json.loads(data)
        return r
    c.open = open
    return c


@pytest.fixture(scope='function')
def app_native_client(app):
    with app.test_client() as c:
        return c


@pytest.fixture(scope='function')
def app_client(app_native_client):  # Patched
    return patch_client(app_native_client)
