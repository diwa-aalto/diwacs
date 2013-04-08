'''
Created on 28.5.2012

@author: neriksso
'''
import MySQLdb
import sys
sys.stdout = open("data\stdout.log", "wb")
sys.stderr = open("data\stderr.log", "wb")  
from models import *
from sqlalchemy import create_engine,func, sql,desc,or_
from sqlalchemy.orm import sessionmaker
from sqlalchemy import exc
import time
from pubsub import pub
import utils
import csv
import watchdog
import shutil
import datetime
import socket
from watchdog.events import FileSystemEventHandler
import logging
import logging.config
logging.config.fileConfig('logging.conf')
logger = logging.getLogger('controller')
STORAGE = "192.168.1.10"
DATABASE = 'mysql+pymysql://wazzuup:serval@'+STORAGE+'/WZP'
ENGINE = create_engine(DATABASE, echo=True) 
PROJECT_PATH = '\\\\'+STORAGE+'\\Projects\\'
#PROJECT_PATH = 'C:\\Projects'
SCANNER_TH = None
CS_TH = None
COMPUTER_INS = None
IS_RESPONSIVE = False
ACTIONS = {
                       1 : "Created",
                       2 : "Deleted",
                       3 : "Updated",
                       4 : "Renamed from something",
                       5 : "Renamed to something",
                       6 : "Opened",
                       7 : "Closed",
            }
def SetLoggerLevel(level):
    logger.setLevel(level)
    
def UpdateStorage(storage):
    global STORAGE
    STORAGE = storage
    global DATABASE
    DATABASE = 'mysql+pymysql://wazzuup:serval@'+STORAGE+'/WZP'
    global ENGINE
    ENGINE = create_engine(DATABASE, echo=True) 
    global PROJECT_PATH
    PROJECT_PATH = '\\\\'+STORAGE+'\\Projects\\'
def SetIsResponsive(responsive):
    global IS_RESPONSIVE
    IS_RESPONSIVE = responsive
def CreateAll():
    """Create tables to the database"""
    try:
        db = ConnectToDatabase()
        db.execute('SET foreign_key_checks = 0')
        db.execute('DROP table IF EXISTS Action')
        db.execute('SET foreign_key_checks = 1')
        db.commit()
        Base.metadata.create_all(ENGINE)    
        for x,y in ACTIONS.items(): db.add(Action(y))
        db.commit()    
        db.close()
    except Exception, e:
        logger.exception('CreateAll Exception')   

def ConnectToDatabase(expire=False):
    """ Connect to the database and return a Session object
    """ 
    S = sessionmaker(bind=ENGINE,expire_on_commit=expire)
    session = S()
    return session

def TestConnection():
    try:
        db = ConnectToDatabase()
        db.query(Project).all()
        db.close()
        return True
    except:
        return False
    
def GetProjectPath(project_id):
    """Fetches the project path from database and return it.
    
    :param project_id: Project id for database.
    :type project_id: Integer.
    :rtype: String.
    
    """
    try:
        db = ConnectToDatabase()
        path = db.query(Project.dir).filter(Project.id==project_id).one()[0]
    except:
        path = False
    db.close()
    return '' if not path else path

def UnsetActivity():
    db = ConnectToDatabase()
    for c in db.query(Activity).filter(Activity.active==True):
        c.active = False
    db.commit()
    db.close()
    
def GetLatestEvent():
    db = ConnectToDatabase()
    event = db.query(Event.id).order_by(Event.id.desc()).first()
    db.close()
    return event[0] if event else 0
    
def GetActiveActivity():
    db = ConnectToDatabase()
    act = db.query(Activity).filter(Activity.active==True).order_by(desc(Activity.id)).first()
    logger.debug("Active activity: %s",str(act.id) if act else "None")
    db.close()
    return act.id if act else None
   
