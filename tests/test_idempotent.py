# coding=utf8

import time

import gevent
import grequests
from gevent.wsgi import WSGIServer


def test_simple_cache(app, app_client):
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


def test_simple_lock(app, app_client):

    def _start_real_server():
        http_server = WSGIServer(('', 54321), app)
        http_server.serve_forever()

    server_thread = gevent.spawn(_start_real_server)

    def _stop_real_server():
        gevent.sleep(1)
        gevent.kill(server_thread)

    api_data_with_lock = dict(email='hit10@icloud.com', password='1234567890')
    api_url_with_lock = 'http://localhost:54321/user_or_return'
    requests_for_api_with_lock = [grequests.put(api_url_with_lock,
                                                json=api_data_with_lock)
                                  for i in range(5)]
    api_data_without_lock = dict(email='hit1@icloud.com',
                                 password='1234567890')
    api_url_without_lock = 'http://localhost:54321/user_or_return_nolock'
    requests_for_api_without_lock = [grequests.put(api_url_without_lock,
                                                   json=api_data_without_lock)
                                     for i in range(5)]
    rs1 = grequests.map(requests_for_api_with_lock, size=10)
    rs2 = grequests.map(requests_for_api_without_lock, size=10)

    stop_server_thread = gevent.spawn(_stop_real_server)
    stop_server_thread.join()

    assert [200] * 5 == [r.status_code for r in rs1]
    assert [200] == [r.status_code for r in rs2[:1]]
    assert [500] * 4 == [r.status_code for r in rs2[1:]]
