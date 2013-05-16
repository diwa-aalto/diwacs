'''
Created on 23.5.2012


@author: neriksso

@requires: sqlalchemy

:synopsis: Used to represent the different database structures on DiWa.
'''
import datetime
import os 
import time
import win32com.client 
import pythoncom
from sqlalchemy import Column, Integer, String, ForeignKey, Table, sql, Boolean, text
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
Base = declarative_base()


#: TODO: The attribute descriptions need a bit of refactoring after the models are up to date with database situation.
class Company(Base):
    """ A class representation of a company.
    
    Fields:
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the company, used as primary key in database table.
        * :py:attr:`name` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Name of the company (Max 50 characters).
    
    :param name: The name of the company.
    :type name: :py:class:`String`
    """
    #: Todo: Should include backref to user documentation here?
    __tablename__ = 'company'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, default = text("coalesce(max(company.id),0)+1 from company"))
    name = Column(String(50, convert_unicode=True), nullable=False)

    def __init__(self,name):
        self.name = name
            

class User(Base):
    """A class representation of a user.
    
    Fields:
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the user, used as primary key in database table.
        * :py:attr:`name` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Name of the user (Max 50 characters).
        * :py:attr:`email` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Email address of the user (Max 100 characters).
        * :py:attr:`title` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Title of the user in the company (Max 50 characters).
        * :py:attr:`department` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Department of the user in the company (Max 100 characters).
        * :py:attr:`company_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - Company id of the employing company.
        * :py:attr:`company` (:py:class:`sqlalchemy.orm.relationship`) - Company relationship.
    
    :param name: Name of the user.
    :type name: :py:class:`String`
    :param company: The employer.
    :type company: :py:class:`models.Company`
    
    """
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, default = text("coalesce(max(user.id),0)+1 from user"))
    name = Column(String(50, convert_unicode=True), nullable=False)
    email = Column(String(100, convert_unicode=True), nullable=True)
    title = Column(String(50, convert_unicode=True), nullable=True)
    department = Column(String(100, convert_unicode=True), nullable=True)
    company_id = Column(Integer, ForeignKey('company.id'))
    company = relationship("Company", backref=backref('employees', order_by=id))

    def __init__(self,name,company):
        self.name = name 
        self.company = company


"""A variable to hold the connection between users and projects (a table).

:py:data:`ProjectMembers` (:py:class:`sqlalchemy.schema.Table`)

This comment is not included in the autodoc because it's over the ProjectMember
definition. However if it was under it, the autodoc would include the whole line
to the documentation before the actual docstring... Which is horribly ugly with
autodoc formatting.
"""
ProjectMembers = Table('projectmembers', Base.metadata,
    Column('Project', Integer, ForeignKey('project.id')),
    Column('User', Integer, ForeignKey('user.id'))
) 

class Activity(Base):
    """ A class representation of an activity.
    
    Fields:
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of activity, used as primary key in database table.
        * :py:attr:`session_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the session activity belongs to.
        * :py:attr:`session` (:py:class:`sqlalchemy.orm.relationship`) - Session relationship.
        * :py:attr:`project_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the project activity belongs to.
        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`) - Project relationship.
        * :py:attr:`active` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Boolean)`) - Boolean flag indicating that the project is active.
        
    :param project: Project activity belongs to.
    :type project: :py:class:`models.Project`
    :param session: Optional session activity belongs to.
    :type session: :py:class:`models.Session`
    """
    __tablename__ = 'activity'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, default = text("coalesce(max(activity.id),0)+1 from activity"))
    session_id = Column(Integer, ForeignKey('session.id'))
    session = relationship("Session", backref=backref('activities', order_by=id))
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)
    project = relationship("Project", backref=backref('activities', order_by=id))
    active = Column(Boolean, nullable=False, default=True)
    def __init__(self,project,session=None):
        #controller.UnsetActivity()
        self.project = project
        if session:
            self.session = session
            
            