def AddActivity(project_id,session_id=None,act_id=None):
    try:
        db = ConnectToDatabase()
        project = db.query(Project).filter(Project.id==project_id).one()
        if session_id:
            session = db.query(Session).filter(Session.id==session_id).one()
        else:
            session = None    
        if not act_id:
                act = Activity(project,session)
        else:
            act = db.query(Activity).filter(Activity.id==act_id).one()
            act.project = project
            act.session = session
              
        db.add(act)
        db.commit()
        db.expunge(act)
        db.close()
        return act.id
    except Exception,e:
        logger.exception('AddActivity exception')   
        return 0
    
def GetProjectIdByActivity(activity):
    db = ConnectToDatabase()
    act = db.query(Activity).filter(Activity.id==activity).one()
    db.close()
    return act.project_id if act.project_id else 0

def GetSessionIdByActivity(activity):
    db = ConnectToDatabase()
    act = db.query(Activity).filter(Activity.id==activity).one()
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
        dir = data["project"]["dir"]
        password = data["project"]["password"]
        company = db.query(Company).filter(Company.name.contains('%s' % data['company']['name'])).first()
        project = Project(name=name,company=company,password=password)
        db.add(project)
        db.commit()
        if dir:
            project.dir = utils.CreateProjectDir(dir)
        else:
            project.dir = utils.CreateProjectDir(project.id)
        db.commit()
        db.close()
        return project
    except:
        logger.exception("Add project exception")
        return None

def CheckPassword(project_id,password):
    db = ConnectToDatabase()
    project_hash = db.query(Project.password).filter_by(id=project_id).one()[0]
    db.close()
    if not project_hash or project_hash == utils.HashPassword(password):
        return True
    else:
        return False
    
def DeleteRecord(Model,idNum):
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
            db.execute("Delete from activity where project_id=%d"%idNum)
                    
        db.delete(record)
        db.commit()
        db.close()
        return True
    except:
        logger.exception("Delete record exception model %s id %d." % (Model,idNum))
        return False

def LastActiveComputer():    
        db = ConnectToDatabase()
        pcs = db.query(Computer.id).filter(func.timestampdiff(sql.text('second'),Computer.time,func.now())<10).count();
        db.close()
        return pcs < 2 
     
def GetActiveComputers(timeout):
    logger.debug('GetActiveComputers called with timeout %d',int(timeout))
    if timeout:
        db = ConnectToDatabase()
        pcs = db.query(Computer.wos_id,Computer.screens,Computer.name).filter(func.timestampdiff(sql.text('second'),Computer.time,func.now())<timeout).all();
        db.close()
        return pcs
    return [] 
  
def EditProject(idNum, row):
    """Update a project info
    
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
    """Fetches projects by a company.
    
    :param company_id: A company id from database.
    :type company_id: Integer.
    
    """
    db = ConnectToDatabase()
    project = db.query(Project).filter(Project.id==project_id).one()
    db.close()
    return project 
        
def GetProjectsByCompany(company_id):
    """Fetches projects by a company.
    
    :param company_id: A company id from database.
    :type company_id: Integer.
    
    """
    db = ConnectToDatabase()
    projects = db.query(Project).filter(Project.company_id==company_id).order_by(Project.name).all()
    db.close()
    return projects 

def GetSessionsByProject(project_id):
    """ Fetches sessions for a project.
    
    :param project_id: Project id from database.
    :type project_id: Integer.
    
    """
    db = ConnectToDatabase()
    sessions = db.query(Session).filter(Session.project_id==project_id).all()
    db.close()
    return sessions  

def StartNewSession(project_id,session_id=None,old_session_id=None):
    """Creates a session to the database and return a session object.
    
    :param project_id: Project id from database.
    :type project_id: Integer.
    :param session_id: an existing session id from database.
    :type session_id: Integer.
    :param old_session_id: A session id of a session which will be continued.
    :type old_session_id: Integer.
    
    """
    db = ConnectToDatabase(True)
    project = db.query(Project).filter(Project.id==project_id).one()
    recent_path = os.path.join(os.getenv('APPDATA'),'Microsoft\\Windows\\Recent')
    session = None
    if session_id:
        session = db.query(Session).filter(Session.id==session_id).one()       
    else:    
        session = Session(project)
        #initial add and commit
        db.add(session)
        db.commit()
        if old_session_id:
            #link two sessions together
            old_session = db.query(Session).filter(Session.id==old_session_id).one()
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
    :type session: :class:`models.Session` 
    
    """
    try:
        global SCANNER_TH
        if SCANNER_TH:
            SCANNER_TH.stop()
        db = ConnectToDatabase(True)
        #db.add(session)
        session = db.query(Session).filter(Session.id==session_id).one()
        db.add(session)
        session.endtime = sql.func.now()       
        db.commit()
        db.close()
    except Exception, e:
        logger.exception('EndSession exception')
    
