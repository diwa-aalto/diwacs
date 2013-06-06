"""
Created on 28.5.2012

:author: neriksso

"""
#import MySQLdb
from logging import config, getLogger
import os
import shutil
import sys
from time import sleep
sys.stdout = open(r'data\stdout.log', 'wb')
sys.stderr = open(r'data\stderr.log', 'wb')

# 3rd party imports
import pythoncom
from sqlalchemy import create_engine, exc, func, desc, sql
from sqlalchemy.orm import sessionmaker
from watchdog.events import FileSystemEventHandler

# Own imports
import diwavars
import filesystem
from models import (Action, Activity, Base, Company, Computer, Event, File,
                    FileAction, Project, Session)
import utils


config.fileConfig('logging.conf')
logger = getLogger('controller')

DATABASE = ('mysql+pymysql://username:password@192.168.1.10/DIWA' +
            '?charset=utf8&use_unicode=1')
ENGINE = create_engine(DATABASE, echo=True)
PROJECT_PATH = '\\\\' + diwavars.STORAGE + '\\Projects\\'
#PROJECT_PATH = 'C:\\Projects'
CS_TH = None
COMPUTER_INS = None
NODE_NAME = ""
NODE_SCREENS = 0
ACTIONS = {
                       1: "Created",
                       2: "Deleted",
                       3: "Updated",
                       4: "Renamed from something",
                       5: "Renamed to something",
                       6: "Opened",
                       7: "Closed",
            }


def SetLoggerLevel(level):
    logger.setLevel(level)


def UpdateStorage():
    global DATABASE
    if ((not diwavars.DB_TYPE) or (not diwavars.DB_ADDRESS) or
        (not diwavars.DB_NAME) or (not diwavars.DB_PASS) or
        (not diwavars.DB_USER)):
        return
    try:
        DATABASE = (
                    ('%s+%s://' % (diwavars.DB_TYPE,
                                   diwavars.DB_DRIVER[diwavars.DB_TYPE])) +
                    ('%s:%s@' % (diwavars.DB_USER, diwavars.DB_PASS)) +
                    diwavars.DB_ADDRESS + '/' + diwavars.DB_NAME +
                    '?charset=utf8&use_unicode=1'
                    )
        logger.debug('DB = ' + DATABASE)
    except Exception, e:
        logger.error('DATABASE ERROR: %s', str(e))
        raise Exception('EXIT')
    global ENGINE
    ENGINE = create_engine(DATABASE, echo=True)
    global PROJECT_PATH
    PROJECT_PATH = '\\\\' + diwavars.STORAGE + '\\Projects\\'


def SetNodeName(name):
    global NODE_NAME
    NODE_NAME = name


def SetNodeScreens(screens):
    global NODE_SCREENS
    NODE_SCREENS = screens


def CreateAll():
    """
    Create tables to the database.

    """
    try:
        db = ConnectToDatabase()
        db.execute('SET foreign_key_checks = 0')
        db.execute('DROP table IF EXISTS Action')
        db.execute('SET foreign_key_checks = 1')
        db.commit()
        Base.metadata.create_all(ENGINE)  # @UndefinedVariable
        for unused_x, y in ACTIONS.items():
            db.add(Action(y))
        db.commit()
        db.close()
    except Exception, e:
        logger.exception('CreateAll Exception: %s', str(e))


def ConnectToDatabase(expire=False):
    """
    Connect to the database and return a Session object.

    """
    S = sessionmaker(bind=ENGINE, expire_on_commit=expire)
    session = S()
    return session


def TestConnection():
    """
    Test the connection to database.

    :rtype: Boolean

    """
    try:
        db = ConnectToDatabase()
        db.query(Project).all()
        db.close()
        return True
    except:
        return False


def GetProjectPassword(project_id):
    """
    Returns the project password.

    :param project_id: ID of the project.
    :type project_id: Integer

    :rtype: String

    """
    myProject = GetProject(project_id)
    return myProject.password if myProject else ''


def GetProjectPath(project_id):
    """
    Fetches the project path from database and return it.

    :param project_id: Project id for database.
    :type project_id: Integer

    :rtype: String

    """
    try:
        db = ConnectToDatabase()
        path = db.query(Project.dir).filter(Project.id == project_id).one()[0]
    except:
        path = False
    db.close()
    return path if path else ''


