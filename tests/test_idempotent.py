# coding=utf8

import time


def test_simple(app, app_client):
    data = dict(email='hit9@icloud.com', password='1234567890')
    r = app_client.put('/user', data=data)
    r.status_code == 200
    # Again
    r = app_client.put('/user', data=data)
    r.status_code == 200
    # Should failed after timeout
    time.sleep(1)
    r = app_client.put('/user', data=data)
    r.status_code != 200


def test_auto_register(auto_registered_app, app_client):
    for endpoint, view_function in auto_registered_app.view_functions.items():
        if endpoint != 'static':
            assert getattr(view_function, '_idempotent_wrapped', False)
