"""
Created on 31.6.2013

:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines and constructs the SQL alchemy Base class.

"""
# System imports.
import logging

# Third party imports.
from sqlalchemy import create_engine, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound


# Internal imports
import diwavars


# CONSTANT
ENGINE = None  # create_engine(DATABASE, echo=True)
LOGGER = None
ACTIONS = {
    1: 'Created', 2: 'Deleted', 3: 'Updated', 4: 'Renamed from something',
    5: 'Renamed to something', 6: 'Opened', 7: 'Closed'
}
REVERSE_ACTIONS = {ACTIONS[key]: key for key in ACTIONS}
Base = declarative_base()


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    logging.config.fileConfig('logging.conf')
    LOGGER = logging.getLogger('models')


def __set_logger_level(level):
    """
    Sets the logger level for controller logger.

    :param level: Level of logging.
    :type level: Integer

    """
    LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


def connect_to_database(expire=False):
    """
    Connect to the database and return a Session object.

    :param expire: Parameter passed to session maker as expire_on_commit.
    :type expire: Boolean

    :returns: Session.
    :rtype: :py:class:`sqlalchemy.orm.session.Session`

    """
    if ENGINE is None:
        LOGGER.exception('No engine!')
        return None
    session_function = sessionmaker(bind=ENGINE, expire_on_commit=expire)
    return session_function()


def create_all():
    """
    Create tables to the database.

    """
    if ENGINE is None:
        return
    try:
        database = connect_to_database()
        database.execute('SET foreign_key_checks = 0')
        database.execute('DROP table IF EXISTS action')
        database.execute('SET foreign_key_checks = 1')
        database.commit()
        Base.metadata.create_all(ENGINE)  # @UndefinedVariable
        for action_id in ACTIONS:
            query = 'INSERT INTO action VALUES({0}, \'{1}\')'
            database.execute(query.format(action_id, ACTIONS[action_id]))
        database.commit()
    except SQLAlchemyError as excp:
        log_msg = 'Exception on create_all call: {exception!s}'
        log_msg = log_msg.format(exception=excp)
        LOGGER.exception(log_msg)
    finally:
        if (database is not None) and hasattr(database, 'close'):
            database.close()
        database = None


def update_database():
    """
    Update the database connection engine.

    .. note::
        This only works when DB_STRING is completely defined by
        the log reader as otherwise the create_engine call would
        cause an exception.

    """
    global ENGINE
    if diwavars.DB_STRING:
        ENGINE = create_engine(diwavars.DB_STRING, echo=False)


class ItemAlreadyExistsException(Exception):
    """
    When the item already exists in the database, you need to use
    get method instead of constructor.

    """
    def __init__(self, message):
        msg = ('This item already exists, please use static method "get" '
               'to retrieve the instance instead of class constructor.')
        message = message + '\n' + msg
        Exception.__init__(self, message)


DEFAULT = 'COALESCE(MAX({0}.id),0)+1 FROM {0}'


class MethodMixin():
    """
    A base class for all our DiWa models.

    Defines some common methods / use cases of SQLAlchemy.

    """
    def __repr__(self):
        """
        Common way of representing models classes based on their id number.

        """
        id_ = getattr(self, 'id', -1)
        name = self.__class__.__name__
        return '<id={0}, item={1}>'.format(id_, name)

    def delete(self):
        """
        Delete an object of this class from the database.

        """
        database = None
        try:
            database = connect_to_database()
            database.delete(self)
            database.commit()
            return True
        except SQLAlchemyError as excp:
            log_msg = 'Exception in {class_name}.delete() : {exception!s}'
            log_msg = log_msg.format(class_name=self.__class__.__name__,
                                     exception=excp)
            LOGGER.exception(log_msg)
            return False
        finally:
            if (database is not None) and hasattr(database, 'close'):
                database.close()
            database = None

    @classmethod
    def delete_many(cls, instances):
        """Delete objects of this class from the database."""
        database = None
        try:
            database = connect_to_database()
            for instance in instances:
                database.delete(instance)
            database.commit()
            return True
        except SQLAlchemyError as excp:
            log_msg = 'Exception in {class_name}.delete() : {exception!s}'
            log_msg = log_msg.format(class_name=cls.__name__, exception=excp)
            LOGGER.exception(log_msg)
            return False
        finally:
            if (database is not None) and hasattr(database, 'close'):
                database.close()
            database = None

    _default_method_values = {'all': [], 'count': 0, 'delete': [],
                              'exists': False, 'first': None, 'last': None,
                              'one': None}

    @classmethod
    def get(cls, method, *filters):
        """
        :param method:
            Valid values are:
                * all - This returns a list of matching objects.
                * count - This returns an integer which represents the count\
                of matching objects.
                * delete - This deletes all the matching objects from the\
                database.
                * exists - This returns boolean informing weather the an\
                object match was found from the database.
                * first - This returns the first matching object.
                * last - This returns the last matching object.
                * one - This returns the object if it exists and raises an\
                exception if it doesn't or if there's more than one instance\
                of the desired object.
        :type method: String

        Additional parameters may be specified to filter results.

        """
        if method in MethodMixin._default_method_values:
            result = MethodMixin._default_method_values[method]
        else:
            raise AttributeError('Method needs to be valid!')
        # Query.
        database = None
        try:
            database = connect_to_database()
            query = database.query(cls)
            query = query.filter(*filters)
            if method == 'last':
                result = query.order_by(desc(getattr(cls, 'id'))).first()
            else:
                result = getattr(query, method)()
            if method == 'exists':
                # The result is a query still...
                result = database.query(result).scalar()
        except (NoResultFound, MultipleResultsFound):
            raise
        except SQLAlchemyError as excp:
            log_msg = 'Exception in {class_name}.get() : {exception!s}'
            log_msg = log_msg.format(class_name=cls.__name__, exception=excp)
            LOGGER.exception(log_msg)
        finally:
            if database and hasattr(database, 'close'):
                database.close()
            database = None
        return result

    @classmethod
    def get_by_id(cls, id_=1):
        """
        Gets the instance of model by ID.

        :param id_: ID of the desired model.
        :type id_: Integer

        """
        return cls.get('one', cls.id == id_)

    @classmethod
    def id_ordering(cls, instance):
        """Key function for id ordering."""
        if not isinstance(instance, cls):
            msg = 'Invalid instance for type: {0}'
            raise ValueError(msg.format(cls.__name__))
        return instance.id

    def update(self):
        """
        Posts updates to this object into the database.

        :returns: Success value.
        :rtype: Boolean

        """
        database = None
        try:
            database = connect_to_database()
            database.add(self)
            database.commit()
            return True
        except SQLAlchemyError as excp:
            log_msg = 'Exception in {0}.update() : {1!s}'
            log_msg = log_msg.format(self.__class__.__name__, excp)
            LOGGER.exception(log_msg)
            return False
        finally:
            if database and hasattr(database, 'close'):
                database.close()
            database = None

    @classmethod
    def update_many(cls, instances):
        """
        Posts updates to these objects into the database.

        :returns: Success value.
        :rtype: Boolean

        """
        database = None
        try:
            database = connect_to_database()
            database.add_all(instances)
            database.commit()
            return True
        except SQLAlchemyError as excp:
            log_msg = 'Exception in {0}.update() : {1!s}'
            log_msg = log_msg.format(cls.__name__, excp)
            LOGGER.exception(log_msg)
            return False
        finally:
            if database and hasattr(database, 'close'):
                database.close()
            database = None
