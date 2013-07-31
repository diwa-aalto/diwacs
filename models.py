"""
Created on 23.5.2012

.. moduleauthor:: neriksso
:author: neriksso
:note: Requires :py:mod:`sqlalchemy`
:synopsis:
    Defines and constructs the SQL alchemy Base class.

"""
# System imports.
from datetime import datetime
import logging

# Third party imports.
from sqlalchemy import (create_engine, ForeignKey, Column, Table, text,
                        Integer, SmallInteger, DateTime, Boolean, String,
                        desc)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.sql import func

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
        database.execute('DROP table IF EXISTS Action')
        database.execute('SET foreign_key_checks = 1')
        database.commit()
        Base.metadata.create_all(ENGINE)  # @UndefinedVariable
        for action_id in ACTIONS:
            database.add(Action(ACTIONS[action_id]))
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
    def __init__(self):
        msg = ('This item already exists, please use static method "get" '
               'to retrieve the instance instead of class constructor.')
        super(ItemAlreadyExistsException, self).__init__(self, msg)


DEFAULT = 'COALESCE(MAX({0}.id),0)+1 FROM {0}'


#:FIXME: This does not inherit well.
class MethodMixin():
    """
    A base class for all our DiWa models.

    """
    # ------------------------ ACTUAL INTERFACE --------------------------
    #def __repr__(self):
    #    id_ = getattr(self, 'id', -1)
    #    name = type(self).__name__
    #    return '<id={0}, item={1}>'.format(id_, name)

    @classmethod
    def delete(cls, instance):
        """Delete an object of this class from the database."""
        database = None
        try:
            database = connect_to_database()
            database.delete(instance)
            database.commit()
            return True
        except SQLAlchemyError, excp:
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
        except (NoResultFound, MultipleResultsFound):
            raise
        except SQLAlchemyError, excp:
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
        return cls.get('one', getattr(cls, 'id') == id_)

    @classmethod
    def id_ordering(cls, instance):
        """Key function for id ordering."""
        if not isinstance(instance, cls):
            msg = 'Invalid instance for type: {0}'
            raise ValueError(msg.format(cls.__name__))
        return instance.id

    @classmethod
    def update(cls, instance):
        """
        Posts updates to this object into the database.

        :returns: Success value.
        :rtype: Boolean

        """
        database = None
        try:
            database = connect_to_database()
            database.add(instance)
            database.commit()
            return True
        except SQLAlchemyError, excp:
            log_msg = 'Exception in {0}.update() : {1!s}'
            log_msg = log_msg.format(cls.__name__, excp)
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
        except SQLAlchemyError, excp:
            log_msg = 'Exception in {0}.update() : {1!s}'
            log_msg = log_msg.format(cls.__name__, excp)
            LOGGER.exception(log_msg)
            return False
        finally:
            if database and hasattr(database, 'close'):
                database.close()
            database = None


ProjectMembers = Table('projectmembers', Base.metadata,
    Column('Project', Integer, ForeignKey('project.id')),
    Column('User', Integer, ForeignKey('user.id'))
)

SessionParticipants = Table('sessionparticipants', Base.metadata,
    Column('Session', Integer, ForeignKey('session.id')),
    Column('User', Integer, ForeignKey('user.id'))
)

SessionComputers = Table('sessioncomputers', Base.metadata,
    Column('Session', Integer, ForeignKey('session.id')),
    Column('Computer', Integer, ForeignKey('computer.id'))
)


# -------------- CLASSES -------------------------------------------------
class Action(MethodMixin, Base):
    """
    A class representation of a action. A file action uses this to describe
    the action.

    Field:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(Integer)`)\
        - ID of the action, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(String)`)\
        - Name of the action (Max 50 characters).

    :param name: Name of the action.
    :type name: :py:class:`String`
    """
    __tablename__ = 'action'

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    name = Column(String(length=50, convert_unicode=True), nullable=True)

    def __init__(self, name):
        self.name = name
        if Action.get('exists', Action.name == name):
            raise ItemAlreadyExistsException('Action already exists!')
        Action.update(self)

    def __str__(self):
        return self.name


