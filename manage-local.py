#!/usr/bin/env python
from migrate.versioning.shell import main

if __name__ == '__main__':
    main(url='mysql://wazzuup:serval@127.0.0.1/WZP', debug='False', repository='migraterepo')
