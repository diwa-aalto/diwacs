'''
Created on 23.5.2012


@author: neriksso

@requires: sqlalchemy

:synopsis: Used to represent the different database structures on DiWa.
'''
import datetime
import os 
import threading
import time
import win32com.client 
import pythoncom
from sqlalchemy import Column, Integer, String, ForeignKey, Table, DateTime,sql,create_engine,Boolean, text
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
import controller
Base = declarative_base()

class Company(Base):
    """ A class representation of a company.
    
    Fields:
        * :py:attr:`id` (:py:class:`Integer`) - Primary key in database table.
        * :py:attr:`name` (:py:class:`String`) - Name of the company.
    
    :param name: The name of the company.
    :type name: String
    """
    #: Todo: Should include backref to user documentation here?
    __tablename__ = 'company'
    id = Column(Integer, primary_key=True)
    name = Column(String(50,convert_unicode=True),nullable=False)

    def __init__(self,name):
        self.name = name
            

class User(Base):
    """A class representation of a user.
    
    Fields:
        * :py:attr:`id` (:py:class:`Integer`) - Primary key in database table.
        * :py:attr:`name` (:py:class:`String`) - Name of the user.
        * :py:attr:`email` (:py:class:`String`) - Email address of the user.
        * :py:attr:`title` (:py:class:`String`) - Title of the user in the company.
        * :py:attr:`department` (:py:class:`String`) - Department of the user in the company.
        * :py:attr:`company_id` (:py:class:`Integer`) - Company id of the employing company.
        * :py:attr:`company` (:py:class:`sqlalchemy.orm.relationship`) - Company relationship.
    
    :param name: Name of the user.
    :type name: String.
    :param company: The employer.
    :type company: :class:`models.Company`
    
    """
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    name = Column(String(50,convert_unicode=True),nullable=False)
    email = Column(String(100,convert_unicode=True))
    title = Column(String(50,convert_unicode=True))
    department = Column(String(100,convert_unicode=True))
    company_id = Column(Integer, ForeignKey('company.id'))
    company = relationship("Company", backref=backref('employees', order_by=id))

    def __init__(self,name,company):
        self.name = name 
        self.company = company
            
ProjectMembers = Table('projectmembers', Base.metadata,
    Column('Project', Integer, ForeignKey('project.id')),
    Column('User', Integer, ForeignKey('user.id'))
)

class Activity(Base):
    """ A class representation of an activity.
    
    Fields:
        * :py:attr:`id` (:py:class:`Integer`) - ID of activity, used as primary key in database table.
        * :py:attr:`session_id` (:py:class:`Integer`) - ID of the session activity belongs to.
        * :py:attr:`session` (:py:class:`sqlalchemy.orm.relationship`) - Session relationship.
        * :py:attr:`project_id` (:py:class:`Integer`) - ID of the project activity belongs to.
        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`) - Project relationship.
        * :py:attr:`active` (:py:class:`Boolean`) - Boolean flag indicating that the project is active.
        
    :param project: Project activity belongs to.
    :type project: models.Project
    :param session: Optional session activity belongs to.
    :type session: models.Session
    """
    __tablename__ = 'activity'
    id = Column(Integer, primary_key=True, autoincrement=True,default = text("coalesce(max(activity.id),0)+1 from activity"))
    session_id = Column(Integer, ForeignKey('session.id'))
    session = relationship("Session", backref=backref('activities', order_by=id))
    project_id = Column(Integer, ForeignKey('project.id'),nullable=False)
    project = relationship("Project", backref=backref('activities', order_by=id))
    active = Column(Boolean,default=True)
    def __init__(self,project,session=None):
        #controller.UnsetActivity()
        self.project = project
        if session:
            self.session = session
            
            
class Project(Base):
    """A class representation of a project.
    
    :param name: Name of the project.
    :type name: String.
    :param company: The owner of the project.
    :type company: :class:`models.Company`
    
    """
    __tablename__ = 'project'
    id = Column(Integer, autoincrement=True,primary_key=True,default = text("coalesce(max(project.id),0)+1 from project"))
    name = Column(String(50,convert_unicode=True))
    password = Column(String(40),nullable=True)
    company_id = Column(Integer, ForeignKey('company.id'),nullable=False)
    company = relationship("Company", backref=backref('projects', order_by=id),uselist=False)
    dir = Column(String(255,convert_unicode=True),nullable=True)
    members = relationship('User', secondary=ProjectMembers, backref='projects')
    
    def __init__(self,name,company,password):
        self.name = name
        self.company = company
        self.password = password

SessionParticipants = Table('sessionparticipants', Base.metadata,
    Column('Session', Integer, ForeignKey('session.id')),
    Column('User', Integer, ForeignKey('user.id'))
)
SessionComputers = Table('sessioncomputers', Base.metadata,
    Column('Session', Integer, ForeignKey('session.id')),
    Column('Computer', Integer, ForeignKey('computer.id'))
)

