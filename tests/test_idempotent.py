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
