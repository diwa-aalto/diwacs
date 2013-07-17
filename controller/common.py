"""
Created on 28.6.2013

:author: neriksso

"""
# Critical imports.
import sys
import diwavars


if diwavars.CURRENTLY_RUNNING:
    sys.stdout = open(r'data\controller_stdout.log', 'w')
    sys.stderr = open(r'data\controller_stderr.log', 'w')

# System imports.
import logging

# Third party imports.
import sqlalchemy

# Own imports.
from models import Action, Base, File, Project

LOGGER = None


def __init_logger():
    """
    Used to initialize the logger, when running from diwacs.py

    """
    global LOGGER
    logging.config.fileConfig('logging.conf')
    LOGGER = logging.getLogger('controller')


def __set_logger_level(level):
    """
    Sets the logger level for controller logger.

    :param level: Level of logging.
    :type level: Integer

    """
    LOGGER.setLevel(level)


diwavars.add_logger_initializer(__init_logger)
diwavars.add_logger_level_setter(__set_logger_level)


ENGINE = None  # create_engine(DATABASE, echo=True)
NODE_NAME = ''
NODE_SCREENS = 0
ACTIONS = {
                       1: 'Created',
                       2: 'Deleted',
                       3: 'Updated',
                       4: 'Renamed from something',
                       5: 'Renamed to something',
                       6: 'Opened',
                       7: 'Closed',
            }


def get_action_id_by_name(action_name):
    """ Get the static ID of action name. """
    for temp_id, temp_name in ACTIONS:
        if temp_name == action_name:
            return temp_id
    return 0


def update_database():
    """
    Update the database connection engine.

    .. note::
        This only works when DB_STRING is completely defined by
        the log reader.

    """
    global ENGINE
    if diwavars.DB_STRING:
        ENGINE = sqlalchemy.create_engine(diwavars.DB_STRING, echo=False)


def set_node_name(name):
    """
    Set the stored node name for own swnp node as global.

    :warning: This should be removed in the future as globals are bad.

    """
    global NODE_NAME
    NODE_NAME = name


def set_node_screens(screens):
    """
    Set the stored node screens settings for own swnp node as global.

    :warning: This should be removed in the future as globals are bad.

    """
    global NODE_SCREENS
    NODE_SCREENS = screens


def create_all():
    """
    Create tables to the database.

    """
    if not ENGINE:
        return
    try:
        database = connect_to_database()
        database.execute('SET foreign_key_checks = 0')
        database.execute('DROP table IF EXISTS Action')
        database.execute('SET foreign_key_checks = 1')
        database.commit()
        Base.metadata.create_all(ENGINE)  # @UndefinedVariable
        for xy_tuple in ACTIONS.items():
            database.add(Action(xy_tuple[1]))
        database.commit()
        database.close()
    except sqlalchemy.exc.SQLAlchemyError as excp:
        LOGGER.exception('create_all Exception: %s', str(excp))


def connect_to_database(expire=False):
    """
    Connect to the database and return a Session object.

    :param expire: Parameter passed to session maker as expire_on_commit.
    :type expire: Boolean

    :returns: Session.
    :rtype: :py:class:`sqlalchemy.orm.session.Session`

    """
    if not ENGINE:
        LOGGER.exception('No engine!')
        return None
    initializer = sqlalchemy.orm.sessionmaker
    session_maker = initializer(bind=ENGINE, expire_on_commit=expire)
    return session_maker()


def delete_record(record_model, id_number):
    """
    Delete a record from database

    :param record_model: The model for which to delete a record.
    :type record_model: :func:`sqlalchemy.ext.declarative.declarative_base`

    :param id_number: Recond id.
    :type id_number: Integer

    :returns: Success.
    :rtype: Boolean

    """
    try:
        database = connect_to_database()
        record = database.query(record_model).filter_by(id=id_number).one()
        if record_model == Project:
            for session in record.sessions:
                LOGGER.debug(str(session))
                database.delete(session)
            db_command = 'Delete from activity where project_id=%d'
            database.execute(db_command % id_number)
        database.delete(record)
        database.commit()
        database.close()
        return True
    except sqlalchemy.exc.SQLAlchemyError:
        excp_string = 'Delete record exception model %s id %d.'
        LOGGER.exception(excp_string, record_model, id_number)
        return False


def get_or_create(database, model, **kwargs):
    """
    Fetches or creates a instance.

    :param database: a related database.
    :type database: :class:`sqlalchemy.orm.session.Session`

    :param model: The model of which an instance is wanted.
    :type model: :py:class:`sqlalchemy.ext.declarative.declarative_base`

    :returns: An object of the desired model.

     """
    instance = database.query(model).filter_by(**kwargs)
    instance = instance.order_by(sqlalchemy.desc(model.id)).first()
    if instance:
        return instance
    if 'path' in kwargs and 'project_id' in kwargs:
        project = database.query(Project)
        project = project.filter(Project.id == kwargs['project_id']).one()
        instance = File(path=kwargs['path'], project=project)
        database.add(instance)
        database.commit()
        return instance
    instance = model(**kwargs)
    return instance


def test_connection():
    """
    Test the connection to database.

    :returns: Does the software have access to the database at this time.
    :rtype: Boolean

    """
    try:
        database = connect_to_database()
        if not database:
            return False
        database.query(Project).count()
        database.close()
        return True
    except sqlalchemy.exc.SQLAlchemyError as excp:
        LOGGER.exception('EXCPT_TEST_CONNECTION: %s', str(excp))
        return False
