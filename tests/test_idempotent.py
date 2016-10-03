# coding=utf8

import time


def test_simple(app, app_client):
    data = dict(email='hit9@icloud.com', password='1234567890')
    r = app_client.put('/user', data=data)
    assert r.status_code == 200
    # Again
    r = app_client.put('/user', data=data)
    assert r.status_code == 200
    # Should failed after timeout
    time.sleep(1)
    r = app_client.put('/user', data=data)
    assert r.status_code != 200


def test_auto_register(auto_registered_app):
    for endpoint, view_function in auto_registered_app.view_functions.items():
        if endpoint != 'static':
            assert getattr(view_function, '_idempotent_wrapped', False)


def test_forget(with_forget_app):
    for endpoint, view_function in with_forget_app.view_functions.items():
        if endpoint == 'get_user':
            assert getattr(view_function, '_idempotent_forget', False)
            assert not hasattr(view_function, '_idempotent_wrapped')


def test_no_db_events_idempotent(app, app_client):
    r = app_client.get('/random')
    assert r.status_code == 200
    data = r.json['result']
    # Again
    r = app_client.get('/random')
    assert r.status_code == 200
    assert r.json['result'] == data
    # Should  after timeout
    time.sleep(1)
    r = app_client.get('/random')
    assert r.status_code == 200
    assert r.json['result'] != data