def UnsetActivity(pgm_group):
    """
    Unsets activity for PGM Group.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    """
    db = ConnectToDatabase()
    for c in db.query(Activity).filter(Activity.active == pgm_group):
        c.active = False
    db.commit()
    db.close()


def GetLatestEvent():
    """
    Get the latest event.

    :rtype: :py:class:`models.Event`

    """
    try:
        db = ConnectToDatabase()
        event = db.query(Event.id).order_by(Event.id.desc()).first()
        db.close()
        return event[0] if event else 0
    except:
        return 0


def GetActiveActivity(pgm_group):
    """
    Get the latest active activity.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :rtype: :py:class:`models.Activity`

    """
    db = ConnectToDatabase()
    filtered = db.query(Activity).filter(Activity.active == pgm_group)
    act = filtered.order_by(desc(Activity.id)).first()
    db.close()
    return act.id if act else None


def GetActiveProject(pgm_group):
    """
    Get the active project.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :rtype: :py:class:`models.Activity`

    """
    activity = GetActiveActivity(pgm_group)
    if activity == None:
        return 0
    else:
        db = ConnectToDatabase()
        act = db.query(Activity).filter(Activity.id == activity)
        try:
            project = act.one().project
            db.close()
            return project.id
        except:
            return '0'


def GetActiveSession(pgm_group):
    """
    Get the active session.

    :param pgm_group: The PGM Group number.
    :type pgm_group: Integer

    :rtype: :py:class:`models.Session`

    """
    activity = GetActiveActivity(pgm_group)
    if activity == None:
        return 0
    else:
        db = ConnectToDatabase()
        session = db.query(Activity).filter(Activity.id == activity)
        session = session.one().session
        db.close()
        return session.id


def AddActivity(project_id, pgm_group, session_id=None, activity_id=None):
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
        db = ConnectToDatabase()
        project = db.query(Project).filter(Project.id == project_id).one()
        if session_id:
            session = db.query(Session).filter(Session.id == session_id).one()
        else:
            session = None
        act = None
        if activity_id:
            act = db.query(Activity).filter(Activity.id == activity_id).one()
            act.project = project
            act.session = session
            act.active = pgm_group
        else:
            act = Activity(project, session)
        db.add(act)
        db.commit()
        db.expunge(act)
        db.close()
        return act.id
    except Exception, e:
        logger.exception('AddActivity exception %s', str(e))
        return 0


def GetProjectIdByActivity(activity):
    db = ConnectToDatabase()
    act = db.query(Activity).filter(Activity.id == activity).one()
    db.close()
    return act.project_id if act.project_id else 0


def GetSessionIdByActivity(activity):
    db = ConnectToDatabase()
    act = db.query(Activity).filter(Activity.id == activity).one()
    db.close()
    return act.session_id if act.session_id else 0


def AddProject(data):
    """Adds a project to database and returns a  project instance

    :param data:  Project information
    :type data: A dictionary
    :rtype: an instance of :class:`models.Project`

    """
    try:
        logger.debug("Adding project")
        db = ConnectToDatabase()
        name = data["project"]["name"]
        directory = data["project"]["dir"]
        password = data["project"]["password"]
        if password:
            password = utils.HashPassword(password)
            directory = utils.GetEncryptedDirName(name, password)
        company = db.query(Company).filter(
                        Company.name.contains('%s' % data['company']['name'])
                        ).first()
        project = Project(name=name, company=company, password=password)
        db.add(project)
        db.commit()
        if directory:
            project.dir = filesystem.CreateProjectDir(directory)
        else:
            project.dir = filesystem.CreateProjectDir(project.id)
        db.commit()
        db.close()
        return project
    except:
        logger.exception("Add project exception")
        return None


def CheckPassword(project_id, password):
    db = ConnectToDatabase()
    project_hash = db.query(Project.password).filter_by(id=project_id).one()[0]
    db.close()
    if not project_hash or project_hash == utils.HashPassword(password):
        return True
    else:
        return False


