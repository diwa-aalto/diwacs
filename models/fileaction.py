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


class Action(BASE):
    """
    A class representation of a action. A file action uses this to describe
    the action.

    Field:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the action, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Name of the action (Max 50 characters).

    :param name: Name of the action.
    :type name: :py:class:`String`
    """
    __tablename__ = 'action'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True
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

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


class File(BASE):
    """
    A class representation of a file.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the file, used as primary key in database table.

        * :py:attr:`path`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Path of the file on DiWa (max 255 chars).

        * :py:attr:`project_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the project this file belongs to.

        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`)\
        - Project this file belongs to.

    """
    __tablename__ = 'file'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True,
        autoincrement=True,
        default=text('COALESCE(MAX(file.id),0)+1 FROM file')
    )

    path = Column(
        name='path',
        type_=String(
            length=255,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=False
    )

    project_id = Column(
        name='project_id',
        type_=INTEGER,
        args=(ForeignKey('project.id')),
        nullable=True
    )

    project = relationship(
        argument='Project',
        backref=backref('files', order_by=id)
    )

    def __repr__(self):
        return self.path


class FileAction(BASE):
    """
    A class representation of a file action.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the FileAction, used as primary key in the database table.

        * :py:attr:`file_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlaclhemy.types.INTEGER)`)\
        - ID of the file this FileAction affects.

        * :py:attr:`file` (:py:class:`sqlalchemy.orm.relationship)`)\
        - The file this FileAction affects.

        * :py:attr:`action_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the action affecting the file.

        * :py:attr:`action` (:py:class:`sqlalchemy.orm.relationship)`)\
        - Action affecting the file.

        * :py:attr:`action_time`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.DATETIME)`)\
        - Time the action took place on.

        * :py:attr:`user_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the user performing the action.

        * :py:attr:`user` (:py:class:`sqlalchemy.orm.relationship`)\
        - User peforming the action.

        * :py:attr:`computer_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the computer user performed the action on.

        * :py:attr:`computer` (:py:class:`sqlalchemy.orm.relationship`)\
        - Computer user performed the action on.

        * :py:attr:`session_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the session user performed the action in.

        * :py:attr:`session` (:py:class:`sqlalchemy.orm.relationship`)\
        - Session user performed the action in.

    :param fileobject: The file which is subjected to the action.
    :type fileobject: :py:class:`models.File`

    :param action: The action which is applied to the file.
    :type action: :py:class:`models.Action`

    :param session: The session in which the FileAction took place on.
    :type session: :py:class:`models.Session`

    :param computer: The computer from which the user performed the action.
    :type computer: :py:class:`models.Computer`

    :param user: The user performing the action.
    :type user: :py:class:`models.User`

    """
    __tablename__ = 'fileaction'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True,
        autoincrement=True,
        default=text('COALESCE(MAX(fileaction.id),0)+1 FROM fileaction')
    )

    file_id = Column(
        name='file_id',
        type_=INTEGER,
        args=(ForeignKey('file.id')),
        nullable=False
    )

    action_id = Column(
        name='action_id',
        type_=INTEGER,
        args=(ForeignKey('action.id')),
        nullable=False
    )

    action_time = Column(
        name='action_time',
        type_=DATETIME,
        default=func.now()
    )

    user_id = Column(
        name='user_id',
        type_=INTEGER,
        args=(ForeignKey('user.id')),
        nullable=True
    )

    computer_id = Column(
        name='computer_id',
        type_=INTEGER,
        args=(ForeignKey('computer.id')),
        nullable=True
    )

    session_id = Column(
        name='session_id',
        type_=INTEGER,
        args=(ForeignKey('session.id')),
        nullable=True
    )

    file = relationship(
        argument='File',
        backref=backref('actions', order_by=id)
    )

    action = relationship(
        argument='Action',
        backref=backref('actions', order_by=id)
    )

    user = relationship(
        argument='User',
        backref=backref('fileactions', order_by=id)
    )

    computer = relationship(
        argument='Computer',
        backref=backref('fileactions', order_by=id)
    )

    session = relationship(
        argument='Session',
        backref=backref('fileactions', order_by=id)
    )

    def __init__(self, fileobject, action, session=None, computer=None,
                 user=None):
        self.file = fileobject
        self.action = action
        self.user = user
        self.session = session
        self.computer = computer
