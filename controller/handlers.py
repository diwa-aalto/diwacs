"""
Created on 28.6.2013

:author: neriksso

"""
# Critical import.
import controller.common

# System imports.
import os
import shutil
from time import sleep

# Third party imports.
from watchdog.events import FileSystemEventHandler

# Own imports.
import controller.project
from models import Action, File, FileAction, Project


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


class PROJECT_FILE_EVENT_HANDLER(FileSystemEventHandler):
    """
    Handler for FileSystem events on project folder.

    :param project_id: Project id from database.
    :type project_id: Integer

    """
    def __init__(self, project_id):
        FileSystemEventHandler.__init__(self)
        self.project_id = project_id
        logmsg = 'PROJECT_FILE_EVENT_HANDLER initialized for project: %d'
        _logger().debug(logmsg, project_id)

    def on_created(self, event):
        """On_created event handler. Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        try:
            database = controller.common.connect_to_database()
            evt_path = event.src_path
            logmsg = 'PROJECT FILE CREATED %s %s'
            _logger().debug(logmsg, str(type(evt_path)), evt_path)
            project = database.query(Project)
            project = project.filter(Project.id == self.project_id).one()
            file_object = File(path=event.src_path, project=project)
            action_object = database.query(Action)
            action_object = action_object.filter(Action.id == 1).one()
            file_action_object = FileAction(file_object, action_object)
            database.merge(file_object)
            database.merge(file_action_object)
            database.commit()
            database.close()
        except Exception as excp:
            logmsg = 'Project file scanner on_created exception: %s'
            _logger().exception(logmsg, str(excp))

    def on_deleted(self, event):
        """
        On_deleted event handler. Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        try:
            database = controller.common.connect_to_database()
            project_id = self.project_id
            file_object = database.query(File)
            file_object = file_object.filter(File.path == event.src_path,
                                             File.project_id == project_id)
            file_object = file_object.order_by(File.id.desc()).first()
            action_object = database.query(Action)
            action_object = action_object.filter(Action.id == 2).one()
            file_action_object = FileAction(file_object, action_object)
            file_object.project = None
            database.merge(file_object)
            database.merge(file_action_object)
            database.commit()
            database.close()
        except Exception as excp:
            logmsg = 'Project file scanner on_deleted exception: %s'
            _logger().exception(logmsg, str(excp))

    def on_modified(self, event):
        """
        On_modified event handler. Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        try:
            database = controller.common.connect_to_database()
            project_id = self.project_id
            file_object = database.query(File)
            file_object = file_object.filter(File.path == event.src_path,
                                             File.project_id == project_id)
            file_object = file_object.order_by(File.id.desc()).first()
            _logger().debug('on_modified - query = %s', str(file_object))
            if not file_object:
                file_object = self.on_created(event)
                _logger().debug('on_created result: %s', str(file_object))
            action_object = database.query(Action).filter(Action.id == 3).one()
            file_action_object = FileAction(file_object, action_object)
            database.merge(file_object)
            database.merge(file_action_object)
            database.commit()
            database.close()
        except Exception as excp:
            logmsg = 'Project file scanner on_modifed exception: %s'
            _logger().exception(logmsg, str(excp))


class SCAN_HANDLER(FileSystemEventHandler):
    """
    Handler for FileSystem events on SCANNING folder.

    :param project_id: Project id from database.
    :type project_id: Integer

    """
    def __init__(self, project_id):
        FileSystemEventHandler.__init__(self)
        self.project_id = project_id
        _logger().debug('SCAN_HANDLER initialized for project: %d', project_id)

    def on_created(self, event):
        """
        On_created event handler. Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        try:
            project_path = controller.project.get_project_path(self.project_id)
            if not project_path:
                return
            basename = os.path.basename(event.src_path)
            _logger().debug('on_created at: %s (%s)', project_path, basename)
            new_path = os.path.join(project_path, basename)
            if 'Scan' in event.src_path:
                sleep(60)
            shutil.copy2(event.src_path, new_path)
            database = controller.common.connect_to_database()
            project = database.query(Project)
            project = project.filter(Project.id == self.project_id).one()
            _logger().debug('File(%s, %s)', new_path, str(project))
            file_object = File(path=new_path, project=project)
            action_object = database.query(Action).filter(Action.id == 1).one()
            file_action_object = FileAction(file_object, action_object)
            _logger().debug('FileAction: %s', str(file_action_object))
            database.add(file_object)
            database.add(file_action_object)
            database.commit()
            database.close()
        except Exception as excp:
            _logger().exception('Exception in SCAN HANDLER: %s', str(excp))
