flask-idempotent2
=================

Redis based idempotent support for sqlalchemy based flask applications.

```python
from flask_idempotent2 import Idempotent

idempotent = Idempotent(app, redis_client, Session)

@app.route('/api', methods=['PUT'])
@idempotent
def api():
    pass
```

Installation
-------------

```
pip install flask_idempotent2
```

Usage
-----

* Register view function via decorator:

   ```python
   @app.route('/api1')
   @idempotent
   def api1():
       pass

   @app.route('/api2')
   @idempotent.parametrize(timeout=60)
   def api2():
       pass
   ```

* Automatically discover view functions to register:

   ```
   idempotent.auto_register()
   ```

License
-------

BSD.
