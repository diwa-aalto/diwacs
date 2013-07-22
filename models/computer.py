"""
Created on 23.5.2012


:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines the company class and its interface to the database.

"""
# Third party imports.
from sqlalchemy import (Column, text, INTEGER, SMALLINT, DATETIME, String,
                        ForeignKey)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.exc import SQLAlchemyError

# Internal imports.
import models.common


def _logger():
    return models.common.LOGGER


class Computer(models.common.BASE):
    """
    A class representation of a computer.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of computer, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Name of the computer.

        * :py:attr:`ip`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.dialects.INTEGER)`)\
        - Internet Protocol address of the computer (Defined as unsigned).

        * :py:attr:`mac`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`\
        - Media Access Control address of the computer.

        * :py:attr:`time`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.DATETIME)`)\
        - Time of the last network activity from the computer.

        * :py:attr:`screens`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.SMALLINT)`)\
        - Number of screens on the computer.

        * :py:attr:`responsive`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.SMALLINT)`)\
        - The responsive value of the computer.

        * :py:attr:`user_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the user currently using the computer.

        * :py:attr:`user` (:py:class:`sqlalchemy.orm.relationship`)\
        - The current user.

        * :py:attr:`wos_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - **WOS** ID.

    """
    __tablename__ = 'computer'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        default=text('COALESCE(MAX(computer.id),0)+1 FROM computer')
    )

    name = Column(
        name='name',
        type_=String(
            length=50,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=False
    )

    ip = Column(
        name='ip',
        type_=INTEGER(unsigned=True),
        nullable=False
    )

    mac = Column(
        name='mac',
        type_=String(
            length=12,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=True
    )

    time = Column(
        name='time',
        type_=DATETIME,
        nullable=True
    )

    screens = Column(
        name='screens',
        type_=SMALLINT,
        nullable=True,
        default=0
    )

    responsive = Column(
        name='responsive',
        type_=SMALLINT,
        nullable=True
    )

    wos_id = Column(
        name='wos_id',
        type_=INTEGER,
        nullable=True
    )

    user_id = Column(
        name='user_id',
        type_=INTEGER,
        args=(ForeignKey('user.id'))
    )

    user = relationship(
        argument='User',
        backref=backref('computers', order_by=id)
    )

    def __init__(self, name, ip, mac, screens, responsive, wos_id):
        self.name = name
        self.ip = ip
        self.mac = mac
        self.screens = screens
        self.responsive = responsive
        self.wos_id = wos_id
        database = models.common.connect_to_database()
        database.add(self)
        database.commit()
        database.close()

    @staticmethod
    def get_most_recent_by_mac(mac_address):
        """
        Retrieve a computer by it's hardware identifier.

        """
        computers = Computer.get(Computer.mac == mac_address)

        # If we got no computers.
        if not computers:
            return None
        # If we got only one, just return it.
        if len(computers) == 1:
            return computers[0]

        # Filter out computers without time stamp.
        temp = [computer for computer in computers if computer.time]

        # If there were none with a timestamp.
        if not temp:
            # Return last (id wise).
            id_sorter = lambda computer: computer.id
            return sorted(computers, key=id_sorter).pop()

        # If there was only one computer with a timestamp, use that one.
        if len(temp) == 1:
            return temp[0]

        # Return the most recent timestamp wise.
        computers = temp
        time_sorter = lambda computer: computer.time
        return sorted(computers, key=time_sorter).pop()

    @staticmethod
    def get(*filters):
        """
        Retrieve computers using filters.

        """
        database = None
        result = None
        try:
            database = models.common.connect_to_database()
            query = database.query(Computer)
            query = query.filter(*filters)
            result = query.all()
        except SQLAlchemyError, excp:
            log_msg = ('Exception at getting computer: {exception!s}')
            log_msg = log_msg.format(exception=excp)
            _logger().exception(log_msg)
        if database:
            database.close()
        return result

    def __str__(self):
        str_msg = '<{wos_id}: name:{computer_name} screens:{screens} {time}>'
        my_time = ('time: ' + self.time.isoformat()) if self.time else ''
        return str_msg.format(wos_id=self.wos_id,
                              computer_name=self.name,
                              screens=self.screens,
                              time=my_time)

    def __repr__(self):
        return self.__str__()
