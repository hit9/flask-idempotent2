# coding=utf8

from flask import Flask, _app_ctx_stack, request, jsonify
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from flask_idempotent2 import Idempotent
import redis


engine = create_engine('postgresql+psycopg2://localhost/testdb')
Session = scoped_session(sessionmaker(bind=engine,
                                      autocommit=False,
                                      expire_on_commit=False),
                         scopefunc=_app_ctx_stack.__ident_func__)
Base = declarative_base()
app = Flask(__name__)
idempotent = Idempotent(app, redis.StrictRedis(), Session)


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)


@app.teardown_request
def close_session(exc):
    Session.remove()


@app.route('/user', methods=['PUT'])
@idempotent.parametrize(timeout=10)
def test():
    data = request.get_json()
    session = Session()
    user = User(email=data['email'], password=data['password'])
    session.add(user)
    session.commit()
    return jsonify(email=user.email, password=user.password)


if __name__ == '__main__':
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.run()
