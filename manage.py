#!/usr/bin/env python
from migrate.versioning.shell import main


USERNAME = 'USERNAME'
PASSWORD = 'PASSWORD'
HOSTNAME = '192.168.1.10'
DATABASE = 'DATABASENAME'
PROTOCOL = 'mysql'


if __name__ == '__main__':
    con_url = (PROTOCOL + '://' + USERNAME + ':' + PASSWORD + '@' +
               HOSTNAME + '/' + DATABASE)
    main(url=con_url, debug='False', repository='migraterepo')
