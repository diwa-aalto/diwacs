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

# Own imports.
import controller.activity
import filesystem
from models import (Action, Activity, Company, File, FileAction, Project,
                    Session)
import utils


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
    if not project_id:
        return filesystem.copy_file_to_project(filepath, 0)
    path = ''
    database = None
    try:
        database = controller.common.connect_to_database()
        project = database.query(Project).filter(Project.id == project_id)
        project = project.one()
        if not project:
            database.close()
            return ''
        newpath = filesystem.copy_file_to_project(filepath, project_id)
        if newpath:
            project_file = File(path=newpath, project=project)
            database.add(project_file)
            database.commit()
        path = newpath
    except sqlalchemy.exc.SQLAlchemyError as excp:
        logmsg = 'Add file to project(%d) exception: %s'
        _logger().exception(logmsg, (project_id, str(excp)))
    if database:
        database.close()
    return path


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
    database = None
    result = None
    try:
        database = controller.common.connect_to_database()
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
            database.close()
            return None
        _logger().debug('Adding project: %s', name)
        company = database.query(Company)
        company_name_filter = Company.name.contains(company_data['name'])
        company = company.filter(company_name_filter).one()
        project = Project(name=name, company=company, password=password)
        if directory:
            project.dir = filesystem.create_project_directory(directory)
        else:
            project.dir = filesystem.create_project_directory(str(project.id))
        if not project.dir:
            del project
            database.close()
            return None
        database.add(project)
        database.commit()
        result = project
    except sqlalchemy.exc.SQLAlchemyError:
        _logger().exception('Add project exception')
    if database:
        database.close()
    return result


def check_password(project_id, password):
    """
    Docstring here.

    """
    project_password = get_project_password(project_id)
    if not project_password:
        return True
    return project_password == utils.hash_password(password)


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
    database = None

    file_object = None
    try:
        database = controller.common.connect_to_database()
        if project_file:
            file_object = controller.common.get_or_create(database, File,
                                                          path=project_file)
        else:
            file_object = controller.common.get_or_create(database, File,
                                                          path=path)
    except sqlalchemy.exc.SQLAlchemyError:
        database.close()
        return

    try:
        action_object = database.query(Action).filter(Action.id == action_id)
        action_object = action_object.one()
        session_object = None
        if session_id > 0:
            session_object = database.query(Session)
            session_object = session_object.filter(Session.id == session_id)
            session_object = session_object.one()
        file_action_object = FileAction(file_object, action_object,
                                        session_object)
        database.add(file_object)
        database.add(file_action_object)
        database.commit()
    except sqlalchemy.exc.SQLAlchemyError as excp:
        database.close()
        _logger().exception('Failed to create FileAction: %s', str(excp))
    database.close()


def get_active_project(pgm_group):
    """
    Get the active project.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :returns: Active project ID.
    :rtype: Integer

    """
    activity_id = controller.activity.get_active_activity(pgm_group)
    if activity_id == None:
        return None
    else:
        database = controller.common.connect_to_database()
        result = None
        try:
            activity = database.query(Activity)
            activity = activity.filter(Activity.id == activity_id)
            activity = activity.one()
            project = activity.project
            result = project.id
        except sqlalchemy.exc.SQLAlchemyError:
            pass
        if database:
            database.close()
        return result


def get_file_path(project_id, filename):
    """
    Returns the filepath for filename.

    :returns: Filepath.
    :rtype: String

    """
    filepath = is_project_file(filename, project_id)
    if filepath:
        return filepath
    return False


def get_project(project_id):
    """
    Fetches projects by a company.

    :param company_id: A company id from database.
    :type company_id: Integer

    """
    database = None
    result = None
    try:
        database = controller.common.connect_to_database()
        project = database.query(Project)
        project = project.filter(Project.id == project_id)
        result = project.one()
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
    return result


def get_project_id_by_activity(activity_id):
    """
    Docstring here.

    """
    result = 0
    try:
        database = controller.common.connect_to_database()
        act = database.query(Activity).filter(Activity.id == activity_id).one()
        database.close()
        if act.project_id:
            result = act.project_id
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    return result


def get_project_password(project_id):
    """
    Returns the project password.

    :param project_id: ID of the project.
    :type project_id: Integer

    :rtype: String

    """
    my_project = get_project(project_id)
    return my_project.password if my_project else ''