def AddEvent(session_id,title,desc):
    """ Adds an event to the database. 
    
    :param session: The current session.
    :type session: :class:`models.Session`
    :param desc: Description of the event.
    :type desc: String.
    
    """
    try:
        db = ConnectToDatabase(True)
        if session_id:
            session = db.query(Session).filter(Session.id==session_id).one()
        else:
            session = None    
        event = Event(desc=desc,session=session,title=title)
        db.add(event)
        db.commit()
        ide = event.id
        db.close()
        logger.debug('AddEvent complete')
        return ide
    except:
        logger.exception('AddEvent exception')    
    
def AddComputer(name,ip,wos_id):
    try:
        global COMPUTER_INS
        
        db = ConnectToDatabase(True)
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        mac = ''
        mac = utils.GetMacForIp(ip)          
        ip_int = utils.DottedIPToInt(ip)
        if mac:
            c = db.query(Computer).filter_by(mac=mac).order_by(desc(Computer.id)).first()
        else:
            c = None      
        if not c:
            logger.debug("no computer instance  found")
            c = Computer(ip=ip_int,name=name,mac=mac,wos_id=wos_id)
            logger.debug(c)  
            db.add(c)
            db.commit()       
        db.expunge(c)
        db.close()
    except Exception,e:
        logger.exception("AddComputer exception")    
    return c
def GetActiveResponsiveNodes():
    nodes = []
    try:
        db = ConnectToDatabase()
        nodes = db.query(Computer.wos_id).filter(func.timestampdiff(sql.text('second'),Computer.time,func.now())<10).filter(Computer.responsive>0).order_by(Computer.wos_id).all()
        db.close()
    except:
        logger.debug("GetActiveResponsiveNodes exception")
    return nodes

def RefreshComputer(computer):
    try:
        db = ConnectToDatabase()
        db.add(computer)
        computer.time = sql.func.now()
        computer.responsive = IS_RESPONSIVE   
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
        logger.exception('refreshcomputer exception:%s',str(e))
    return computer        

def AddComputerToSession(session,name,ip,wos_id):
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
        mac = utils.GetMacForIp(ip)
        ip_int = utils.DottedIPToInt(ip)
        c = AddComputer(name,ip,wos_id)
        db.add(c)
        session.computers.append(c)
        #db.add(session)
        db.commit()
        db.expunge(session)
        db.expunge(c)
        COMPUTER_INS = c
        db.close()
    except Exception,e:
        logger.debug("Exception in AddComputerToSession")
        
def GetOrCreate(session, model, **kwargs):
    """Fetches or creates a instance.
    
    :param session: a related session 
    :type session: :class:`models.Session`
    :param model: The model of which an instance is wanted
    :type  model: :func:`sqlalchemy.ext.declarative.declarative_base`.
    
     """
    instance = session.query(model).filter_by(**kwargs).order_by(desc(model.id)).first()
    if instance:
        return instance
    else:
        if 'path' in kwargs and 'project_id' in kwargs:
            project = session.query(Project).filter(Project.id==kwargs['project_id']).one()
            instance = File(path=kwargs['path'],project=project)
            session.add(instance)
            session.commit()
            return instance
        instance = model(**kwargs)
        return instance
    