def DeleteRecord(Model, idNum):
    """ Delete a record from database

    :param Model: The model for which to delete a record.
    :type Model: :func:`sqlalchemy.ext.declarative.declarative_base`.
    :param idNum: Recond id.
    :type idNum: Integer.

    """
    try:
        db = ConnectToDatabase()
        record = db.query(Model).filter_by(id=idNum).one()
        if Model == Project:
            for session in record.sessions:
                logger.debug(session)
                db.delete(session)
            db.execute("Delete from activity where project_id=%d" % idNum)

        db.delete(record)
        db.commit()
        db.close()
        return True
    except:
        logger.exception("Delete record exception model %s id %d." % (Model,
                                                                      idNum))
        return False


def LastActiveComputer():
    db = ConnectToDatabase()
    pcs = db.query(Computer.id).filter(func.timestampdiff(sql.text('second'),
                                                          Computer.time,
                                                          func.now()) < 10
                                       ).count()
    db.close()
    return pcs < 2


def GetActiveComputers(timeout):
    logger.debug('GetActiveComputers called with timeout %d', int(timeout))
    if timeout:
        db = ConnectToDatabase()
        pcs = (db.query(Computer.wos_id, Computer.screens, Computer.name)
                       ).filter(func.timestampdiff(sql.text('second'),
                                                   Computer.time,
                                                   func.now()) < timeout).all()
        db.close()
        return pcs
    return []


def EditProject(idNum, row):
    """ Update a project info

    :param idNum: Database id number of the project.
    :type idNum: Integer.
    :param row: The new project information.
    :type row: A dictionary

    """
    try:
        db = ConnectToDatabase()
        record = db.query(Project).filter_by(id=idNum).one()
        record.name = row["name"]
        record.dir = row["dir"]
        db.add(record)
        db.commit()
        db.close()
    except:
        logger.exception("EditProject exception")


def GetProject(project_id):
    """
    Fetches projects by a company.

    :param company_id: A company id from database.
    :type company_id: Integer.

    """
    try:
        db = ConnectToDatabase()
        project = db.query(Project).filter(Project.id == project_id).one()
        db.close()
        return project
    except:
        return None


def GetProjectsByCompany(company_id):
    """
    Fetches projects by a company.

    :param company_id: A company id from database.
    :type company_id: Integer.

    """
    db = ConnectToDatabase()
    projects = (db.query(Project).filter(Project.company_id == company_id)
                ).order_by(Project.name).all()
    db.close()
    return projects


def GetSessionsByProject(project_id):
    """ Fetches sessions for a project.

    :param project_id: Project id from database.
    :type project_id: Integer.

    """
    db = ConnectToDatabase()
    sessions = db.query(Session).filter(Session.project_id == project_id).all()
    db.close()
    return sessions


def StartNewSession(project_id, session_id=None, old_session_id=None):
    """Creates a session to the database and return a session object.

    :param project_id: Project id from database.
    :type project_id: Integer.
    :param session_id: an existing session id from database.
    :type session_id: Integer.
    :param old_session_id: A session id of a session which will be continued.
    :type old_session_id: Integer.

    """
    db = ConnectToDatabase(True)
    project = None
    try:
        project = db.query(Project).filter(Project.id == project_id).one()
    except:
        return None
    """recent_path = os.path.join(os.getenv('APPDATA'),
                               'Microsoft\\Windows\\Recent')"""
    session = None
    if session_id:
        try:
            session = db.query(Session).filter(Session.id == session_id).one()
        except:
            session = None
    else:
        session = Session(project)
        #initial add and commit
        db.add(session)
        db.commit()
        if old_session_id:
            #link two sessions together
            old_session = db.query(Session).filter(Session.id ==
                                                   old_session_id).one()
            session.previous_session = old_session
            old_session.next_session = session
            db.add(session)
            db.add(old_session)
            db.commit()

    db.expunge(session)
    db.close()
    return session


def EndSession(session_id):
    """Ends a session, sets its endtime to database. Ends file scanner.

    :param session: Current session.
    :type session: :py:class:`models.Session`

    """
    try:
        db = ConnectToDatabase(True)
        #db.add(session)
        session = db.query(Session).filter(Session.id == session_id).one()
        db.add(session)
        session.endtime = sql.func.now()
        db.commit()
        db.close()
    except Exception, e:
        logger.exception('EndSession exception %s', str(e))


