"""
Created on 23.5.2012


:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines the project class and its interface to the database.

"""
# Third party imports.
from sqlalchemy import (Column, text, DATETIME, INTEGER, String, ForeignKey)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref

# Internal imports.
import models.common
BASE = models.common.BASE


def _logger():
    return models.common.LOGGER


class Event(BASE):
    """
    A class representation of Event. A simple note with timestamp during a
    session.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the event, used as primary key in database table.

        * :py:attr:`title`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Title of the event (Max 40 characters).

        * :py:attr:`desc`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - More in-depth description of the event (Max 500 characters).

        * :py:attr:`time`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.DATETIME)`)\
        - Time the event took place.

        * :py:attr:`session_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the session this event belongs to.

        * :py:attr:`session` (:py:class:`sqlalchemy.orm.relationship`)\
        - Session this event belongs to.

    """
    __tablename__ = 'event'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True,
        autoincrement=True,
        default=text('COALESCE(MAX(event.id),0)+1 FROM event')
    )

    title = Column(
        name='title',
        type_=String(
            length=40,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=False
    )

    desc = Column(
        name='desc',
        type_=String(
            length=500,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=True
    )

    time = Column(
        name='time',
        type_=DATETIME,
        default=func.now()
    )

    session_id = Column(
        name='session_id',
        type_=INTEGER,
        args=(ForeignKey('session.id'))
    )

    session = relationship(
        argument='Session',
        backref=backref('events', order_by=id)
    )
