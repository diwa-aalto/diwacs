from sqlalchemy import *
from migrate import *
meta = MetaData()

table = Table('event', meta)
title_new = Column('title',String(40),nullable=True)
title_old = Column('title',String(40),nullable=False)
desc_new = Column('desc',String(500),nullable=True)
desc_old = Column('desc',String(500),nullable=False)
def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    meta.bind = migrate_engine
    title_old.drop(table)
    title_new.create(table)
    desc_old.drop(table)
    desc_new.create(table)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    meta.bind = migrate_engine
    title_new.drop(table)
    title_old.create(table)
    desc_new.drop(table)
    desc_old.create(table)
