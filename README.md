DiWaCS
======

DiWaCS is a project collaboration tool for Windows.

> (c) 2012-2013 DiWa project by Strategic Usability Research Group STRATUS,
> Aalto University School of Science.


Basic description of the system
-------------------------------
The system is more than just the software, it is a room that has been
equipped with the software for the purpose of researching usability.

The system is equipped to handle projects. It offers an interface in which
files can be stored into projects. Projects can be additionally "hidden"
behind a password but this is __not__ a real security feature, more like
an extra. Corporate users should anyways implement their own password
protection for the system 

Project can contain sessions these represent the time that users have
interacted with the project. Creating a session for a project is optional
but some features are only enabled while a session is on.

The projects can have events that represent important events of the project.
For example when an important conclusion has been reached. When these events
are triggered the software also tries to capture screenshots of all the
visible screens and take a snapshot from the room camera. The software also
records constantly audio from the room and will save a recording around the
time the event fired.


Setup instructions
------------------
The most crucial part of the system is the database. You should deploy a
database before installing the system. The system has been developed using
MySQL server, but it has been tested succesfully on PostgreSQL also. After
you have setup the database and installed the software (or otherwise set
up an running environment for it) you should configure the config.ini file
found under you home directory `~\.wos\config.ini` and can be edited using
plaintext editors.

It is noteworthy to know that you ***need*** to have the database connection
configured (password, username, databasename) before running the software or
the software will just display a notice that it could not connect to the
database and shutdown. This behaviour should be removed from the software and
more user friendly way of editing the config to be implemented. It does
already support in GUI editing of screen name, visibility and the permission
to run shell commands sent by the server.