class Computer(Base):
    """A class representation of a computer. 
    
    Fields:
        * name
        * ip
        * mac
        * user
        * responsive
        * wos_id
         
    """
    __tablename__ = "computer"
    id = Column(Integer, primary_key=True, autoincrement=True,default = text("coalesce(max(computer.id),0)+1 from computer"))
    name = Column(String(50,convert_unicode=True),nullable=False)
    ip = Column(mysql.INTEGER(unsigned=True),nullable=False)
    mac = Column(String(12),nullable=True)
    time = Column(mysql.DATETIME)
    screens = Column(mysql.SMALLINT,default=0)
    responsive = Column(mysql.TINYINT,nullable=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship("User", backref=backref('computers', order_by=id))
    wos_id = Column(Integer)
    
    def __str__(self):
        return "<%d: name:%s screens:%d time:%s>" % (self.wos_id,self.name,self.screens,self.time.isoformat())
    
    def __repr__(self):
        return self.__str__()
                            
class Session(Base):
    """A class representation of a session.
    
    :param project: The project for the session.
    :type company: :class:`models.Project`
    
    """
    __tablename__ = 'session'
    id = Column(Integer, primary_key=True,autoincrement=True,default = text("coalesce(max(session.id),0)+1 from session"))
    name = Column(String(50,convert_unicode=True),nullable=True)
    project_id = Column(Integer, ForeignKey('project.id'),nullable=False)
    project = relationship("Project", backref=backref('sessions', order_by=id))
    starttime = Column(DateTime,default=sql.func.now())
    endtime = Column(DateTime)
    previous_session_id = Column(Integer, ForeignKey('session.id'))
    previous_session = relationship('Session', uselist=False,remote_side=[id])
    participants = relationship('User', secondary=SessionParticipants, backref='sessions')
    computers = relationship('Computer', secondary=SessionComputers, backref='sessions')
    
    def __init__(self,project):
        self.project = project
        self.users = []
        self.endtime = None
        self.last_checked =  None
        
    def start(self):
        """Start a session. Set the last checked field."""
        self.last_checked = datetime.datetime.now()
        
    def get_last_checked(self):
        """Fetch last checked field.
        
        :return: Last checked field
        :rtype: Datetime
        
        """
        return self.last_checked   
     
    def addUser(self,user):
        """Add users to a session."""
        self.users.append(user)
    
    def fileRoutine(self):
        """ File checking routine for logging"""
        recent_path = os.path.join(os.getenv('APPDATA'),'Microsoft\\Windows\\Recent')
        f = open('log.txt','w')
        log_path = os.path.join(os.getcwd(),f.name)
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        except pythoncom.com_error:
                # already initialized.
                pass
        shell = win32com.client.Dispatch("WScript.Shell")
        while self.endtime == None:
            for file in os.listdir(recent_path):
                filepath = os.path.join(recent_path,file)
                file_atime =  datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                #f.write(file + " " + str(file_atime))              
                if file_atime  > self.get_last_checked():
                    #f.write("file ")
                    try:
                        shortcut = shell.CreateShortCut(filepath)
                        if os.path.isfile(shortcut.TargetPath) and not shortcut.TargetPath == log_path:
                            f.write(shortcut.TargetPath+" "+str(file_atime))
                        else:
                            continue    
                    except:
                        ext = file.rfind('.')
                        f.write(file[:ext]+" "+str(file_atime))   
                    f.write(" opened \n")    
                    
            self.last_checked = datetime.datetime.now()
            #f.write("-----------------------")
            time.sleep(10)
        f.close()
        
class Event(Base):
    """A class representation of Event. A simple note with timestamp during a session.
    
    Fields:
        * desc
        * title
        * time
        * session
        
    """
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True, autoincrement=True,default = text("coalesce(max(event.id),0)+1 from event"))
    title = Column(String(40,convert_unicode=True),nullable=False)
    desc = Column(String(500,convert_unicode=True),nullable=False)
    time = Column(DateTime,default=sql.func.now())
    session_id = Column(Integer, ForeignKey('session.id'))
    session = relationship("Session", backref=backref('events', order_by=id))    
          
class Action(Base):
    """A class representation of a action. Describes a file action.
    
    :param name: Name of the action.
    :type name: String.
    
    """
    __tablename__ = 'action'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    
    
    def __init__(self,name):
        self.name = name
        
    def __repr__(self):
        return self.name 
         
class File(Base):
    """A class representation of a file.
    
    Fields:
        * path
        * project
        
    """
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True, autoincrement=True,default = text("coalesce(max(file.id),0)+1 from file"))
    path = Column(String(255,convert_unicode=True),nullable=False)
    project_id = Column(Integer, ForeignKey('project.id'),nullable=True)
    project = relationship("Project", backref=backref('files', order_by=id))
    
    def __repr__(self):
        return self.path 
    
                
class FileAction(Base):
    """A class representation of a fileaction. 
    
    :param file: The file in question.
    :type file: :class:`models.File`
    :param action: The action in question.
    :type action: :class:`models.Action`
    :param session: The session in question.
    :type session: :class:`models.Session`
    :param computer: The computer in question.
    :type computer: :class:`models.Computer`
    :param user: The user performing the action.
    :type user: :class:`models.User`
    
    """
    __tablename__ = 'fileaction'
    id = Column(Integer, primary_key=True, autoincrement=True,default = text("coalesce(max(fileaction.id),0)+1 from fileaction"))
    file_id = Column(Integer, ForeignKey('file.id'),nullable=False)
    file = relationship("File", backref=backref('actions', order_by=id))
    action_id = Column(Integer, ForeignKey('action.id'),nullable=False)
    action = relationship("Action", backref=backref('actions', order_by=id))
    action_time = Column(DateTime,default=sql.func.now()) 
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship("User", backref=backref('fileactions', order_by=id))
    computer_id = Column(Integer, ForeignKey('computer.id'))
    computer = relationship("Computer", backref=backref('fileactions', order_by=id))
    session_id = Column(Integer, ForeignKey('session.id'))
    session = relationship("Session", backref=backref('fileactions', order_by=id))  
    
    def __init__(self,file,action,session=None,computer=None,user=None):
        self.file = file
        self.action = action
        self.user = user
        self.session = session
        self.computer = computer                             