def AddEvent(session_id, title, desc):
    """ Adds an event to the database.

    :param session: The current session.
    :type session: :class:`models.Session`
    :param desc: Description of the event.
    :type desc: String.

    """
    try:
        db = ConnectToDatabase(True)
        if session_id:
            session = db.query(Session).filter(Session.id ==
                                               session_id).one()
        else:
            session = None
        event = Event(desc=desc, session=session, title=title)
        db.add(event)
        db.commit()
        ide = event.id
        db.close()
        logger.debug('AddEvent complete')
        return ide
    except:
        logger.exception('AddEvent exception')


def AddComputer(name, ip, wos_id):
    try:
        global COMPUTER_INS
        db = ConnectToDatabase(True)
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        wanted_mac = utils.GetMacForIp(ip)
        ip_int = utils.DottedIPToInt(ip)
        if wanted_mac:
            c = db.query(Computer).filter_by(mac=wanted_mac)
            c = c.order_by(desc(Computer.id)).first()
            if c:
                c.name = name
                c.ip = ip_int
                c.wos_id = wos_id
                db.add(c)
                db.commit()
        else:
            c = None
        if not c:
            logger.debug("no computer instance  found")
            c = Computer(ip=ip_int, name=name, mac=wanted_mac, wos_id=wos_id)
            db.add(c)
            db.commit()
        db.expunge(c)
        db.close()
    except Exception, e:
        logger.exception("AddComputer exception: %s", str(e))
    return c


def GetActiveResponsiveNodes(pgm_group):
    nodes = []
    try:
        db = ConnectToDatabase()
        nodes = db.query(Computer.wos_id).filter(
                                        func.timestampdiff(sql.text('second'),
                                                           Computer.time,
                                                           func.now()
                                        ) < 10,
                                        Computer.responsive == pgm_group
                        ).order_by(Computer.wos_id).all()
        db.close()
    except:
        logger.debug("GetActiveResponsiveNodes exception")
    return nodes


def RefreshComputer(computer):
    try:
        db = ConnectToDatabase()
        db.add(computer)
        computer.time = sql.func.now()
        computer.responsive = diwavars.RESPONSIVE
        computer.name = NODE_NAME
        computer.screens = NODE_SCREENS
        db.commit()
        db.expunge(computer)
        db.close()
    except exc.DBAPIError:
        db.expunge(computer)
        db.close()
        raise
        logger.debug('exc.DBAPIError detected')
        #pub.sendMessage("connection_error",error=True)
    except Exception as e:
        logger.exception('refreshcomputer exception:%s', str(e))
    return computer


def AddComputerToSession(session, name, ip, wos_id):
    """Adds a computer to a session.

    :param session: A current session.
    :type session: :class:`models.Session`
    :param name: A name of the computer.
    :type name: String.
    :param ip: Computers IP address.
    :type ip: Integer.
    :param wos_id: Wos id of the computer.
    :type wos_id: Integer.

    """
    global COMPUTER_INS
    try:
        db = ConnectToDatabase(True)
        db.add(session)
        c = AddComputer(name, ip, wos_id)
        db.add(c)
        session.computers.append(c)
        #db.add(session)
        db.commit()
        db.expunge(session)
        db.expunge(c)
        COMPUTER_INS = c
        db.close()
    except Exception, e:
        logger.debug("Exception in AddComputerToSession: %s", str(e))


def GetOrCreate(session, model, **kwargs):
    """Fetches or creates a instance.

    :param session: a related session.
    :type session: :class:`models.Session`
    :param model: The model of which an instance is wanted.
    :type  model: :func:`sqlalchemy.ext.declarative.declarative_base`

     """
    instance = session.query(model).filter_by(**kwargs)
    instance = instance.order_by(desc(model.id)).first()
    if instance:
        return instance
    else:
        if 'path' in kwargs and 'project_id' in kwargs:
            project = session.query(Project).filter(
                            Project.id == kwargs['project_id']).one()
            instance = File(path=kwargs['path'], project=project)
            session.add(instance)
            session.commit()
            return instance
        instance = model(**kwargs)
        return instance


