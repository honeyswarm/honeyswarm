from mongoengine import Document, ReferenceField, ObjectIdField, BooleanField, StringField, IntField, DictField, DateTimeField, ListField
from datetime import datetime
from flask_login import UserMixin

class User(UserMixin, Document):
    email = StringField(unique=True)
    password = StringField()
    name = StringField()

class Honeypot(Document):
    honey_type = StringField()
    description = StringField()

class Hive(Document):
    name = StringField(unique=True)
    registered = BooleanField(default=False)
    salt_alive = BooleanField()
    created_at = DateTimeField(default=datetime.utcnow)
    last_seen = DateTimeField()
    ip_address = StringField()
    hostname = StringField()
    honeypots = ListField(ReferenceField(Honeypot), default=[])


class PepperJobs(Document):
    job_id = StringField()
    job_short = StringField()
    job_description = StringField()
    created_at = DateTimeField(default=datetime.utcnow)
    complete = BooleanField(default=False)
    completed_at = StringField()
    job_response = DictField()
    