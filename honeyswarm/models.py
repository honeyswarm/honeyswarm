from mongoengine import Document, ReferenceField, ObjectIdField, BooleanField, StringField, IntField, DictField, DateTimeField, ListField
from datetime import datetime
from flask_login import UserMixin


class Frame(Document):
    name = StringField()
    description = StringField()


class Honeypot(Document):
    name = StringField()
    honey_type = StringField()
    description = StringField()
    pillar = ListField()

class Hive(Document):
    name = StringField(unique=True)
    registered = BooleanField(default=False)
    salt_alive = BooleanField()
    created_at = DateTimeField(default=datetime.utcnow)
    last_seen = DateTimeField()
    grains = DictField(default={'osfullname': 'Not Polled', 'ipv4':[]})
    honeypots = ListField(ReferenceField(Honeypot), default=[])
    frame = ReferenceField(Frame)

class PepperJobs(Document):
    job_id = StringField()
    job_short = StringField()
    job_description = StringField()
    created_at = DateTimeField(default=datetime.utcnow)
    last_check = DateTimeField()
    complete = BooleanField(default=False)
    completed_at = DateTimeField()
    job_response = StringField()
    hive = ReferenceField(Hive)


class User(UserMixin, Document):
    email = StringField(unique=True)
    password = StringField()
    name = StringField()
