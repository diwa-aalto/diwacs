"""
Created on 23.5.2012


:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines the project class and its interface to the database.

"""
# System imports.
import datetime

# Third party imports.
from sqlalchemy import (Column, text, DATETIME, INTEGER, String, ForeignKey,
                        Table)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref

# Internal imports.
import models.common
BASE = models.common.BASE


def _logger():
    return models.common.LOGGER


SessionParticipants = Table(
    name='sessionparticipants',
    metadata=BASE.metadata,
    args=(
        Column(
            name='Session',
            type_=INTEGER,
            args=(ForeignKey('session.id'))
        ),
        Column(
            name='User',
            type_=INTEGER,
            args=(ForeignKey('user.id'))
        )
    )
)

SessionComputers = Table(
    name='sessioncomputers',
    metadata=BASE.metadata,
    args=(
        Column(
            name='Session',
            type_=INTEGER,
            args=(ForeignKey('session.id'))
        ),
        Column(
            name='Computer',
            type_=INTEGER,
            args=(ForeignKey('computer.id'))
        )
    )
)


class Session(BASE):
    """
    A class representation of a session.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of session, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Name of session (Max 50 characters).

        * :py:attr:`project_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the project the session belongs to.

        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`)\
        - The project the session belongs to.

        * :py:attr:`starttime`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.DATETIME)`)\
        - Time the session began, defaults to `now()`.

        * :py:attr:`endtime`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.DATETIME)`)\
        - The time session ended.

        * :py:attr:`previous_session_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the previous session.

        * :py:attr:`previous_session`\
        (:py:class:`sqlalchemy.orm.relationship`) - The previous session.

        * :py:attr:`participants` (:py:class:`sqlalchemy.orm.relationship`)\
        - Users that belong to this session.

        * :py:attr:`computers` (:py:class:`sqlalchemy.orm.relationship`)\
        - Computers that belong to this session.

    :param project: The project for the session.
    :type project: :py:class:`models.Project`

    """
    __tablename__ = 'session'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True,
        nullable=False,
        autoincrement=True,
        default=text('COALESCE(MAX(session.id),0)+1 FROM session')
    )

    name = Column(
        name='name',
        type_=String(
            length=50,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=True
    )

    project_id = Column(
        name='project_id',
        type_=INTEGER,
        args=(ForeignKey('project.id')),
        nullable=False
    )

    starttime = Column(
        name='starttime',
        type_=DATETIME,
        default=func.now(),
        nullable=True
    )

    endtime = Column(
        name='endtime',
        type_=DATETIME,
        nullable=True
    )

    previous_session_id = Column(
        name='previous_session_id',
        type_=INTEGER,
        args=(ForeignKey('session.id')),
        nullable=True
    )

    project = relationship(
        argument='Project',
        backref=backref('sessions', order_by=id)
    )

    previous_session = relationship(
        argument='Session',
        uselist=False,
        remote_side=[id]
    )

    participants = relationship(
        argument='User',
        secondary=SessionParticipants,
        backref=backref('sessions')
    )

    computers = relationship(
        argument='Computer',
        secondary=SessionComputers,
        backref=backref('sessions')
    )

    def __init__(self, project):
        self.project = project
        self.users = []
        self.endtime = None
        self.last_checked = None

    def Start(self):
        """
        Start a session.
        Set the :py:attr:`last_checked` field to current DateTime.

        """
        self.last_checked = datetime.datetime.now()

    def GetLastChecked(self):
        """
        Fetch :py:attr:`last_checked` field.

        :returns: :py:attr:`last_checked` field (None before\
                  :py:meth:`models.Session.start` is called).
        :rtype: :py:class:`datetime.datetime` or :py:const:`None`

        """
        return self.last_checked

    def AddUser(self, user):
        """
        Add users to a session.

        :param user: User to be added into the session.
        :type user: :py:class:`models.User`

        """
        self.users.append(user)