class Project(Base):
    """A class representation of a project.
    
    Fields:
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of project, used as primary key in database table.
        * :py:attr:`name` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Name of the project (Max 50 characters).
        * :py:attr:`company_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the company that owns the project.
        * :py:attr:`company` (:py:class:`sqlalchemy.orm.relationship`) - The company that owns the project.
        * :py:attr:`dir` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Directory path for the project files (Max 255 characters).
        * :py:attr:`password` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Password for the project (Max 40 characters).
        * :py:attr:`members` (:py:class:`sqlalchemy.orm.relationship`) - The users that work on the project.
        
    :param name: Name of the project.
    :type name: :py:class:`String`
    :param company: The owner of the project.
    :type company: :py:class:`models.Company`
    
    """
    __tablename__ = 'project'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, default = text("coalesce(max(project.id),0)+1 from project"))
    name = Column(String(50, convert_unicode=True), nullable=False)
    company_id = Column(Integer, ForeignKey('company.id'), nullable=False)
    company = relationship("Company", backref=backref('projects', order_by=id), uselist=False)
    dir = Column(String(255, convert_unicode=True), nullable=True)  #: Is it ok for a project to not have a directory?
    password = Column(String(40) , nullable=True)
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
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of computer, used as primary key in database table.
        * :py:attr:`name` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Name of the computer.
        * :py:attr:`ip` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.dialects.mysql.INTEGER)`) - Internet Protocol address of the computer (Defined as unsigned).
        * :py:attr:`mac` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Media Access Control address of the computer.
        * :py:attr:`time` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.dialects.mysql.DATETIME)`) - Time of the last network activity from the computer.
        * :py:attr:`screens` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.dialects.mysql.SMALLINT)`) - Number of screens on the computer.
        * :py:attr:`responsive` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.dialects.mysql.TINYINT)`) - The responsive value of the computer.
        * :py:attr:`user_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the user currently using the computer.
        * :py:attr:`user` (:py:class:`sqlalchemy.orm.relationship`) - The current user.
        * :py:attr:`wos_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - **WOS** ID.
    
    """
    __tablename__ = "computer"
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, default = text("coalesce(max(computer.id),0)+1 from computer"))
    name = Column(String(50, convert_unicode=True), nullable=False)
    ip = Column(mysql.INTEGER(unsigned=True), nullable=False)
    mac = Column(String(12, convert_unicode=True), nullable=True)
    time = Column(mysql.DATETIME, nullable=True)
    screens = Column(mysql.SMALLINT, nullable=True, default=0)
    responsive = Column(mysql.TINYINT, nullable=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship("User", backref=backref('computers', order_by=id))
    wos_id = Column(Integer, nullable=True)
    
    def __str__(self):
        return "<%d: name:%s screens:%d time:%s>" % (self.wos_id,self.name,self.screens,self.time.isoformat())
    
    def __repr__(self):
        return self.__str__()
                            
class Session(Base):
    """A class representation of a session.
    
    Fields:
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of session, used as primary key in database table.
        * :py:attr:`name` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Name of session (Max 50 characters).
        * :py:attr:`project_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the project the session belongs to.
        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`) - The project the session belongs to.
        * :py:attr:`starttime` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.dialects.mysql.DATETIME)`) - Time the session began, defaults to `now()`.
        * :py:attr:`endtime` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.dialects.mysql.DATETIME)`) - The time session ended.
        * :py:attr:`previous_session_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the previous session.
        * :py:attr:`previous_session` (:py:class:`sqlalchemy.orm.relationship`) - The previous session.
        * :py:attr:`participants` (:py:class:`sqlalchemy.orm.relationship`) - Users that belong to this session.
        * :py:attr:`computers` (:py:class:`sqlalchemy.orm.relationship`) - Computers that belong to this session.
    
    :param project: The project for the session.
    :type project: :py:class:`models.Project`
    
    
    """
    __tablename__ = 'session'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, default = text("coalesce(max(session.id),0)+1 from session"))
    name = Column(String(50, convert_unicode=True), nullable=True)
    project_id = Column(Integer, ForeignKey('project.id'), nullable=False)
    project = relationship("Project", backref=backref('sessions', order_by=id))
    starttime = Column(mysql.DATETIME, default=sql.func.now(), nullable=True)
    endtime = Column(mysql.DATETIME, nullable=True)
    previous_session_id = Column(Integer, ForeignKey('session.id'), nullable=True)
    previous_session = relationship('Session', uselist=False, remote_side=[id])
    participants = relationship('User', secondary=SessionParticipants, backref='sessions')
    computers = relationship('Computer', secondary=SessionComputers, backref='sessions')
    
    def __init__(self, project):
        self.project = project
        self.users = []
        self.endtime = None
        self.last_checked =  None
        
    def start(self):
        """Start a session. Set the :py:attr:`last_checked` field to current DateTime."""
        self.last_checked = datetime.datetime.now()
        
    def get_last_checked(self):
        """Fetch :py:attr:`last_checked` field.
        
        :return: :py:attr:`last_checked` field (None before :py:meth:`models.Session.start` is called).
        :rtype: :py:class:`datetime.datetime` or :py:const:`None`
        
        """
        return self.last_checked   
     
    def addUser(self, user):
        """Add users to a session.
        
        :param user: User to be added into the session.
        :type user: :py:class:`models.User`
        """
        self.users.append(user)
    
    def fileRoutine(self):
        """ File checking routine for logging.
        
        :throws IOError: When log.txt is not available for write access.
        """
        recent_path = os.path.join(os.getenv('APPDATA'),'Microsoft\\Windows\\Recent')
        f = open('log.txt', 'w')
        log_path = os.path.join(os.getcwd(),f.name)
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        except pythoncom.com_error :
            # already initialized.
            pass
        
        shell = win32com.client.Dispatch("WScript.Shell")
        while self.endtime == None :
            for dir_entry in os.listdir(recent_path):
                dir_path = os.path.join(recent_path, dir_entry)
                dir_mtime = None
                try :
                    dir_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(dir_path))
                    #: os.path.getmtime() can raise exceptions as well.
                except os.error :
                    continue
                    #: Just ignore the entry if you fail to get the mtimne.
                if dir_mtime > self.get_last_checked() :
                    try :
                        shortcut = shell.CreateShortCut(dir_path)
                        if os.path.isfile(shortcut.TargetPath) and not shortcut.TargetPath == log_path :
                            f.write(shortcut.TargetPath + " " + str(dir_mtime) + " opened \n")
                    except :
                        ext = dir_entry.rfind('.')
                        f.write(dir_entry[:ext] + " " + str(dir_mtime) + " opened \n")
            self.last_checked = datetime.datetime.now()
            time.sleep(10)
        
        f.close()
        
class Event(Base):
    """A class representation of Event. A simple note with timestamp during a session.
    
    Fields:
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the event, used as primary key in database table.
        * :py:attr:`title` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Title of the event (Max 40 characters).
        * :py:attr:`desc` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - More in-depth description of the event (Max 500 characters).
        * :py:attr:`time` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.dialects.mysql.DATETIME)`) - Time the event took place.
        * :py:attr:`session_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the session this event belongs to.
        * :py:attr:`session` (:py:class:`sqlalchemy.orm.relationship`) - Session this event belongs to.
    
    """
    __tablename__ = 'event'
    id = Column(Integer, primary_key=True, autoincrement=True, default = text("coalesce(max(event.id),0)+1 from event"))
    title = Column(String(40, convert_unicode=True), nullable=False) #: ?
    desc = Column(String(500, convert_unicode=True), nullable=True)
    time = Column(mysql.DATETIME, default=sql.func.now())
    session_id = Column(Integer, ForeignKey('session.id'))
    session = relationship("Session", backref=backref('events', order_by=id))
          
class Action(Base):
    """A class representation of a action. A file action uses this to describe the action.
    
    Field:
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the action, used as primary key in database table.
        * :py:attr:`name` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Name of the action (Max 50 characters).
    
    :param name: Name of the action.
    :type name: :py:class:`String`
    
    """
    __tablename__ = 'action'
    id = Column(Integer, primary_key=True)
    name = Column(String(50, convert_unicode=True), nullable=True)
    
    
    def __init__(self, name) :
        self.name = name
        
    def __repr__(self) :
        return self.name 
         
class File(Base):
    """A class representation of a file.
    
    Fields:
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the file, used as primary key in database table.
        * :py:attr:`path` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.String)`) - Path of the file on DiWa (max 255 chars).
        * :py:attr:`project_id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the project this file belongs to.
        * :py:attr:`project` (:py:class:`sqlalchemy.orm.relationship`) - Project this file belongs to.
        
    """
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True, autoincrement=True,default = text("coalesce(max(file.id),0)+1 from file"))
    path = Column(String(255, convert_unicode=True), nullable=False)
    project_id = Column(Integer, ForeignKey('project.id'),nullable=True)
    project = relationship("Project", backref=backref('files', order_by=id))
    
    def __repr__(self):
        return self.path 
    
                
class FileAction(Base):
    """A class representation of a fileaction.
    
    Fields:
        * :py:attr:`id` (:py:class:`sqlalchemy.schema.Column(sqlalchemy.types.Integer)`) - ID of the FileAction, used as primary key in the database table.
        * more (TODO)
    
    :param file: The file in question.
    :type file: :py:class:`models.File`
    :param action: The action in question.
    :type action: :py:class:`models.Action`
    :param session: The session in question.
    :type session: :py:class:`models.Session`
    :param computer: The computer in question.
    :type computer: :py:class:`models.Computer`
    :param user: The user performing the action.
    :type user: :py:class:`models.User`
    
    """
    __tablename__ = 'fileaction'
    id = Column(Integer, primary_key=True, autoincrement=True,default = text("coalesce(max(fileaction.id),0)+1 from fileaction"))
    file_id = Column(Integer, ForeignKey('file.id'),nullable=False)
    file = relationship("File", backref=backref('actions', order_by=id))
    action_id = Column(Integer, ForeignKey('action.id'),nullable=False)
    action = relationship("Action", backref=backref('actions', order_by=id))
    action_time = Column(mysql.DATETIME, default=sql.func.now()) 
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship("User", backref=backref('fileactions', order_by=id))
    computer_id = Column(Integer, ForeignKey('computer.id'))
    computer = relationship("Computer", backref=backref('fileactions', order_by=id))
    session_id = Column(Integer, ForeignKey('session.id'))
    session = relationship("Session", backref=backref('fileactions', order_by=id))  
    
    def __init__(self, file, action, session=None, computer=None, user=None):
        self.file = file
        self.action = action
        self.user = user
        self.session = session
        self.computer = computer
        
        
