#!/usr/bin/env python
from migrate.versioning.shell import main


USERNAME = 'USERNAME'
PASSWORD = 'PASSWORD'
DATABASE = 'DATABASENAME'
PROTOCOL = 'mysql'


if __name__ == '__main__':
    con_url = (PROTOCOL + '://' + USERNAME + ':' + PASSWORD + '@127.0.0.1/' +
               DATABASE)
    main(url=con_url, debug='False', repository='migraterepo')