def GetRecentFiles(project_id):
    """Fetches files accessed recently in the project sessions from the
    database.

    .. todo::  Add a limit parameter, currently fetches all files.

    .. todo:: Duplicate check.

    :param project_id: The project id
    :type project_id: Integer.
    :rtype: a list of files

    """
    db = ConnectToDatabase()
    files = db.query(File.path, FileAction.action_time).filter(
                                File.project_id == project_id,
                                File.id == FileAction.file_id
                                ).order_by(desc(FileAction.action_time))
    files = files.group_by(File.path).all()
    db.close()
    return files


def InitSyncProjectDir(project_id):
    """
    Initial sync of project dir and database.

    :param project_id: Project id from database.
    :type project_id: Integer.

    """
    try:
        db = ConnectToDatabase()
        myqr = db.query(File.path).filter(File.project_id == project_id).all()
        project_files = list(set(myqr))
        project_path = GetProjectPath(project_id)
        for root, unused_dirs, files in os.walk(project_path):
            for f in files:
                if (os.path.join(root, f),) not in project_files:
                    AddFileToProject(os.path.join(root, f), project_id)
                else:
                    project_files.remove((os.path.join(root, f),))
        for f in project_files:
            files = db.query(File).filter(File.path == f[0],
                                          File.project_id == project_id).all()
            for ff in files:
                ff.project = None
                db.add(ff)
        db.commit()
        db.close()
    except Exception, e:
        logger.exception('Init sync project dir error: %s', str(e))


def AddFileToProject(filepath, project_id):
    """Add a file to project. Copies it to the folder and adds a record to
    database.

    :param filepath: A filepath.
    :type filepath: String
    :param project_id: Project id from database.
    :type projecT_id: Integer.
    :return: New filepath.
    :rtype: String

    """
    if not project_id:
        f = filesystem.CopyFileToProject(filepath, project_id)
        return f if f else ''
    try:
        db = ConnectToDatabase()
        project = db.query(Project).filter(Project.id == project_id).one()
        newpath = filesystem.CopyFileToProject(filepath, project_id)
        if newpath:
            f = File(path=newpath, project=project)
            db.add(f)
            db.commit()
            db.close()
        return newpath
    except Exception, e:
        logger.exception('Add file to project(%s) exception: %s',
                         str(project_id), str(e))
        return ""


def IsProjectFile(filename, project_id):
    """Checks, if a file belongs to a project. Checks both project folder
    and database.

    :param filename: a filepath.
    :type filename: String.
    :param project_id: Project id from database.
    :type project_id: Integer.
    :rtype: Boolean

    """
    try:
        if isinstance(filename, str):
            filename = unicode(filename, errors='replace')
        db = ConnectToDatabase()
        basename = os.path.basename(filename)
        if isinstance(basename, str):
            basename = unicode(basename, errors='replace')
        logger.debug("IsProjectFile %s %s" % (str(type(filename)), filename))
        files = db.query(File.path).filter(File.project_id == project_id,
                                           File.path.like(u'%' + basename)
                                           ).order_by(desc(File.id)).all()
        db.close()
    except Exception, e:
        logger.exception("IsProjectFile query exception: %s", str(e))
        files = []
    for f in files:
        filebase = os.path.basename(f[0])
        if isinstance(filebase, str):
            filebase = unicode(filebase, errors='replace')
        if filebase == basename:
            return f[0]
    f = filesystem.SearchFile(os.path.basename(filename),
                              GetProjectPath(project_id))
    if f:
        return AddFileToProject(f, project_id)
    return ''


def GetFilePath(project_id, filename):
    f = IsProjectFile(filename, project_id)
    if f:
        return f
    return False


def CreateFileaction(path, action, session_id, project_id):
    """Logs a file action to the database.

    :param path: Filepath.
    :type path: String.
    :param action: File action id.
    :type action: Integer.
    :param session_id: Current session id.
    :type session_id: Integer.
    :param project_id: Project id from database.
    :type project_id: Integer.

    """
    global COMPUTER_INS
    db = ConnectToDatabase()
    project_file = IsProjectFile(path, project_id)
    if project_file:
        fi = GetOrCreate(db, File, path=project_file)
    else:
        fi = GetOrCreate(db, File, path=path)

    a = db.query(Action).filter(Action.id == action).one()
    if session_id > 0:
        session = db.query(Session).filter(Session.id == session_id).one()
    else:
        session = None
    fa = FileAction(fi, a, session)
    db.add(fi)
    db.add(fa)
    db.commit()
    db.close()