def GetRecentFiles(project_id):
    """Fetches files accessed recently in the project sessions from the database.
   
    .. todo::  Add a limit parameter, currently fetches all files.
    
    .. todo:: Duplicate check.
    
    :param project_id: The project id
    :type project_id: Integer.
    :rtype: a list of files
    
    """
    db = ConnectToDatabase()
    files = db.query(File.path,FileAction.action_time).filter(File.project_id==project_id,File.id==FileAction.file_id).order_by(desc(FileAction.action_time)).group_by(File.path).all()
    db.close()
    return files

def InitSyncProjectDir(project_id):
    """Initial sync of project dir and database.
    
    :param project_id: Project id from database.
    :type project_id: Integer.
    
    """
    try:
        db = ConnectToDatabase()
        project_files = list(set(db.query(File.path).filter(File.project_id==project_id).all()))
        project_path = GetProjectPath(project_id)
        for root, dirs, files in os.walk(project_path):
            for file in files:
                if (os.path.join(root,file),) not in project_files:
                    AddFileToProject(os.path.join(root,file),project_id)
                else:
                    project_files.remove((os.path.join(root,file),))
        for file in project_files:
            files = db.query(File).filter(File.path==file[0],File.project_id==project_id).all()
            for f in files:
                f.project = None
                db.add(f)
        db.commit()
        db.close()
    except Exception,e:
        logger.exception('Init sync project dir error')
                          
def AddFileToProject(file,project_id):
    """Add a file to project. Copies it to the folder and adds a record to database.
    
    :param file: A filepath.
    :type file: String
    :param project_id: Project id from database.
    :type projecT_id: Integer.
    :return: New filepath.
    :rtype: String
    """
    try:
        db = ConnectToDatabase()
        project = db.query(Project).filter(Project.id == project_id).one()
        filepath=utils.CopyFileToProject(file, project_id)
        if filepath:
            f = File(path=filepath,project=project)
            db.add(f)
            db.commit()
            db.close()
        return filepath
    except Exception,e:
        logger.exception('Add file to project exception')
        return ""
    
         
def IsProjectFile(filename,project_id):
    """Checks, if a file belongs to a project. Checks both project folder and database.
    
    :param filename: a filepath.
    :type filename: String.
    :param project_id: Project id from database.
    :type project_id: Integer.
    :rtype: Boolean."""
    try:
        db = ConnectToDatabase()
        files = db.query(File.path).filter(File.project_id==project_id,File.path.like('%'+ os.path.basename(filename))).order_by(desc(File.id)).all()
        db.close()
    except Exception,e:
        logger.exception("IsProjectFile query exception")

    for file in files:
            if os.path.basename(file[0]) == os.path.basename(filename):
                return file[0]
    f = utils.SearchFile(os.path.basename(filename), GetProjectPath(project_id))
    if f:
        return AddFileToProject(f,project_id)          
    return False

def GetFilePath(project_id,filename):
    file = IsProjectFile(filename,project_id)
    if file:
        return file
    return False
    
def CreateFileaction(path,action,session_id,project_id):
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
    project_file = IsProjectFile(path,project_id)
    if project_file:
        fi = GetOrCreate(db, File, path=project_file)
    else:
        fi = GetOrCreate(db, File, path=path)
    a = db.query(Action).filter(Action.id==action).one()
    if session_id>0:
        session=db.query(Session).filter(Session.id==session_id).one()
    else:
        session = None    
    fa = FileAction(fi,a,session,None)
    db.add(fi)
    db.add(fa)
    db.commit()
    db.close()
    