class Activity(MethodMixin, Base):
    """
    A class representation of an activity.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(Integer)`)\
        - ID of activity, used as primary key in database table.

        * :py:attr:`session_id`\
        (:py:class:`sqlalchemy.schema.Column(Integer)`)\
        - ID of the session activity belongs to.

        * :py:attr:`session` (:py:class:`sqlalchemy.orm.relationship`)\
        - Session relationship.

        * :py:attr:`project_id`\
        (:py:class:`sqlalchemy.schema.Column(Integer)`)\
        - ID of the project activity belongs to.

        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`)\
        - Project relationship.

        * :py:attr:`active`\
        (:py:class:`sqlalchemy.schema.Column(Boolean)`)\
        - Boolean flag indicating that the project is active.

    :param project: Project activity belongs to.
    :type project: :py:class:`models.Project`

    :param session: Optional session activity belongs to.
    :type session: :py:class:`models.Session`

    """
    __tablename__ = 'activity'

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    session_id = Column(Integer, ForeignKey('session.id'), nullable=True)

    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)

    active = Column(Boolean, nullable=False, default=True)

    session = relationship('Session',
                           backref=backref('activities', order_by=id))

    project = relationship('Project',
                           backref=backref('activities', order_by=id))

    def __init__(self, project, session=None):
        self.project = project
        self.project_id = project.id
        self.session = session
        self.session_id = session.id if session else 0
        Activity.update(self)


class Company(MethodMixin, Base):
    """
    A class representation of a company.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(Integer)`)\
        - ID of the company, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(String)`)\
        - Name of the company (Max 50 characters).

    :param name: The name of the company.
    :type name: :py:class:`String`

    """
    __tablename__ = 'company'

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    name = Column(String(length=50, convert_unicode=True), nullable=False)

    def __init__(self, name):
        """
        Note, you should call this constructor only inside a
        try ... except ... block.

        """
        self.name = name
        if Company.get('exists', Company.name == name):
            raise ItemAlreadyExistsException('Company already exists!')
        Company.update(self)

    def __str__(self):
        """
        Human interface representation for Company.

        :returns: The name of the company.
        :rtype: String

        """
        return self.name


class Computer(MethodMixin, Base):
    """
    A class representation of a computer.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(Integer)`)\
        - ID of computer, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(String)`)\
        - Name of the computer.

        * :py:attr:`ip`\
        (:py:class:`sqlalchemy.schema.Column(Integer)`)\
        - Internet Protocol address of the computer (Defined as unsigned).

        * :py:attr:`mac`\
        (:py:class:`sqlalchemy.schema.Column(String)`\
        - Media Access Control address of the computer.

        * :py:attr:`time`\
        (:py:class:`sqlalchemy.schema.Column(DateTime)`)\
        - Time of the last network activity from the computer.

        * :py:attr:`screens`\
        (:py:class:`sqlalchemy.schema.Column(SmallInteger)`)\
        - Number of screens on the computer.

        * :py:attr:`responsive`\
        (:py:class:`sqlalchemy.schema.Column(SmallInteger)`)\
        - The responsive value of the computer.

        * :py:attr:`user_id`\
        (:py:class:`sqlalchemy.schema.Column(Integer)`)\
        - ID of the user currently using the computer.

        * :py:attr:`user` (:py:class:`sqlalchemy.orm.relationship`)\
        - The current user.

        * :py:attr:`wos_id`\
        (:py:class:`sqlalchemy.schema.Column(Integer)`)\
        - Network node ID, usually the last part of IP address (X.X.X.Y).

    """
    __tablename__ = 'computer'

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    name = Column(String(length=50, convert_unicode=True), nullable=False)

    ip = Column(Integer(unsigned=True), nullable=False)

    mac = Column(String(length=12, convert_unicode=True), nullable=True)

    time = Column(DateTime, nullable=True)

    screens = Column(SmallInteger, nullable=True, default=0)

    responsive = Column(SmallInteger, nullable=True)

    wos_id = Column(Integer, nullable=True)

    user_id = Column(Integer, ForeignKey('user.id'))

    user = relationship('User', backref=backref('computers', order_by=id))

    def __init__(self, name, ip, mac, screens, responsive, wos_id):
        self.name = name
        self.ip = ip
        self.mac = mac
        self.screens = screens
        self.responsive = responsive
        self.wos_id = wos_id
        if Action.get('exists', Computer.mac == mac):
            raise ItemAlreadyExistsException('Computer already exists!')
        Computer.update(self)

    @classmethod
    def time_ordering(cls, computer):
        """Key function for time ordering."""
        return computer.time

    @classmethod
    def get_most_recent_by_mac(cls, mac_address):
        """
        Retrieve a computer by it's hardware identifier.

        """
        computers = Computer.get('all', Computer.mac == mac_address)

        # If we got no computers.
        if not computers:
            return None

        # If we got only one, just return it.
        if len(computers) == 1:
            return computers.pop()

        # Filter out computers without time stamp.
        temp = [computer for computer in computers if computer.time]

        # If there were none with a timestamp, return the last id wise.
        if not temp:
            return sorted(computers, key=Computer.id_ordering).pop()

        # If there was only one computer with a timestamp, use that one.
        computers = temp
        if len(computers) == 1:
            return computers.pop()

        # Return the most recent timestamp wise.
        return sorted(computers, key=Computer.time_ordering).pop()

    def __str__(self):
        str_msg = '<{wos_id}: name:{name} screens:{screens}{iftime}>'
        my_time = (' time: ' + self.time.isoformat()) if self.time else ''
        return str_msg.format(iftime=my_time, **self.__dict__)


