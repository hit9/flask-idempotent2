flask-idempotent2
=================

Redis based automatic idempotent and concurrency lock support for 
sqlalchemy based flask applications. 

Idempotent
----------

It caches responses in redis by `request_id`, requests in a short time with the same `request_id` would get the same response. But a cached response will be expired if any its affected db resources are last changed by other requests.

```python
from flask_idempotent2 import Idempotent

idempotent = Idempotent(app, redis_client, DBSession) # DBSession: SQLAlchemy Session

@app.route('/api', methods=['PUT'])
@idempotent.cache(15)  # Cache result for 15s
def api():
    pass
```

Requests Lock
-------------

```python
@app.route('/api', methods=['PUT'])
@idempotent.lock(3)   # Lock concurrency requests for 3s
def api():
    pass
```

Installation
-------------

```
pip install flask_idempotent2
```

Cache Details
-------------

### Here's how it works, in brief:

1. Responses are cached into redis (with expiration).
2. Return the response in redis if it exists.
3. Clear the cache if any related db changes are made.

### And here's the detailed version:

1. Get `request_id` by preconfigured `key_func`.

2. Get cached response from redis by `request_id`.

3. Return the cached response if it exists and its related db resources are still not changed.

4. Otherwise call `view_function` and cache its response into redis with `request_id` as key and preconfigured `timeout` as  an expiration. Then return this response.

5. All db changes during the `view_function` call will be recorded in redis, in format of `resource-instance` to `request-id`.A cached response is valid only if its affected resource instances are all last affected by the same `request-id`. If any other requests affects these db resources, the `request-id` will be reset, thus the cached response expires.

   | Key                                      | Value                                    |
   | ---------------------------------------- | -----------------------------------------|
   | app-name:api-name:request-id           | serialized-response, affected-resource-instances |
   | affected-resource:id *e.g.* `"User:1"` | request-id                               |
   | affected-resource:id...                | ...                                      |


### How requests are distinguished?

Requests are distinguished by preconfigured `keyfunc`, which is a function with no arguments and should return the `request_id`.

```
from flask_idempotent2 import Idempotent, gen_keyfunc

keyfunc = gen_keyfunc(path=True, methods=True, query_string=True, data=True)
idempotent = Idempotent(app, redis_client, DBSession, keyfunc)
```

### Unittests problem with flask.g

`flask.g` can't be accessed outside flask request context, so I suggest you to use a threading local object instead:

```
import threading
# If your service is gevent based (one request one gevent thread).
# 1. Use gevent threading local instead.
# 2. Or just make sure builtin threading is patched by gevent.
g_ = threading.local()
idempotent = Idempotent(app, redis_client, DBSession, g_=threading.local())
```

License
-------

BSD.
