"""
Created on 28.6.2013

:author: neriksso

"""
# Critical import.
import controller.common

# System imports.


# Third party imports.
import sqlalchemy

# Own imports.
from models import Activity, Project, Session


def logger():
    """ Return controller logger. """
    return controller.common.LOGGER


def add_activity(project_id, pgm_group, session_id=None, activity_id=None):
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
    try:
        database = controller.common.connect_to_database()
        project = database.query(Project).filter(Project.id == project_id)
        project = project.one()
        if session_id:
            session = database.query(Session).filter(Session.id == session_id)
            session = session.one()
        else:
            session = None
        activity = None
        if activity_id:
            activity = database.query(Activity)
            activity = activity.filter(Activity.id == activity_id)
            activity = activity.one()
            activity.project = project
            activity.session = session
            activity.active = pgm_group
        else:
            activity = Activity(project, session)
        database.add(activity)
        database.commit()
        database.expunge(activity)
        database.close()
        return activity.id
    except sqlalchemy.exc.SQLAlchemyError, excp:
        logger().exception('add_activity exception: %s', str(excp))
        return None


def get_active_activity(pgm_group):
    """
    Get the latest active activity id.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :returns: Latest active activity ID.
    :rtype: Integer

    """
    database = None
    result = None
    try:
        database = controller.common.connect_to_database()
        activity = database.query(Activity)
        activity = activity.filter(Activity.active == pgm_group)
        activity = activity.order_by(sqlalchemy.desc(Activity.id)).first()
        if activity:
            result = activity.id
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
    return result


def unset_activity(pgm_group):
    """
    Unsets activity for PGM Group.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    """
    database = None
    try:
        database = controller.common.connect_to_database()
        activities = database.query(Activity)
        for activity in activities.filter(Activity.active == pgm_group).all():
            activity.active = False
            database.add(activity)
        database.commit()
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