class Event(MethodMixin, Base):
    """
    A class representation of Event. A simple note with timestamp during a
    session.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the event, used as primary key in database table.

        * :py:attr:`title`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Title of the event (Max 40 characters).

        * :py:attr:`desc`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - More in-depth description of the event (Max 500 characters).

        * :py:attr:`time`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.DateTime)`)\
        - Time the event took place.

        * :py:attr:`session_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the session this event belongs to.

        * :py:attr:`session` (:py:class:`sqlalchemy.orm.relationship`)\
        - Session this event belongs to.

    """
    __tablename__ = 'event'

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    title = Column(String(length=40, convert_unicode=True), nullable=False)

    desc = Column(String(length=500, convert_unicode=True), nullable=True)

    time = Column(DateTime, default=func.now())

    session_id = Column(Integer, ForeignKey('session.id'))

    session = relationship('Session', backref=backref('events', order_by=id))

    def __init__(self, session, title='', description=''):
        self.title = title
        self.desc = description
        self.session = session
        Event.update(self)


class File(MethodMixin, Base):
    """
    A class representation of a file.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the file, used as primary key in database table.

        * :py:attr:`path`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Path of the file on DiWa (max 255 chars).

        * :py:attr:`project_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the project this file belongs to.

        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`)\
        - Project this file belongs to.

    """
    __tablename__ = 'file'

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    path = Column(String(length=255, convert_unicode=True), nullable=False)

    project_id = Column(Integer, ForeignKey('project.id'), nullable=True)

    project = relationship('Project', backref=backref('files', order_by=id))

    def __init__(self, file_path, project=None):
        self.path = file_path
        self.project = project
        if File.get('exists', File.path == file_path):
            raise ItemAlreadyExistsException('File already exists!')
        File.update(self)

    def __str__(self):
        return self.path


