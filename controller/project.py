"""
Created on 28.6.2013

:author: neriksso

"""
# Critical import.
import controller.common

# System imports.
import os

# Third party imports.
import sqlalchemy
from sqlalchemy.exc import SQLAlchemyError

# Own imports.
import controller.activity
import filesystem
from modelsbase import (ItemAlreadyExistsException, connect_to_database,
                        REVERSE_ACTIONS)
from models import (Action, Activity, Company, File, FileAction, Project,
                    Session)
import utils
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


def add_file_to_project(file_path, project_id):
    """
    Add a file to project. Copies it to the folder and adds a record to
    database.

    :param file_path: A file_path.
    :type file_path: String

    :param project_id: Project id from database.
    :type projecT_id: Integer

    :return: New file_path.
    :rtype: String

    """
    if not file_path:
        return ''
    file_path = os.path.abspath(file_path)
    if File.get('exists', File.path == file_path, 
                           File.project_id == project_id):
        _logger().debug('Not adding file to project: File exists')
        return ''
    project = Project.get_by_id(project_id)
    try:
        if file_path.startswith(project.dir):
            newpath = file_path
        else:
            newpath = filesystem.copy_file_to_project(file_path, project_id)
        if newpath:
            try:
                File(newpath, project_id)
            except ItemAlreadyExistsException:
                pass
        return newpath
    except SQLAlchemyError as excp:
        log_msg = 'Add file to {project!s} exception: {exception!s}'
        log_msg = log_msg.format(project=project, exception=excp)
        _logger().exception(log_msg)
        return ''


def add_project(data):
    """
    Adds a project to database and returns a  project instance

    :param data:  Project information
    :type data: A dictionary

    :rtype: an instance of :class:`models.Project`

    """
    if 'project' not in data:
        return None
    if 'company' not in data:
        return None
    project_data = data['project']
    company_data = data['company']
    if ('name' not in project_data) or ('name' not in company_data):
        return None
    project_name = project_data['name']
    exists = Project.get('exists', Project.name == project_name)
    if exists:
        raise ItemAlreadyExistsException('The project exists already!')
    company = Company.get('one', Company.name == company_data['name'])
    # Parse data.
    name = project_data['name']
    directory = ''
    directory_set = False
    if 'dir' in project_data:
        directory = project_data['dir']
        directory_set = True
    password = ''
    if 'password' in project_data:
        password = project_data['password']
        if password:
            password = utils.hash_password(password)
            directory = utils.get_encrypted_directory_name(name, password)
            directory_set = True
    project = Project(name, '', company, password)
    if directory_set:
        project.dir = filesystem.create_project_directory(directory)
    else:
        project.dir = filesystem.create_project_directory(str(project.id))
    if not project.dir:
        project.delete()
        return None
    Project.update(project)
    return project


def check_password(project_id, password):
    """
    Check that the password is correct for accessing a given project.

    :note:
        This returns true also if the project does not have password
        specified as the project is public in that case. The password
        provided is ignored in this case.

    :param project_id: ID of the project.
    :type project_id: Integer

    :param password: Password to check.
    :type password: String

    :returns: Is the password authorized to access the project.
    :type: Boolean

    """
    project = Project.get_by_id(project_id)
    if not project.password:
        return True
    return project.password == utils.hash_password(password)


def create_file_action(path, action_id, session_id, project_id):
    """
    Logs a file action to the database.

    :param path: Filepath.
    :type path: String

    :param action_id: File action id.
    :type action_id: Integer

    :param session_id: Current session id.
    :type session_id: Integer

    :param project_id: Project id from database.
    :type project_id: Integer

    """
    args = (File.path == path,)
    kwargs = {'path': path, 'project_id': project_id}
    if is_project_file(path, project_id):
        args = args + (File.project_id == project_id,)
    file_object = controller.common.get_or_create(File, *args, **kwargs)
    action_object = Action.get_by_id(action_id)
    session_object = Session.get_by_id(session_id) if session_id > 0 else None
    return FileAction(file_object, action_object, session_object)


def get_active_project(pgm_group):
    """
    Get the active project.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :returns: Active project ID.
    :rtype: Integer

    """
    activity = controller.activity.get_active_activity(pgm_group)
    return activity.project_id if activity else 0


def get_project_id_by_activity(activity_id):
    """
    Get the project ID that this activity_id is a part of.

    :param activity_id: ID of the activity_id.
    :type activity_id: Integer

    :returns: The project ID.
    :rtype: Integer

    """
    try:
        activity = Activity.get_by_id(activity_id)
    except NoResultFound:
        return 0
    return activity.project_id if activity else 0


def get_projects_by_company(company_id):
    """
    Fetches projects by a company.

    :param company_id: A company id from database.
    :type company_id: Integer

    """
    projects = Project.get('all', Project.company_id == company_id)
    lower_case_sorter = lambda project: unicode(project).lower()
    projects.sort(key=lower_case_sorter)
    return projects


def edit_project(project_id, row):
    """
    Update the project info.

    :param project_id: Database id number of the project.
    :type project_id: Integer

    :param row: The new project information.
    :type row: A dictionary

    """  # TODO: Not called...
    project = Project.get_by_id(project_id)
    needs_to_update = False
    for key in row:
        try:
            setattr(project, key, row[key])
            needs_to_update = True
        except AttributeError as excp:
            log_msg = 'Attribute error in edit_project: {exception}'
            log_msg = log_msg.format(exception=excp)
            _logger().exception(log_msg)
    if needs_to_update:
        project.update()


def init_sync_project_directory(project_id):
    """
    Initial sync of project dir and database.

    :param project_id: Project id from database.
    :type project_id: Integer

    """
    log_msg = 'init_sync_project_directory project ID = {project_id}'
    log_msg = log_msg.format(project_id=project_id)
    _logger().debug(log_msg)
    project = Project.get_by_id(project_id)
    if not project:
        return
    project_files = File.get('all', File.project_id == project_id)
    project_filepaths = [f.path for f in project_files]
    try:
        for (root, directories, basenames) in os.walk(project.dir):
            for filepath in [os.path.join(root, n) for n in basenames]:
                if filepath in project_filepaths:
                    # Simultaneously remove the element from both lists.
                    index = project_filepaths.index(filepath)
                    project_files.pop(index)
                    project_filepaths.pop(index)
                else:
                    # Add the new file to project.
                    add_file_to_project(filepath, project_id)
        # project_files now only contains the files that have been deleted!
        for file_ in project_files:
            deleted = REVERSE_ACTIONS['Deleted']
            try:
                controller.create_file_action(file_.path, deleted, 0,
                                              project_id)
            except Exception as excp:
                _logger().exception('{0!s}'.format(excp))
            file_.project_id = None
        File.update_many(project_files)
    except OSError as excp:
        log_msg = ('Exception in Initial project directory synchronization '
                   'call: {exception!s}')
        log_msg = log_msg.format(exception=excp)
        _logger().exception(log_msg)


def is_project_file(filename, project_id):
    """
    Checks, if a file belongs to a project. Checks both project folder
    and database.

    :param filename: a filepath.
    :type filename: String

    :param project_id: Project id from database.
    :type project_id: Integer

    :rtype: Boolean

    """
    filebase = os.path.basename(filename)
    fileabs = os.path.abspath(filename)
    if File.get('exists', File.path == fileabs, File.project_id == project_id):
        return True
    project = Project.get_by_id(project_id)
    file_project_path = filesystem.search_file(filebase, project.dir)
    project = None
    if file_project_path:
        try:
            File(file_project_path, project_id)
            return True
        except (ItemAlreadyExistsException, SQLAlchemyError):
            pass
    return False
