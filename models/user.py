"""
Created on 23.5.2012


:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines the project class and its interface to the database.

"""
# Third party imports.
from sqlalchemy import (Column, text, INTEGER, String, ForeignKey, Table)
from sqlalchemy.orm import relationship, backref

# Internal imports.
import models.common


def _logger():
    return models.common.LOGGER


class User(models.common.BASE):
    """
    A class representation of a user.

    :note: Currently not used anywhere.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the user, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Name of the user (Max 50 characters).

        * :py:attr:`email`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Email address of the user (Max 100 characters).

        * :py:attr:`title`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Title of the user in the company (Max 50 characters).

        * :py:attr:`department`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Department of the user in the company (Max 100 characters).

        * :py:attr:`company_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - Company id of the employing company.

        * :py:attr:`company` (:py:class:`sqlalchemy.orm.relationship`)\
        - Company relationship.

    :param name: Name of the user.
    :type name: :py:class:`String`

    :param company: The employer.
    :type company: :py:class:`models.Company`

    """
    __tablename__ = 'user'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True,
        nullable=False,
        autoincrement=True,
        default=text('COALESCE(MAX(user.id),0)+1 FROM user')
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

    email = Column(
        name='email',
        type_=String(
            length=100,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=True
    )

    title = Column(
        name='title',
        type_=String(
            length=50,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=True
    )

    department = Column(
        name='department',
        type_=String(
            length=100,
            collation='utf8_general_ci',
            convert_unicode=True
        ),
        nullable=True
    )

    company_id = Column(
        name='company_id',
        type_=INTEGER,
        args=(ForeignKey('company.id')),
        nullable=False
    )

    company = relationship(
        argument='Company',
        backref=backref('employees', order_by=id)
    )

    def __init__(self, name, company, email=None, title=None, department=None):
        self.name = name
        self.email = email
        self.title = title
        self.department = department
        self.company = company
        database = models.common.connect_to_database()
        database.add(self)
        database.commit()
        database.close()


"""
A variable to hold the connection between users and projects (a table).

:py:data:`ProjectMembers` (:py:class:`sqlalchemy.schema.Table`)

This comment is not included in the autodoc because it's over the
ProjectMember definition. However if it was under it, the autodoc
would include the whole line to the documentation before the actual
docstring... Which is horribly ugly with autodoc formatting.

"""
ProjectMembers = Table(
    name='projectmembers',
    metadata=models.common.BASE.metadata,
    args=(
        Column(
            name='Project',
            type_=INTEGER,
            args=(ForeignKey('project.id'))
        ),
        Column(
            name='User',
            type_=INTEGER,
            args=(ForeignKey('user.id'))
        )
    )
)
