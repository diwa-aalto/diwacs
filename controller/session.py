"""
Created on 28.6.2013

:author: neriksso

"""
# Critical import.
import controller.common

# Third party imports.
import sqlalchemy

# Own imports
import controller.activity
from models import Activity, Event, Project, Session


def _logger():
    """
    Get the current logger for controller package.

    This function has been prefixed with _ to hide it from
    documentation as this is only used internally in the
    package.

    :returns: The logger.
    :rtype: logging.Logger

    """
    return controller.common.LOGGER


def add_event(session_id, title, description):
    """
    Adds an event to the database.
    Returns the ID field of the added event.

    :param session: The current session.
    :type session: :class:`models.Session`

    :param description: Description of the event.
    :type description: String

    :returns: The event ID.
    :rtype: Integer

    """
    event_id = None
    database = None
    try:
        database = controller.common.connect_to_database(True)
        session = None
        if session_id:
            session = database.query(Session)
            session = session.filter(Session.id == session_id).one()
        event = Event(desc=description, session=session, title=title)
        database.add(event)
        database.commit()
        event_id = event.id
    except sqlalchemy.exc.SQLAlchemyError:
        _logger().exception('add event exception.')
    if database:
        database.close()
    _logger().info('A new event added.')
    return event_id


def get_active_session(pgm_group):
    """
    Get the active session.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :returns: The active session ID.
    :rtype: Integer

    """
    activity_id = controller.activity.get_active_activity(pgm_group)
    if activity_id == None:
        return 0
    database = None
    session_id = None
    try:
        database = controller.common.connect_to_database()
        activity = database.query(Activity)
        activity = activity.filter(Activity.id == activity_id)
        activity = activity.one()
        session = activity.session
        session_id = session.id
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
    return session_id


def get_latest_event():
    """
    Get the latest event id.

    :returns: The ID of latest event.
    :rtype: Integer

    """
    database = None
    result = 0
    try:
        database = controller.common.connect_to_database()
        event = database.query(Event.id)
        event = event.order_by(sqlalchemy.desc(Event.id)).first()
        if event.id:
            result = event.id
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
    return result


def get_session_id_by_activity(activity_id):
    """
    Docstring here.

    """
    session_id = 0
    try:
        database = controller.common.connect_to_database()
        act = database.query(Activity).filter(Activity.id == activity_id).one()
        if act.session_id:
            session_id = act.session_id
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
    return session_id


def get_sessions_by_project(project_id):
    """
    Fetches sessions for a project.

    :param project_id: Project id from database.
    :type project_id: Integer

    """
    database = None
    result = []
    try:
        database = controller.common.connect_to_database()
        sessions = database.query(Session)
        sessions = sessions.filter(Session.project_id == project_id).all()
        if sessions:
            result = sessions
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
    return result


def end_session(session_id):
    """
    Ends a session, sets its endtime to database.
    Ends file scanner.

    :param session: Current session.
    :type session: :py:class:`models.Session`

    """
    database = None
    if not session_id or session_id < 1:
        return
    _logger().debug('end_session(%d)', session_id)
    try:
        database = controller.common.connect_to_database()
        session = database.query(Session).filter(Session.id == session_id)
        session = session.one()
        session.endtime = sqlalchemy.func.now()
        database.add(session)
        database.commit()
    except sqlalchemy.exc.SQLAlchemyError as excp:
        _logger().exception('end_session exception: %s', str(excp))
    if database:
        database.close()


def start_new_session(project_id, session_id=None, old_session_id=None):
    """
    Creates a session to the database and return a session object.

    :param project_id: Project id from database.
    :type project_id: Integer

    :param session_id: an existing session id from database.
    :type session_id: Integer

    :param old_session_id: A session id of a session which will be continued.
    :type old_session_id: Integer

    """
    database = controller.common.connect_to_database()
    project = None
    try:
        project = database.query(Project)
        project = project.filter(Project.id == project_id).one()
    except sqlalchemy.exc.SQLAlchemyError:
        return None
    # recent_path = os.path.join(os.getenv('APPDATA'),
    #                            'Microsoft\\Windows\\Recent')
    session = None
    if session_id:
        try:
            session = database.query(Session)
            session = session.filter(Session.id == session_id).one()
        except sqlalchemy.exc.SQLAlchemyError:
            session = None
    else:
        session = Session(project)
        #initial add and commit
        database.add(session)
        database.commit()
        if old_session_id:
            #link two sessions together
            try:
                old_session = database.query(Session)
                old_session = old_session.filter(Session.id == old_session_id)
                old_session = old_session.one()
                session.previous_session = old_session
                old_session.next_session = session
                database.add(session)
                database.add(old_session)
                database.commit()
            except sqlalchemy.exc.SQLAlchemyError:
                pass
    database.expunge(session)
    database.close()
    return session
