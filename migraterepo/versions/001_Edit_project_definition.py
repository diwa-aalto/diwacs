from sqlalchemy import *
from migrate import *
import models

meta = MetaData()

project_table = Table('project', meta)
pass_col = Column('password',String(40))
 
        
def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    meta.bind = migrate_engine
    pass_col.create(project_table)

def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    meta.bind = migrate_engine
    pass_col.drop(project_table)