class SCAN_HANDLER(FileSystemEventHandler):
    """ Handler for FileSystem events on SCANNING folder.
    
    :param project_id: Project id from database.
    :type project_id: Integer.
    
    """
    def __init__(self,project_id):
        self.project_id=project_id
            
    def on_created(self,event):
        """On_created event handler. Logs to database.
        
        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`
        
        """
        try:
            project_path = GetProjectPath(self.project_id)
            if not project_path:
                return                
            new_path = os.path.join(project_path,os.path.basename(event.src_path))
            if 'Scan' in  event.src_path:
                time.sleep(35)                        
            shutil.copy2(event.src_path,new_path)
            db = ConnectToDatabase()
            f = File(path=new_path,project=db.query(Project).filter(Project.id==self.project_id).one())
            fa = FileAction(file=f,action=db.query(Action).filter(Action.id==1).one())
            db.add(f)
            db.add(fa)
            db.commit()
            db.close()
        except Exception,e:
            logger.exception('Exception in SCAN HANDLER:%s',str(e))    
            
class PROJECT_FILE_EVENT_HANDLER(FileSystemEventHandler):
    """ Handler for FileSystem events on project folder.
    
    :param project_id: Project id from database.
    :type project_id: Integer.
    
    """
    def __init__(self,project_id):
        self.project_id=project_id
            
    def on_created(self,event):
        """On_created event handler. Logs to database.
        
        :param event: The event.
        :type event: an instance of :class:`watchdog.events.FileSystemEvent`
        
        """
        try:
            db = ConnectToDatabase()
            f = File(path=event.src_path,project=db.query(Project).filter(Project.id==self.project_id).one())
            fa = FileAction(file=f,action=db.query(Action).filter(Action.id==1).one())
            db.add(f)
            db.add(fa)
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
            f = db.query(File).filter(File.path==event.src_path,File.project_id==self.project_id).order_by(File.id.desc()).first()
            fa = FileAction(file=f,action=db.query(Action).filter(Action.id==2).one())
            f.project = None
            db.add(f)
            db.add(fa)
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
            f = db.query(File).filter(File.path==event.src_path,File.project_id==self.project_id).order_by(File.id.desc()).first()
            if not f:
                f = self.on_created(event)           
            fa = FileAction(file=f,action=db.query(Action).filter(Action.id==3).one())
            db.add(f)
            db.add(fa)
            db.commit()
            db.close()
        except Exception,e:
            logger.exception("Project file scanner on_modifed exception")      
        
            
class FILE_ACTION_SCANNER(threading.Thread):
    """ A scanner thread for monitoring user actions (Open, Close, Create, etc..) during a session. Utilizes Nirsoft's tools `RecentFilesView <http://www.nirsoft.net/utils/recent_files_view.html>`_ and `OpenedFilesView <http://www.nirsoft.net/utils/opened_files_view.html>`_ .
    
    :param session_id: Current session id from database.
    :type session_id: Integer.
    :param project_id: Current project id from database.
    :type project_id: Integer.
    :param path: Filepath of project folder.
    :type path: String.
    
    """
    def __init__ (self,session_id,project_id,path):
        threading.Thread.__init__(self,name="file action scanner")
        self.session_id = session_id
        self.project_id = project_id
        self.path = path
        self._stop = threading.Event()
    def stop(self):
        """Stops the thread."""
        self._stop.set()
         
    def run(self):
            """Starts the thread."""
            last_check = datetime.datetime.now()
            #open files
            open_files = []
            #recent files
            rf = []
            #opened files
            of = []
            while not self._stop.isSet():
                del rf[:]
                del of[:]
                utils.RecentFilesQuery()()
                reader = csv.reader(open('rfv.csv'))
                rf = [(x[0],x[3]) for x in reader if not os.path.isdir(x[0])]
                for x in rf:
                    if datetime.datetime.strptime(x[1],'%d.%m.%Y %H:%M:%S')<last_check:
                        break                    
                    CreateFileaction(x[0],6,self.session_id,self.project_id)
                        #open_files.append(x) 
                last_check = datetime.datetime.now()
                time.sleep(5)         
