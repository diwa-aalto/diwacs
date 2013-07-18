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
from watchdog.events import DirCreatedEvent, FileSystemEventHandler

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
        self.project_id = project_id
        FileSystemEventHandler.__init__(self)
        log_msg = ('PROJECT_FILE_EVENT_HANDLER initialized for project '
                   'with ID {project_id}')
        log_msg = log_msg.format(project_id=project_id)
        _logger().debug(log_msg)

    def on_created(self, event):
        """
        On_created event handler. Logs to database.

        :param event: The event.
        :type event: :py:class:`watchdog.events.FileSystemEvent`

        """
        # We are only interested in files.
        if isinstance(event, DirCreatedEvent):
            return
        database = None
        try:
            database = controller.common.connect_to_database()
            file_path = event.src_path
            log_msg = 'Project file {filename} created in {directory}'
            log_msg = log_msg.format(filename=os.path.basename(file_path),
                                     directory=os.path.dirname(file_path))
            _logger().debug(log_msg)
            project = database.query(Project)
            project = project.filter(Project.id == self.project_id).one()
            file_object = File(path=file_path, project=project)
            action_object = database.query(Action)
            action_object = action_object.filter(Action.id == 1).one()
            file_action_object = FileAction(file_object, action_object)
            database.merge(file_object)
            database.merge(file_action_object)
            database.commit()
        except Exception as excp:
            log_msg = ('Exception in Project file scanner on_created '
                       'callback: {exception!s}')
            log_msg = log_msg.format(exception=excp)
            _logger().exception(log_msg)
        if database is not None:
            database.close()

    def on_deleted(self, event):
        """
        On_deleted event handler. Logs to database.

        :param event: The event.
        :type event: :py:class:`watchdog.events.FileSystemEvent`

        """
        # We are only interested in files.
        if isinstance(event, DirCreatedEvent):
            return
        database = None
        try:
            database = controller.common.connect_to_database()
            project_id = self.project_id
            file_path = event.src_path
            log_msg = 'Project file {filename} deleted in {directory}'
            log_msg = log_msg.format(filename=os.path.basename(file_path),
                                     directory=os.path.dirname(file_path))
            _logger().debug(log_msg)
            file_object = database.query(File)
            file_object = file_object.filter(File.path == file_path,
                                             File.project_id == project_id)
            file_object = file_object.order_by(File.id.desc()).first()
            action_object = database.query(Action)
            action_object = action_object.filter(Action.id == 2).one()
            file_action_object = FileAction(file_object, action_object)
            file_object.project = None
            database.merge(file_object)
            database.merge(file_action_object)
            database.commit()
        except Exception as excp:
            log_msg = ('Exception in Project file scanner on_deleted '
                       'callback: {exception!s}')
            log_msg = log_msg.format(exception=excp)
            _logger().exception(log_msg)
        if database is not None:
            database.close()

    def on_modified(self, event):
        """
        On_modified event handler. Logs to database.

        :param event: The event.
        :type event: :py:class:`watchdog.events.FileSystemEvent`

        """
        # We are only interested in files.
        if isinstance(event, DirCreatedEvent):
            return
        database = None
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
        except Exception as excp:
            log_msg = ('Exception in Project file scanner on_modified '
                       'callback: {exception!s}')
            log_msg = log_msg.format(exception=excp)
            _logger().exception(log_msg)
        if database is not None:
            database.close()

    def on_moved(self, event):
        """
        On_modified event handler.

        - If the file exists in database:
            - If the target path is inside project directory, change the\
            path entry in database.
            - If the target path is outside project directory, set the\
            file as deleted (project.id = NULL).
        - If the file does not exist in database:
            - If the target path is inside the project directory, add the\
            file into the database.
            - If the target path is outside the project directory, do nothing.

        :param event: The event.
        :type event: :py:class:`watchdog.events.FileSystemEvent`

        """
        # We are only interested in files.
        if isinstance(event, DirCreatedEvent):
            return
        database = None
        # TODO: Fill this.
        if database is not None:
            database.close()


#:TODO: Just merge this with our PROJECT_FILE_EVENT_HANDLER...
class SCAN_HANDLER(FileSystemEventHandler):
    """
    Handler for FileSystem events on SCANNING folder.

    :param project_id: Project id from database.
    :type project_id: Integer

    """
    def __init__(self, project_id):
        self.project_id = project_id
        FileSystemEventHandler.__init__(self)
        log_msg = 'SCAN_HANDLER initialized for project with ID {project_id}'
        log_msg = log_msg.format(project_id=project_id)
        _logger().debug(log_msg)

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
            file_path = event.src_path
            basename = os.path.basename(file_path)
            _logger().debug('on_created at: %s (%s)', project_path, basename)
            new_path = os.path.join(project_path, basename)
            if 'Scan' in file_path:
                sleep(60)
            shutil.copy2(file_path, new_path)
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
            log_msg = 'Exception in SCAN HANDLER: {exception!s}'
            log_msg = log_msg.format(exception=excp)
            _logger().exception(log_msg)
