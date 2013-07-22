"""
Created on 23.5.2012


:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines the project class and its interface to the database.

"""
# Third party imports.
from sqlalchemy import (Column, text, INTEGER, BOOLEAN, ForeignKey)
from sqlalchemy.orm import relationship, backref

# Internal imports.
import models.common


def _logger():
    return models.common.LOGGER


class Activity(models.common.BASE):
    """
    A class representation of an activity.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of activity, used as primary key in database table.

        * :py:attr:`session_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the session activity belongs to.

        * :py:attr:`session` (:py:class:`sqlalchemy.orm.relationship`)\
        - Session relationship.

        * :py:attr:`project_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the project activity belongs to.

        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`)\
        - Project relationship.

        * :py:attr:`active`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.BOOLEAN)`)\
        - Boolean flag indicating that the project is active.

    :param project: Project activity belongs to.
    :type project: :py:class:`models.Project`

    :param session: Optional session activity belongs to.
    :type session: :py:class:`models.Session`

    """
    __tablename__ = 'activity'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True,
        nullable=False,
        autoincrement=True,
        default=text("COALESCE(MAX(activity.id),0)+1 FROM activity")
    )

    session_id = Column(
        name='session_id',
        type_=INTEGER,
        args=(ForeignKey('session.id')),
        nullable=True
    )

    project_id = Column(
        name='project_id',
        type_=INTEGER,
        args=(ForeignKey('project.id')),
        nullable=False
    )

    active = Column(
        name='active',
        type_=BOOLEAN,
        nullable=False,
        default=True
    )

    session = relationship(
        argument='Session',
        backref=backref('activities', order_by=id)
    )

    project = relationship(
        argument='Project',
        backref=backref('activities', order_by=id)
    )

    def __init__(self, project, session=None):
        self.project = project
        if session:
            self.session = session
        database = models.common.connect_to_database()
        database.add(self)
        database.commit()
        database.close()
