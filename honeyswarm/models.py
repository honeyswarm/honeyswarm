
from flask_mongoengine import Document
from mongoengine import ReferenceField, BooleanField, StringField, IntField, \
    DictField, DateTimeField, ListField
from datetime import datetime
from flask_security import UserMixin, RoleMixin


class AuthKey(Document):
    meta = {
        'db_alias': 'hpfeeds_db'
    }
    identifier = StringField()
    secret = StringField()
    publish = ListField(default=[])
    subscribe = ListField(default=[])


class Config(Document):
    honeyswarm_host = StringField()
    honeyswarm_api = StringField()
    broker_host = StringField()


class HoneypotEvents(Document):

    meta = {
        'db_alias': 'hpfeeds_db'
    }
    date = DateTimeField(default=datetime.utcnow())
    service = StringField()
    port = IntField()
    honeypot_type = StringField()
    channel = StringField()
    payload = DictField()
    honeypot_instance_id = StringField()
    source_ip = StringField()


class Frame(Document):
    name = StringField(unique=True)
    description = StringField()
    supported_os = ListField()
    frame_state_path = StringField()
    pillar = ListField()


class Honeypot(Document):
    name = StringField(unique=True)
    honeypot_state_file = StringField()
    honey_type = StringField()
    description = StringField()
    pillar = ListField()
    channels = ListField()


class HoneypotInstance(Document):
    honeypot = ReferenceField(Honeypot)
    hpfeeds = ReferenceField(AuthKey)
    pillar = DictField(default={})


class Hive(Document):
    name = StringField(unique=True)
    registered = BooleanField(default=False)
    salt_alive = BooleanField()
    created_at = DateTimeField(default=datetime.utcnow())
    last_seen = DateTimeField()
    grains = DictField(default={'osfullname': 'Not Polled', 'ipv4': []})
    honeypots = ListField(ReferenceField(HoneypotInstance), default=[])
    frame = ReferenceField(Frame)
    event_count = IntField(default=0)


class PepperJobs(Document):
    job_id = StringField()
    job_short = StringField()
    job_description = StringField()
    created_at = DateTimeField(default=datetime.utcnow())
    last_check = DateTimeField()
    complete = BooleanField(default=False)
    completed_at = DateTimeField()
    job_response = StringField()
    hive = ReferenceField(Hive)


class Role(Document, RoleMixin):
    name = StringField(max_length=80, unique=True)
    description = StringField(max_length=255)


class User(Document, UserMixin):
    email = StringField(unique=True)
    password = StringField()
    name = StringField(unique=True)
    active = BooleanField(default=False)
    fs_uniquifier = StringField(max_length=255)
    confirmed_at = DateTimeField()
    roles = ListField(ReferenceField(Role), default=[])