class FileAction(MethodMixin, Base):
    """
    A class representation of a file action.

    Fields:

        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the FileAction, used as primary key in the database table.

        * :py:attr:`file_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlaclhemy.types.Integer)`)\
        - ID of the file this FileAction affects.

        * :py:attr:`file` (:py:class:`sqlalchemy.orm.relationship)`)\
        - The file this FileAction affects.

        * :py:attr:`action_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the action affecting the file.

        * :py:attr:`action` (:py:class:`sqlalchemy.orm.relationship)`)\
        - Action affecting the file.

        * :py:attr:`action_time`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.DateTime)`)\
        - Time the action took place on.

        * :py:attr:`user_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the user performing the action.

        * :py:attr:`user` (:py:class:`sqlalchemy.orm.relationship`)\
        - User peforming the action.

        * :py:attr:`computer_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the computer user performed the action on.

        * :py:attr:`computer` (:py:class:`sqlalchemy.orm.relationship`)\
        - Computer user performed the action on.

        * :py:attr:`session_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the session user performed the action in.

        * :py:attr:`session` (:py:class:`sqlalchemy.orm.relationship`)\
        - Session user performed the action in.

    :param file_: The file which is subjected to the action.
    :type file_: :py:class:`models.File`

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

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    file_id = Column(Integer, ForeignKey('file.id'), nullable=False)

    action_id = Column(Integer, ForeignKey('action.id'), nullable=False)

    action_time = Column(DateTime, default=func.now())

    user_id = Column(Integer, ForeignKey('user.id'), nullable=True)

    computer_id = Column(Integer, ForeignKey('computer.id'), nullable=True)

    session_id = Column(Integer, ForeignKey('session.id'), nullable=True)

    file = relationship('File', backref=backref('actions', order_by=id))

    action = relationship('Action', backref=backref('actions', order_by=id))

    user = relationship('User', backref=backref('fileactions', order_by=id))

    computer = relationship('Computer',
                            backref=backref('fileactions', order_by=id))

    session = relationship('Session',
                           backref=backref('fileactions', order_by=id))

    def __init__(self, file_, action, session=None, computer=None,
                 user=None):
        self.file = file_
        self.action = action
        self.session = session
        self.computer = computer
        self.user = user
        FileAction.update(self)


class Project(MethodMixin, Base):
    """
    A class representation of a project.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of project, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Name of the project (Max 50 characters).

        * :py:attr:`company_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
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

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    name = Column(String(length=50, convert_unicode=True), nullable=False)

    company_id = Column(Integer, ForeignKey('company.id'), nullable=False)

    dir = Column(String(length=255, convert_unicode=True), nullable=True)

    password = Column(String(length=40, convert_unicode=True), nullable=True)

    company = relationship('Company',
                           backref=backref(name='projects', order_by=id),
                           uselist=False)

    members = relationship('User', ProjectMembers, backref=backref('projects'))

    def __init__(self, name, directory, company, password):
        self.name = name
        self.company = company
        self.dir = directory
        self.password = password
        if Project.get('exists', Project.name == name):
            raise ItemAlreadyExistsException('Project already exists!')
        Project.update(self)


class Session(MethodMixin, Base):
    """
    A class representation of a session.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of session, used as primary key in database table.

        * :py:attr:`name`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`)\
        - Name of session (Max 50 characters).

        * :py:attr:`project_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - ID of the project the session belongs to.

        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`)\
        - The project the session belongs to.

        * :py:attr:`starttime`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.DateTime)`)\
        - Time the session began, defaults to `now()`.

        * :py:attr:`endtime`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.DateTime)`)\
        - The time session ended.

        * :py:attr:`previous_session_id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
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

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    name = Column(String(length=50, convert_unicode=True), nullable=True)

    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)

    starttime = Column(DateTime, default=func.now(), nullable=True)

    endtime = Column(DateTime, nullable=True)

    previous_session_id = Column(Integer, ForeignKey('session.id'),
                                 nullable=True)

    project = relationship('Project', backref=backref('sessions', order_by=id))

    previous_session = relationship('Session', uselist=False, remote_side=[id])

    participants = relationship('User', SessionParticipants,
                                backref=backref('sessions'))

    computers = relationship('Computer', SessionComputers,
                             backref=backref('sessions'))

    def __init__(self, project, previous_session=None):
        self.project = project
        self.users = []
        self.endtime = None
        self.last_checked = None
        self.previous_session = previous_session
        Session.update(self)

    def Start(self):
        """
        Start a session.
        Set the :py:attr:`last_checked` field to current DateTime.

        """
        self.last_checked = datetime.now()

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


class User(MethodMixin, Base):
    """
    A class representation of a user.

    :note: Currently not used anywhere.

    Fields:
        * :py:attr:`id`\
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
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
        (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`)\
        - Company id of the employing company.

        * :py:attr:`company` (:py:class:`sqlalchemy.orm.relationship`)\
        - Company relationship.

    :param name: Name of the user.
    :type name: :py:class:`String`

    :param company: The employer.
    :type company: :py:class:`models.Company`

    """
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True,
                default=text(DEFAULT.format(__tablename__)))

    name = Column(String(length=50, convert_unicode=True), nullable=False)

    email = Column(String(length=100, convert_unicode=True), nullable=True)

    title = Column(String(length=50, convert_unicode=True), nullable=True)

    department = Column(String(length=100, convert_unicode=True),
                        nullable=True)

    company_id = Column(Integer, ForeignKey('company.id'), nullable=False)

    company = relationship('Company',
                           backref=backref('employees', order_by=id))

    def __init__(self, name, company, email=None, title=None, department=None):
        self.name = name
        self.email = email
        self.title = title
        self.department = department
        self.company = company
        self.uniqueness = (User.name == name, User.company_id == company.id)
        if User.get('exists', User.name == name,
                    User.company_id == company.id):
            raise ItemAlreadyExistsException('User already exists!')
        User.update(self)
