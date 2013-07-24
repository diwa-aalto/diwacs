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


class PROJECT_EVENT_HANDLER(FileSystemEventHandler):
    """
    Handler for FileSystem events on project folder.
    It uses watchdog library internally.

    :param project_id: Project id from database.
    :type project_id: Integer

    """
    # -------------- CLASS VARIABLES --------------
    project_handler = {
        'created': PROJECT_EVENT_HANDLER._on_created_project,
        'deleted': PROJECT_EVENT_HANDLER._on_deleted_project,
        'modified': PROJECT_EVENT_HANDLER._on_modified_project,
        'moved': PROJECT_EVENT_HANDLER._on_moved_project
    }

    scanner_handler = {
        'created': PROJECT_EVENT_HANDLER._on_created_scanner
    }

    # -------------- CONSTRUCTOR --------------
    def __init__(self, project_id, handler_type='project'):
        # Initialize.
        self.project_id = project_id
        FileSystemEventHandler.__init__(self)
        self.actions = None
        # Handler is a project file handler...
        if handler_type == 'project':
            log_msg = ('PROJECT_EVENT_HANDLER initialized for project '
                       'with ID {project_id}')
            self.actions = PROJECT_EVENT_HANDLER.project_handler
        # Handler is a project scanner handler.
        elif handler_type == 'scanner':
            log_msg = ('Project image scan handler initialized for project '
                       'with ID {project_id}')
            self.actions = PROJECT_EVENT_HANDLER.scanner_handler
        # Undefined handler type.
        else:
            raise NotImplementedError()
        # Populate the log_mgs with data and log.
        log_msg = log_msg.format(**self.__dict__)
        _logger().debug(log_msg)

    # -------------- PUBLIC METHODS --------------
    def on_created(self, event):
        if 'created' in self.actions:
            self.actions['created'](event)

    def on_deleted(self, event):
        if 'deleted' in self.actions:
            self.actions['deleted'](event)

    def on_modified(self, event):
        if 'modified' in self.actions:
            self.actions['modified'](event)

    def on_moved(self, event):
        if 'moved' in self.actions:
            self.actions['moved'](event)

    # -------------- PRIVATE METHODS VARIABLES --------------
    def _on_created_project(self, event):
        """
        On_created event handler for project files.
        Logs to database.

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

    def _on_deleted_project(self, event):
        """
        On_deleted event handler for project files.
        Logs to database.

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

    def _on_modified_project(self, event):
        """
        On_modified event handler for project files.
        Logs to database.

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

    def _on_moved_project(self, event):
        """
        On_modified event handler for project files.

        This should get called when a project file has been moved.

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

    def _on_created_scanner(self, event):
        """
        On_created event handler for project scanned files.
        Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        database = None
        try:
            project_path = controller.project.get_project_path(self.project_id)
            if not project_path:
                return
            file_path = event.src_path
            basename = os.path.basename(file_path)
            _logger().debug('on_created at: %s (%s)', project_path, basename)
            new_path = os.path.join(project_path, basename)
            try:
                # Let's build the directory path to the file.
                path_parts = os.path.dirname(file_path)
                path_parts = os.path.splitdrive(path_parts)[1]  # (drive, path)
                # Now it is for example: [this part]
                # C:[\Some\path\To\dir]\myfile.txt
                path_parts = path_parts.strip(os.path.sep)
                path_parts = path_parts.split(os.path.sep)
                # ['Some', 'path', 'To', 'dir']
                path_parts = [part.lower() for part in path_parts]
                # ['some', 'path', 'to', 'dir']
                if 'scan' in path_parts:
                    # The file is a subdirectory of "scan" folder in
                    # some sense.
                    sleep(60)
            except (IndexError, ValueError):
                pass
            shutil.copy2(file_path, new_path)
            database = controller.common.connect_to_database()
            project = database.query(Project)
            project = project.filter(Project.id == self.project_id).one()
            _logger().debug('File(%s, %s)', new_path, str(project))
            file_object = File(path=new_path, project=project)
            action_object = database.query(Action).filter(Action.id == 1).one()
            file_action_object = FileAction(file_object, action_object)
            database.add(file_object)
            database.add(file_action_object)
            database.commit()
            log_msg = ('FileAction FILE(id={file_id}, name="{file_name}") '
                       'ACTION (id=1, name="Created")')
            log_msg = log_msg.format(file_id=file_object.id,
                                     file_name=basename)
            _logger().debug(log_msg)
        except Exception as excp:
            log_msg = 'Exception in SCAN HANDLER: {exception!s}'
            log_msg = log_msg.format(exception=excp)
            _logger().exception(log_msg)
        if database:
            database.close()
