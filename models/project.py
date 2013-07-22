"""
Created on 23.5.2012


:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines the project class and its interface to the database.

"""
# Third party imports.
from sqlalchemy import (Column, text, INTEGER, String, ForeignKey)
from sqlalchemy.orm import relationship, backref

# Internal imports.
import models.common
import models.user


def _logger():
    return models.common.LOGGER


class Project(models.common.BASE):
    """
    A class representation of a project.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of project, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Name of the project (Max 50 characters).

        * :py:attr:`company_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the company that owns the project.

        * :py:attr:`company` (:py:class:`sqlalchemy.orm.relationship`)\
        - The company that owns the project.

        * :py:attr:`dir`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Directory path for the project files (Max 255 characters).

        * :py:attr:`password`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Password for the project (Max 40 characters).

        * :py:attr:`members` (:py:class:`sqlalchemy.orm.relationship`)\
        - The users that work on the project.

    :param name: Name of the project.
    :type name: :py:class:`String`

    :param company: The owner of the project.
    :type company: :py:class:`models.Company`

    :TODO: document `directory` and `password` parameters.

    """
    __tablename__ = 'project'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True,
        nullable=False,
        autoincrement=True,
        default=text('COALESCE(MAX(project.id),0)+1 FROM project')
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

    company_id = Column(
        name='company_id',
        type_=INTEGER,
        args=(ForeignKey('company.id')),
        nullable=False
    )

    dir = Column(
        name='dir',
        type_=String(
            length=255,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=True
    )

    password = Column(
        name='password',
        type_=String(
            length=40,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=True
    )

    company = relationship(
        argument='Company',
        backref=backref(name='projects', order_by=id),
        uselist=False
    )

    members = relationship(
        argument='User',
        secondary=models.user.ProjectMembers,
        backref=backref('projects')
    )

    def __init__(self, name, directory, company, password):
        self.name = name
        self.company = company
        self.dir = directory
        self.password = password
        database = models.common.connect_to_database()
        database.add(self)
        database.commit()
        database.close()
