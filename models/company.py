"""
Created on 23.5.2012


:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines the company class and its interface to the database.

"""
# Third party imports.
from sqlalchemy import (Column, text, INTEGER, String)
from sqlalchemy.exc import SQLAlchemyError

# Internal imports.
import models.common
import models.Project


def _logger():
    return models.common.LOGGER


class Company(models.common.BASE):
    """
    A class representation of a company.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.INTEGER)`)\
        - ID of the company, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Name of the company (Max 50 characters).

    :param name: The name of the company.
    :type name: :py:class:`String`

    """
    __tablename__ = 'company'

    id = Column(
        name='id',
        type_=INTEGER,
        primary_key=True,
        nullable=False,
        autoincrement=True,
        default=text('COALESCE(MAX(company.id),0)+1 FROM company')
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

    def __init__(self, name):
        """
        Note, you should call this constructor only inside a
        try ... except ... block.

        """
        self.name = name
        database = models.common.connect_to_database()
        database.add(self)
        database.commit()
        database.close()

    def __str__(self):
        return self.name

    @staticmethod
    def get_by_id(company_id=1):
        """
        Gets the company by ID.

        :param company_id: ID of the desired company.
        :type company_id: Integer

        """
        database = None
        result = None
        try:
            database = models.common.connect_to_database()
            query = database.query(Company).filter(Company.id == company_id)
            result = query.one()
        except SQLAlchemyError, excp:
            log_msg = 'No company found with ID = {company_id}: {exception!s}'
            log_msg = log_msg.format(company_id=company_id, exception=excp)
            _logger().exception(log_msg)
        if database:
            database.close()
        return result

    def get_projects(self, *filters):
        """
        Get all the projects of this company.

        You can optionally specify any amount of filters.

        """
        database = None
        result = []
        try:
            database = models.common.connect_to_database()
            query = database.query(models.Project)
            query = query.filter(models.Project.company_id == self.id)
            query = query.filter(*filters)
            result = query.all()
        except SQLAlchemyError, excp:
            log_msg = ('Exception when searching for project of '
                       'company {company_name}: {exception!s}')
            log_msg = log_msg.format(company_name=self.name, exception=excp)
            _logger().exception(log_msg)
        if database:
            database.close()
        return result
