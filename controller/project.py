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
from modelsbase import ItemAlreadyExistsException
from models import (Action, Activity, Company, File, FileAction, Project,
                    Session)
import utils
import models
import modelsbase


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


def add_file_to_project(filepath, project_id):
    """
    Add a file to project. Copies it to the folder and adds a record to
    database.

    :param filepath: A filepath.
    :type filepath: String

    :param project_id: Project id from database.
    :type projecT_id: Integer

    :return: New filepath.
    :rtype: String

    """
    if File.get('exists', File.path == filepath):
        return
    project = Project.get_by_id(project_id)
    try:
        newpath = filesystem.copy_file_to_project(filepath, project_id)
        if newpath:
            File(path=newpath, project=project)
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
    _logger().debug('<{0}: {1}>'.format(type(project_name).__name__,
                                        str(project_name)))
    _logger().debug('[{0}: {1}]'.format(type(Project.name).__name__,
                                        str(Project.name)))
    expression = (Project.name == project_name)
    _logger().debug('"{0}: {1}"'.format(type(expression).__name__,
                                        str(expression)))
    exists = Project.get('exists', expression)
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
        password = utils.hash_password(password)
        directory = utils.get_encrypted_directory_name(name, password)
        directory_set = True
    if not directory_set:
        return None
    _logger().debug('Adding project: {name}'.format(name=name))
    project = Project(name=name, company=company, password=password)
    if directory:
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
    Docstring here.

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
    project_file = is_project_file(path, project_id)
    project_file = project_file if project_file else path
    kwargs = {'path': project_file, 'project_id': project_id}
    file_object = controller.common.get_or_create(File, **kwargs)
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
    return activity.project if activity else 0


def get_project_id_by_activity(activity_id):
    """
    Docstring here.

    """
    activity = Activity.get_by_id(activity_id)
    return activity.project_id if activity else 0


def get_projects_by_company(company_id):
    """
    Fetches projects by a company.

    :param company_id: A company id from database.
    :type company_id: Integer

    """
    projects = Project.get('all', Project.company_id == company_id)
    projects.sort(key=str)
    return projects


def get_recent_files(project_id, max_files_count=None):
    """
    Fetches files accessed recently in the project sessions from the database.

    .. versionadded:: 0.9.3.0
        Added a limit parameter, limits the number of returned results.

    .. note::
        Duplicate check has been added at some point in time.

    :param project_id: The project id
    :type project_id: Integer

    :returns:
        The list of filepaths that have recently been used in this project.
    :rtype: List of String

    """
    database = None
    result = []
    try:
        database = models.connect_to_database()
        my_query = database.query(File.path, FileAction.action_time)
        files = my_query.filter(File.project_id == project_id,
                                File.id == FileAction.file_id)
        files = files.order_by(sqlalchemy.desc(FileAction.action_time))
        files = files.group_by(File.path)
        if max_files_count and type(max_files_count) == int:
            files = files.limit(max_files_count)
        result = files.all()
    except SQLAlchemyError:
        pass
    if database:
        database.close()
    return result


def edit_project(project_id, row):
    """
    Update the project info.

    :param project_id: Database id number of the project.
    :type project_id: Integer

    :param row: The new project information.
    :type row: A dictionary

    """
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
            deleted = modelsbase.REVERSE_ACTIONS['Deleted']
            controller.create_file_action(file_.path, deleted, 0, project_id)
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
    project = Project.get_by_id(project_id)
    if File.get('exists', File.path == fileabs, File.project_id == project_id):
        return True
    file_project_path = filesystem.search_file(filebase, project.path)
    if file_project_path:
        try:
            file_ = File(file_project_path, project)
            return file_.path
        except (ItemAlreadyExistsException, SQLAlchemyError):
            pass
    return ''
