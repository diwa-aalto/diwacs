"""
Created on 28.6.2013

:author: neriksso

"""
# Critical import.
import controller.common

# Own imports.
from models import Activity, Project, Session


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


def add_or_update_activity(project_id, pgm_group, session_id=0, activity_id=0):
    """
    Add activity to database.

    :param project_id: ID of the project Activity is associated with.
    :type project_id: Integer

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :param session_id: ID of the session Activity is associated with.
    :type session_id: Integer

    :param activity_id: ID of the activity.
    :type activity_id: Integer

    :returns: Activity ID of the added activity.
    :rtype: Integer

    """
    project = Project.get_by_id(project_id)
    session = Session.get_by_id(session_id) if session_id > 0 else None
    if activity_id > 0:
        activity = Activity.get_by_id(activity_id)
        activity.project = project
        if session_id > 0:
            activity.session = session
    else:
        activity = Activity(project, session)
    activity.active = pgm_group
    Activity.update(activity)
    return activity.id


def get_active_activity(pgm_group):
    """
    Get the latest active activity.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :returns: Latest active activity.
    :rtype: :py:class:`models.Activity`

    """
    return Activity.get('last', Activity.active == pgm_group)


def unset_activity(pgm_group):
    """
    Unsets activity for PGM Group.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    """
    activities = Activity.get('all', Activity.active == pgm_group)
    for activity in activities:
        activity.active = None
        Activity.update(activity)   # TODO: Buffer somehow so one
                                    #       connection is enough?
