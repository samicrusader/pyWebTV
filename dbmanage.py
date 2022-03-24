#!/usr/bin/env python3
import argparse
import json
import redis
import sqlalchemy
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field
from redis.commands.json.path import Path
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text
from urllib.parse import quote

print('pyWebTV database management tool\nhttps://github.com/samicrusader/pyWebTV\nTAKE BACKUPS WHEN USING THIS TOOL!!!!\n')

Base = declarative_base()


class IPBlacklist(Base):
    __tablename__ = "ipblacklist"
    ip = sqlalchemy.Column(sqlalchemy.String(length=15),
                           unique=True, nullable=False, primary_key=True)
    expires = sqlalchemy.Column(
        sqlalchemy.DateTime, unique=False, nullable=True)
    reason = sqlalchemy.Column(sqlalchemy.String(
        length=100), unique=False, nullable=False)


class IPBlacklistSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = IPBlacklist
        include_fk = True


class Subscribers(Base):
    __tablename__ = "subscribers"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)

    # Required
    user = sqlalchemy.Column(sqlalchemy.Integer, unique=False, nullable=False)
    subscriber_category = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)
    registration_ip = sqlalchemy.Column(
        sqlalchemy.String(length=15), unique=False, nullable=False)
    cancelled = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    terminated = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)


class SubscribersSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Subscribers
        include_fk = True


class Terminals(Base):
    __tablename__ = "terminals"
    ssid = sqlalchemy.Column(sqlalchemy.String(
        length=16), primary_key=True, unique=True, nullable=False)
    subscriber = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)


class TerminalsSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Terminals
        include_fk = True


class Users(Base):
    __tablename__ = "users"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)

    # Required
    username = sqlalchemy.Column(sqlalchemy.String(
        length=12), unique=True, nullable=False)
    # FIXME: something something argon2id compatible settings
    password = sqlalchemy.Column(sqlalchemy.String(
        length=100), unique=False, nullable=False)
    timezone = sqlalchemy.Column(sqlalchemy.String(
        length=5), unique=False, nullable=False)
    is_subscriber = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    subscriber = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)
    registration_ip = sqlalchemy.Column(
        sqlalchemy.String(length=15), unique=False, nullable=False)

    # User information
    first_name = sqlalchemy.Column(sqlalchemy.String(
        length=18), unique=False, nullable=False)
    last_name = sqlalchemy.Column(sqlalchemy.String(
        length=18), unique=False, nullable=True)

    # Socialization
    irc_nick = sqlalchemy.Column(sqlalchemy.String(
        length=8), unique=True, nullable=False)
    has_mail_account = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    mail_username = sqlalchemy.Column(
        sqlalchemy.String(length=12), unique=True, nullable=True)
    mail_password = sqlalchemy.Column(
        sqlalchemy.String(length=256), unique=True, nullable=True)
    has_news_account = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    news_username = sqlalchemy.Column(
        sqlalchemy.String(length=12), unique=True, nullable=True)
    news_password = sqlalchemy.Column(
        sqlalchemy.String(length=256), unique=True, nullable=True)
    messenger_enabled = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    messenger_server = sqlalchemy.Column(
        sqlalchemy.String(length=253), unique=False, nullable=True)
    # FIXME: Escargot password WILL be encrypted. No clue what the output is.
    messenger_password = sqlalchemy.Column(
        sqlalchemy.String(length=20), unique=True, nullable=True)
    wtv_domain = sqlalchemy.Column(sqlalchemy.String(
        length=253), unique=False, nullable=True)

    # Settings
    setup_advanced_option = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    setup_play_bgm = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    setup_bgm_tempo = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)
    setup_bgm_volume = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)
    setup_background_color = sqlalchemy.Column(
        sqlalchemy.String(6), unique=False, nullable=False)
    setup_font_sizes = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)
    setup_in_stereo = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    setup_keyboard = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)
    setup_link_color = sqlalchemy.Column(
        sqlalchemy.String(6), unique=False, nullable=False)
    setup_play_songs = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    setup_play_sounds = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    setup_text_color = sqlalchemy.Column(
        sqlalchemy.String(6), unique=False, nullable=False)
    setup_visited_color = sqlalchemy.Column(
        sqlalchemy.String(6), unique=False, nullable=False)
    setup_japan_keyboard = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)
    setup_chat_access_level = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)
    setup_chat_on_nontrusted_page = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)
    setup_tv_chat_level = sqlalchemy.Column(
        sqlalchemy.Integer, unique=False, nullable=False)

    # Change in case of compromise
    force_chpasswd = sqlalchemy.Column(
        sqlalchemy.Boolean, unique=False, nullable=False)


class UsersSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Users
        include_fk = True


def redis_set(name: str, data: dict):
    """
    ReJSON.set wrapper
    """
    r.json().set(name, Path.rootPath(), data)
    return True


def redis_get(name: str):
    """
    ReJSON.get wrapper
    """
    return r.json().get(name)


def createdb():
    if engine.execute(text('select exists (select from information_schema.tables where table_schema = \'public\' and table_name = \'subscribers\' or table_name = \'terminals\' or table_name = \'users\');')).one()[0] == True:
        input('You are going to wipe your database!\nPlease Ctrl+C NOW if you do not want to do this.\nPress Enter to proceed...')
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='python3 dbmanage.py')

    parser.add_argument('--config', '-c', default='config.json',
                        help='Specify server configuration file.')
    parser.add_argument('--create', '-d', help='Create database.')
    parser.add_argument('--migrate', '-m', help='Migrate database.')

    args = parser.parse_args()

    if not args._get_args():
        parser.print_help()
        exit(1)

    try:
        config = json.load(open(args.config, 'r'))['db']
    except:
        print('Specify a config.')
        exit(1)

    sqlconfig = config['psql']
    redisconfig = config['redis']
    engine = sqlalchemy.create_engine(
        f"postgresql+pg8000://{sqlconfig['username']}:{quote(sqlconfig['password'])}@{sqlconfig['host']}:{sqlconfig['port']}/{sqlconfig['database']}")
    r = redis.Redis(
        host=redisconfig['host'], port=redisconfig['port'], db=redisconfig['db'])

    if args.create:
        createdb()
    elif args.migrate:
        # migratedb()
        pass
    else:
        parser.print_help()
        exit(1)
