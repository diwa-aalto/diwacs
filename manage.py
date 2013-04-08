#!/usr/bin/env python
from migrate.versioning.shell import main

if __name__ == '__main__':
    main(url='mysql://wazzuup:serval@192.168.1.10/WZP', debug='False', repository='migraterepo')
