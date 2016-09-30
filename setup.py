# -*- coding: utf-8 -*-

'''
Flask-Idempotent2
-----------------

Installation
`````````````

.. code:: bash

    $ pip install flask-idempotent2

Links
`````

* `github <http://github.com/hit9/flask-idempotent2/>`_
* `flask <http://flask.pocoo.org/>`_
'''

import re
import ast
from setuptools import setup

_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('flask_idempotent2.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))


setup(
    name='flask-idempotent2',
    version=version,
    url='http://github.com/hit9/flask-docjson',
    license='BSD',
    author='Chao Wang',
    author_email='hit9@icloud.com',
    description='Redis based idempotent support for sqlalchemy based flask'
                'applications.',
    long_description=__doc__,
    py_modules=['flask_idempotent2'],
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=open('requirements.txt').readlines(),
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