class SCAN_HANDLER(FileSystemEventHandler):
    """ Handler for FileSystem events on SCANNING folder.

    :param project_id: Project id from database.
    :type project_id: Integer.

    """
    def __init__(self, project_id):
        self.project_id = project_id
        logger.debug('SCAN_HANDLER initialized for project: %d' % project_id)

    def on_created(self, event):
        """
        On_created event handler. Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        try:
            project_path = GetProjectPath(self.project_id)
            if not project_path:
                return
            logger.debug('on_created at: %s (%s)' % (project_path,
                                os.path.basename(event.src_path)))
            new_path = os.path.join(project_path,
                                    os.path.basename(event.src_path))
            if 'Scan' in event.src_path:
                sleep(60)
            shutil.copy2(event.src_path, new_path)
            db = ConnectToDatabase()
            proj = db.query(Project).filter(Project.id ==
                                            self.project_id).one()
            logger.debug('File(%s, %s)' % (new_path, str(proj)))
            f = File(path=new_path, project=proj)
            fa = FileAction(file=f, action=db.query(Action).filter(Action.id ==
                                                                   1).one())
            logger.debug('FileAction: %s', str(fa))
            db.add(f)
            db.add(fa)
            db.commit()
            db.close()
        except Exception, e:
            logger.exception('Exception in SCAN HANDLER:%s', str(e))


class PROJECT_FILE_EVENT_HANDLER(FileSystemEventHandler):
    """ Handler for FileSystem events on project folder.

    :param project_id: Project id from database.
    :type project_id: Integer.

    """
    def __init__(self, project_id):
        self.project_id = project_id

    def on_created(self, event):
        """On_created event handler. Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        try:
            db = ConnectToDatabase()
            logger.debug("PROJECT FILE CREATED %s %s" %
                         (str(type(event.src_path)), event.src_path))
            proj = db.query(Project).filter(Project.id ==
                                            self.project_id).one()
            logger.debug("Adding to project: %s" % str(proj))
            f = File(path=event.src_path, project=proj)
            logger.debug("File: %s" % str(f))
            fa = FileAction(filename=f,
                            action=db.query(Action).filter(Action.id ==
                                                           1).one())
            logger.debug("FileAction: %s" % str(f))
            db.merge(f)
            db.merge(fa)
            db.commit()
            db.close()
        except:
            logger.exception("Project file scanner on_created exception")

    def on_deleted(self, event):
        """On_deleted event handler. Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        try:
            db = ConnectToDatabase()
            f = db.query(File).filter(File.path == event.src_path,
                                      File.project_id == self.project_id
                                      ).order_by(File.id.desc()).first()
            fa = FileAction(filename=f,
                            action=db.query(Action).filter(Action.id ==
                                                           2).one())
            f.project = None
            db.merge(f)
            db.merge(fa)
            db.commit()
            db.close()
        except:
            logger.exception("Project file scanner on_deleted exception")

    def on_modified(self, event):
        """On_modified event handler. Logs to database.

        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`

        """
        try:
            db = ConnectToDatabase()
            logger.debug('on_modified(%s)' % str(event))
            f = db.query(File).filter(File.path == event.src_path,
                                      File.project_id == self.project_id
                                      ).order_by(File.id.desc()).first()
            logger.debug('on_modified - query = %s', str(f))
            if not f:
                f = self.on_created(event)
                logger.debub('on_created result: ' % str(f))
            fa = FileAction(filename=f,
                            action=db.query(Action).filter(Action.id ==
                                                           3).one())
            logger.debug('on_modified - fileaction = %s', str(fa))
            db.merge(f)
            db.merge(fa)
            db.commit()
            db.close()
        except Exception, e:
            logger.exception("Project file scanner on_modifed exception: %s",
                             str(e))
