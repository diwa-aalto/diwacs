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
from watchdog.events import (FileCreatedEvent, FileDeletedEvent,
                             FileModifiedEvent, FileMovedEvent,
                             FileSystemEventHandler)

# Own imports.
import controller.project
from models import (File, Project, ACTIONS, REVERSE_ACTIONS)
import diwavars


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
    # -------------- CONSTRUCTOR --------------
    def __init__(self, project_id, handler_type='project'):
        # Initialize.
        self.project_id = project_id
        FileSystemEventHandler.__init__(self)
        # Handler is a project file handler...
        if handler_type == 'project':
            log_msg = ('PROJECT_EVENT_HANDLER initialized for project '
                       'with ID {project_id}')
            self.actions = {
                'Created': self._on_created_project,
                'Deleted': self._on_deleted_project,
                'Modified': self._on_modified_project,
                'Moved': self._on_moved_project
            }
        # Handler is a project scanner handler.
        elif handler_type == 'scanner':
            log_msg = ('Project image scan handler initialized for project '
                       'with ID {project_id}')
            self.actions = {'Created': self._on_created_scanner}
        # Undefined handler type.
        else:
            raise NotImplementedError()
        # Populate the log_mgs with data and log.
        log_msg = log_msg.format(**self.__dict__)
        _logger().debug(log_msg)

    # -------------- PUBLIC METHODS --------------
    # These ignore directory events.
    def on_created(self, event):
        if isinstance(event, FileCreatedEvent) and 'Created' in self.actions:
            self.actions['Created'](event)

    def on_deleted(self, event):
        if isinstance(event, FileDeletedEvent) and 'Deleted' in self.actions:
            self.actions['Deleted'](event)

    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent) and 'Modified' in self.actions:
            self.actions['Modified'](event)

    def on_moved(self, event):
        if isinstance(event, FileMovedEvent) and 'Moved' in self.actions:
            self.actions['Moved'](event)

    # -------------- PRIVATE METHODS --------------
    def _project_prototype(self, path, action_id):
        """
        On_created event handler for project files.
        Logs to database.

        :param event: The event.
        :type event: :py:class:`watchdog.events.FileSystemEvent`

        """
        #: TODO: In init pass a function to query current session id :p
        try:
            log_msg = 'Project file {filename} {action} in {directory}'
            log_msg = log_msg.format(filename=os.path.basename(path),
                                     action=ACTIONS[action_id],
                                     directory=os.path.dirname(path))
            _logger().debug(log_msg)
            pgm = diwavars.PGM_GROUP
            session_id = controller.session.get_active_session(pgm)
            controller.project.create_file_action(path, action_id, session_id,
                                                  self.project_id)
        except Exception as excp:
            log_msg = ('Exception in Project file handler on_{action} '
                       'callback: {exception!s}')
            log_msg = log_msg.format(action=ACTIONS[action_id], exception=excp)
            _logger().exception(log_msg)

    def _on_created_project(self, event):
        """
        On_created event handler for project files.
        Logs to database.

        :param event: The event.
        :type event: :py:class:`watchdog.events.FileSystemEvent`

        """
        self._project_prototype(event.src_path, REVERSE_ACTIONS['Created'])

    def _on_deleted_project(self, event):
        """
        On_deleted event handler for project files.
        Logs to database.

        :param event: The event.
        :type event: :py:class:`watchdog.events.FileSystemEvent`

        """
        self._project_prototype(event.src_path, REVERSE_ACTIONS['Deleted'])

    def _on_modified_project(self, event):
        """
        On_modified event handler for project files.
        Logs to database.

        :param event: The event.
        :type event: :py:class:`watchdog.events.FileSystemEvent`

        """
        self._project_prototype(event.src_path, REVERSE_ACTIONS['Updated'])

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
        source = os.path.abspath(event.src_path)
        target = os.path.abspath(event.dest_path)
        try:
            project = Project.get_by_id(self.project_id)
            source_file = File.get('one', File.project == project,
                                   File.path == source)
            project_path = os.path.abspath(project.path)
            if source_file is not None:
                # Case 1
                if target.startswith(project_path):
                    source_file.path = target
                    act_path = target
                    action = REVERSE_ACTIONS['Renamed to something']
                # Case 2
                else:
                    source_file.project_id = None
                    act_path = source
                    action = REVERSE_ACTIONS['Deleted']
                File.update(source_file)
                self._project_prototype(act_path, action)
            else:
                # Case 3
                if target.startswith(project_path):
                    action = REVERSE_ACTIONS['Created']
                    self._project_prototype(target, action)
                # Case 4, should never happen.
                else:
                    pass
        except Exception as excp:
            log_msg = ('Exception in Project file handler on_moved '
                       'callback: {exception!s}')
            log_msg = log_msg.format(exception=excp)
            _logger().exception(log_msg)
        #:TODO: If we implement expunge in Base, do it here for File
        #       in Finally: block.

    def _on_created_scanner(self, event):
        """
        On_created event handler for project scanned files.
        Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        try:
            project = Project.get_by_id(self.project_id)
            if not project.path:
                return
            file_path = event.src_path
            basename = os.path.basename(file_path)
            log_msg = 'On created at: {path} ({name})'
            log_msg = log_msg.format(path=project.path, name=basename)
            _logger().debug(log_msg)
            new_path = os.path.join(project.path, basename)
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
            self._project_prototype(new_path, REVERSE_ACTIONS['Created'])
        except Exception as excp:
            log_msg = 'Exception in SCAN HANDLER: {exception!s}'
            log_msg = log_msg.format(exception=excp)
            _logger().exception(log_msg)
