# coding=utf8

import json
from flask_idempotent2 import gen_keyfunc


def test_keyfunc_consistence(app):
    default_keyfunc = gen_keyfunc()
    with app.test_request_context(method='PUT',
                                  path='/user',
                                  content_type='application/json',
                                  query_string=dict(key='val'),
                                  data=json.dumps(dict(key='val2'))):
        key1 = default_keyfunc()
        key2 = default_keyfunc()
        assert key1 == key2


def test_keyfunc_query_string(app):
    default_keyfunc = gen_keyfunc(use_checksum=False)
    with app.test_request_context(query_string=dict(a=1)):
        key1 = default_keyfunc()
    with app.test_request_context(query_string=dict(a=2)):
        key2 = default_keyfunc()
    assert key1 != key2


def test_keyfunc_query_string_inv(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, query_string=False)
    with app.test_request_context(query_string=dict(a=1)):
        key1 = default_keyfunc()
    with app.test_request_context(query_string=dict(a=1)):
        key2 = default_keyfunc()
    assert key1 == key2


def test_keyfunc_method(app):
    default_keyfunc = gen_keyfunc(use_checksum=False)
    with app.test_request_context(method='GET', path='/user/1'):
        key1 = default_keyfunc()
    with app.test_request_context(method='POST', path='/user/1'):
        key2 = default_keyfunc()
    assert key1 != key2


def test_keyfunc_method_inv(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, method=False)
    with app.test_request_context(method='GET', path='/user/1'):
        key1 = default_keyfunc()
    with app.test_request_context(method='POST', path='/user/1'):
        key2 = default_keyfunc()
    assert key1 == key2


def test_keyfunc_path(app):
    default_keyfunc = gen_keyfunc(use_checksum=False)
    with app.test_request_context(method='GET', path='/user/1'):
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/2'):
        key2 = default_keyfunc()
    assert key1 != key2


def test_keyfunc_path_inv(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, path=False)
    with app.test_request_context(method='GET', path='/user/1'):
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/2'):
        key2 = default_keyfunc()
    assert key1 == key2


def test_keyfunc_data(app):
    default_keyfunc = gen_keyfunc(use_checksum=False)
    with app.test_request_context(method='PUT', path='/user',
                                  content_type='application/json',
                                  data=json.dumps(dict(key='val2'))):
        key1 = default_keyfunc()
    with app.test_request_context(method='PUT', path='/user',
                                  content_type='application/json',
                                  data=json.dumps(dict(key='val4'))):
        key2 = default_keyfunc()
    assert key1 != key2


def test_keyfunc_data_inv(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, data=False)
    with app.test_request_context(method='PUT', path='/user',
                                  content_type='application/json',
                                  data=json.dumps(dict(key='val2'))):
        key1 = default_keyfunc()
    with app.test_request_context(method='PUT', path='/user',
                                  content_type='application/json',
                                  data=json.dumps(dict(key='val4'))):
        key2 = default_keyfunc()
    assert key1 == key2


def test_keyfunc_headers(app):
    keyfunc = gen_keyfunc(use_checksum=False, headers=['key'])
    with app.test_request_context(method='GET', path='/user/1',
                                  headers={'key': 'val1'}):
        key1 = keyfunc()
    with app.test_request_context(method='GET', path='/user/1',
                                  headers={'key': 'val2'}):
        key2 = keyfunc()
    assert key1 != key2


def test_keyfunc_headers_inv(app):
    keyfunc = gen_keyfunc(use_checksum=False, headers=None)
    with app.test_request_context(method='GET', path='/user/1',
                                  headers={'key': 'val1'}):
        key1 = keyfunc()
    with app.test_request_context(method='GET', path='/user/1',
                                  headers={'key': 'val2'}):
        key2 = keyfunc()
    assert key1 == key2


def test_keyfunc_session(app):
    default_keyfunc = gen_keyfunc(use_checksum=False)
    from flask import session
    with app.test_request_context(method='GET', path='/user/1'):
        session['key'] = 'val1'
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/1'):
        session['key'] = 'val2'
        key2 = default_keyfunc()
    assert key1 != key2


def test_keyfunc_session_inv(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, session=False)
    from flask import session
    with app.test_request_context(method='GET', path='/user/1'):
        session['key'] = 'val1'
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/1'):
        session['key'] = 'val2'
        key2 = default_keyfunc()
    assert key1 == key2


def test_keyfunc_content_length(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, data=False)
    with app.test_request_context(method='GET', path='/user/1',
                                  content_length=3, data=b'abc'):
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/1',
                                  content_length=4, data='abcd'):
        key2 = default_keyfunc()
    assert key1 != key2


def test_keyfunc_content_length_inv(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, data=False,
                                  content_length=False)
    with app.test_request_context(method='GET', path='/user/1',
                                  content_length=3, data=b'abc'):
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/1',
                                  content_length=4, data='abcd'):
        key2 = default_keyfunc()
    assert key1 == key2


def test_keyfunc_content_type(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, data=False)
    with app.test_request_context(method='GET', path='/user/1',
                                  content_type='application/json',
                                  data=json.dumps(dict(a='b'))):
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/1',
                                  content_type='application/form',
                                  data=json.dumps(dict(a='b'))):
        key2 = default_keyfunc()
    assert key1 != key2


def test_keyfunc_content_type_inv(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, data=False,
                                  content_type=False)
    with app.test_request_context(method='GET', path='/user/1',
                                  content_type='application/json',
                                  data=json.dumps(dict(a='b'))):
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/1',
                                  content_type='application/form',
                                  data=json.dumps(dict(a='b'))):
        key2 = default_keyfunc()
    assert key1 == key2


def test_keyfunc_remote_addr(app):
    default_keyfunc = gen_keyfunc(use_checksum=False)
    with app.test_request_context(method='GET', path='/user/1',
                                  headers={'X-Forwarded-For': '192.168.1.1'}):
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/1',
                                  headers={'X-Forwarded-For': '192.168.1.2'}):
        key2 = default_keyfunc()
    assert key1 != key2


def test_keyfunc_remote_addr_inv(app):
    default_keyfunc = gen_keyfunc(use_checksum=False, remote_addr=False)
    with app.test_request_context(method='GET', path='/user/1',
                                  headers={'X-Forwarded-For': '192.168.1.1'}):
        key1 = default_keyfunc()
    with app.test_request_context(method='GET', path='/user/1',
                                  headers={'X-Forwarded-For': '192.168.1.2'}):
        key2 = default_keyfunc()
    assert key1 == key2
