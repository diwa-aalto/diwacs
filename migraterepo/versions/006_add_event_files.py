from sqlalchemy import *
from migrate import *

meta = MetaData()

table = Table('eventfile', meta,
              Column('id',Integer, primary_key=True),
    Column('event_id',Integer, ForeignKey('event.id')),
    Column('filepath',String(600),nullable=False),
    Column('filename',String(255),nullable=True),
    Column('extension',String(255),nullable=True))

def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    meta.bind = migrate_engine
    table.create()
    


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    meta.bind = migrate_engine
    table.drop()
