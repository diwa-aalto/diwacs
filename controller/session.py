"""
Created on 28.6.2013

:author: neriksso

"""
# Critical import.
import controller.common

# Third party imports.
from sqlalchemy import func

# Own imports
import controller.activity
from models import Activity, Event, Project, Session
from sqlalchemy.orm.exc import NoResultFound


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
    session = Session.get_by_id(session_id)
    return Event(session, title, description).id


def get_active_session(pgm_group):
    """
    Get the active session.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :returns: The active session ID.
    :rtype: Integer

    """
    activity = controller.activity.get_active_activity(pgm_group)
    return activity.session if activity else None


def get_latest_event_id():
    """
    Get the latest event id.

    :returns: The ID of latest event.
    :rtype: Integer

    """
    event = Event.get('last')
    return event.id


def get_session_id_by_activity(activity_id):
    """
    Get the session ID that this activity_id is a part of.

    :param activity_id: ID of the activity_id.
    :type activity_id: Integer

    :returns: The project ID.
    :rtype: Integer

    """
    activity = Activity.get_by_id(activity_id)
    return activity.session_id if activity else 0


def get_sessions_by_project(project_id):
    """
    Fetches sessions for a project.

    :param project_id: Project id from database.
    :type project_id: Integer

    """
    return Session.get('all', Session.project_id == project_id)


def end_session(session_id):
    """
    Ends a session, sets its endtime to database.
    Ends file scanner.

    :param session: Current session.
    :type session: :py:class:`models.Session`

    """
    if session_id < 1:
        return
    session = Session.get_by_id(session_id)
    session.endtime = func.now()
    session.update()


def start_new_session(project_id, old_session_id=None):
    """
    Creates a session to the database and return a session object.

    :param project_id: Project id from database.
    :type project_id: Integer

    :param old_session_id: A session id of a session which will be continued.
    :type old_session_id: Integer

    """
    project = Project.get_by_id(project_id)
    try:
        old_session = Session.get_by_id(old_session_id)
    except NoResultFound:
        old_session = None
    return Session(project, old_session)