def get_project_path(project_id):
    """
    Fetches the project path from database and return it.

    :param project_id: Project id for database.
    :type project_id: Integer

    :rtype: String

    """
    my_project = get_project(project_id)
    return my_project.dir if my_project else ''


def get_projects_by_company(company_id):
    """
    Fetches projects by a company.

    :param company_id: A company id from database.
    :type company_id: Integer

    """
    database = None
    result = []
    try:
        database = controller.common.connect_to_database()
        projects = database.query(Project)
        projects = projects.filter(Project.company_id == company_id)
        projects = projects.order_by(Project.name).all()
        result = projects
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
    return result


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
        database = controller.common.connect_to_database()
        my_query = database.query(File.path, FileAction.action_time)
        files = my_query.filter(File.project_id == project_id,
                                File.id == FileAction.file_id)
        files = files.order_by(sqlalchemy.desc(FileAction.action_time))
        files = files.group_by(File.path)
        if max_files_count and type(max_files_count) == int:
            files = files.limit(max_files_count)
        result = files.all()
    except sqlalchemy.exc.SQLAlchemyError:
        pass
    if database:
        database.close()
    return result


def edit_project(id_number, row):
    """
    Update the project info.

    :param id_number: Database id number of the project.
    :type id_number: Integer

    :param row: The new project information.
    :type row: A dictionary

    """
    database = None
    try:
        database = controller.common.connect_to_database()
        record = database.query(Project).filter_by(id=id_number).one()
        needs_update = False
        if 'name' in row:
            record.name = row['name']
            needs_update = True
        if 'dir' in row:
            record.dir = row['dir']
            needs_update = True
        if 'password' in row:
            record.password = row['password']
            needs_update = True
        if needs_update:
            database.add(record)
            database.commit()
    except sqlalchemy.exc.SQLAlchemyError:
        _logger().exception('edit_project exception')
    if database:
        database.close()


def init_sync_project_directory(project_id):
    """
    Initial sync of project dir and database.

    :param project_id: Project id from database.
    :type project_id: Integer

    """
    database = None
    _logger().debug('init_sync_project_dir(%d)', project_id)
    if not project_id or project_id < 1:
        return
    try:
        database = controller.common.connect_to_database()
        my_query = database.query(File)
        project_files = my_query.filter(File.project_id == project_id).all()
        project_path = get_project_path(project_id)
        if not project_path:
            database.close()
            return
        _logger().debug('Project path: %s', project_path)
        project_filepaths = [project.path for project in project_files]
        for root, directories, files in os.walk(project_path):
            for filename in files:
                target_path = os.path.join(root, filename)
                if target_path not in project_filepaths:
                    add_file_to_project(target_path, project_id)
                else:
                    index = project_filepaths.index(target_path)
                    project_files.pop(index)
                    project_filepaths.pop(index)
        _logger().debug('Pathwalk complete!')
        project_filepaths = []
        # project_files now only contains the files that have been deleted!
        for file_ in project_files:
            file_.project_id = None
            database.add(file_)
        _logger().debug('Path processing complete.')
        database.commit()
    except sqlalchemy.exc.SQLAlchemyError as excp:
        _logger().exception('Init sync project dir error: %s', str(excp))
    if database:
        database.close()


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
    database = None
    try:
        if isinstance(filename, str):
            filename = unicode(filename, errors='replace')
        database = controller.common.connect_to_database()
        basename = os.path.basename(filename)
        if isinstance(basename, str):
            basename = unicode(basename, errors='replace')
        _logger().debug('is_project_file %s %s', str(type(filename)), filename)
        files = database.query(File)
        files = files.filter(File.project_id == project_id,
                             File.path.like(u'%' + basename))
        files = files.order_by(sqlalchemy.desc(File.id)).all()
    except sqlalchemy.exc.SQLAlchemyError as excp:
        _logger().exception('is_project_file query exception: %s', str(excp))
        files = []
    if database:
        database.close()
    for fileobject in files:
        filebase = os.path.basename(fileobject.path)
        if isinstance(filebase, str):
            filebase = unicode(filebase, errors='replace')
        if filebase == basename:
            return fileobject.path
    filebase = os.path.basename(filename)
    project_path = get_project_path(project_id)
    file_project_path = filesystem.search_file(filebase, project_path)
    if file_project_path:
        return add_file_to_project(file_project_path, project_id)
    return ''
