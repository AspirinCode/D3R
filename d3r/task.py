# -*- coding: utf-8 -*-

import os
import logging
import subprocess
import shlex
import smtplib
import platform
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class D3RParameters(object):
    """Holds parameters common to Tasks

    """
    pass

class TaskException(Exception):
    """base exception class for all the other exceptions provided by 
       this module.
    """
    pass

class UnsetPathError(TaskException):
    """Exception to denote path is unset
    """
    pass


class UnsetFileNameError(TaskException):
    """Exception to denote file name is unset
    """
    pass


class UnsetNameError(TaskException):
    """Exception to denote name is unset
    """
    pass


class UnsetStageError(TaskException):
    """Exception to denote stage is unset
    """
    pass


class UnsetBlastDirError(TaskException):
    """Exception to denote blastdir in D3RParameters is unset
    """
    pass


class TaskUnableToStartError(TaskException):
    """Exception to denote when task cannot start due to failure
    """
    pass


class TaskFailedError(TaskException):
    """Exception to denote when a task failed
    """
    pass


class D3RTask(object):
    """Represents a base Task that can be run.

    This is a base class from which other classes that actual do work
    can be derived from.  It provides internal attributes for name,
    stage, and status.  As well as a run() function.

    """
    STAGE_DIRNAME_PREFIX = "stage"

    START_FILE = "start"
    ERROR_FILE = "error"
    COMPLETE_FILE = "complete"

    START_STATUS = "start"
    COMPLETE_STATUS = "complete"
    UNKNOWN_STATUS = "unknown"
    NOTFOUND_STATUS = "notfound"
    ERROR_STATUS = "error"

    def __init__(self, path, args):
        """Constructor

        Creates a `D3RTask` with `D3RTask.UNKNOWN_STATUS` status
        with `path` and `args` set to values passed in
        """
        self._path = path
        self._name = None
        self._stage = None
        self._status = D3RTask.UNKNOWN_STATUS
        self._error = None
        self._args = args
        self._can_run = None

    def get_args(self):
        return self._args

    def set_args(self, args):
        self._args = args

    def get_path(self):
        return self._path

    def set_path(self, path):
        self._path = path

    def get_name(self):
        return self._name

    def set_name(self, name):
        self._name = name

    def get_stage(self):
        return self._stage

    def set_stage(self, stage):
        self._stage = stage

    def get_status(self):
        return self._status

    def set_status(self, status):
        self._status = status

    def get_error(self):
        return self._error

    def set_error(self, error):
        self._error = error

    def _get_smtp_server(self):
        """Gets smtplib server for localhost"""
        return smtplib.SMTP(self.get_args().smtp,
                            self.get_args().smtpport)

    def _build_from_address(self):
        """Returns from email address

           The address is in format of login@host
        """
        hostname = platform.node()
        if hostname is '':
            hostname = 'localhost'
        return (os.getlogin() + '@' + hostname)

    def _send_start_email(self):
        """Creates start email message that can be passed to sendmail

        """
        the_message = ('Hi,\n ' + self.get_dir_name() + ' has started' +
                       ' running on host ' + platform.node() +
                       ' under path ' + self.get_dir() + '\n\n' +
                       'Sincerely,\n' + __file__)
                         
        msg = MIMEText(the_message)
        msg['Subject'] = (self.get_dir_name() + ' has started running')
        self._send_email(msg)


    def _send_end_email(self):
        """Creates end email message that can be passed to sendmail

        """
        
        the_message = ('Hi,\n ' + self.get_dir_name() + ' has finished' +
                       ' with status ' + self.get_status() + ' on host '
                       + platform.node() +
                       ' under path ' + self.get_dir() + '\n\n' +
                       'Sincerely,\n' + __file__)
                         
        msg = MIMEText(the_message)
        msg['Subject'] = (self.get_dir_name() +
                          ' has finished with status '+ self.get_status())
        self._send_email(msg)


    def _send_email(self,mime_msg):
        """Sends email with message passed in


           If email attribute is set with valid email addresses
           in get_args() object then this method will send
           an email with `message` passed in as content.
        """
        try: 
            if self.get_args().email is not None:
                email_list = self.get_args().email.split(',')
                logger.debug('Sending email to: ' + ", ".join(email_list))
                server = self._get_smtp_server()

                from_addr = self._build_from_address()

                mime_msg['From'] = from_addr
                mime_msg['To'] = self.get_args().email

                server.sendmail(from_addr,
                                email_list, mime_msg.as_string())
                server.quit()
                return
            else:
                logger.debug('Email was set to None, skipping email ' +
                             'notification')
        except AttributeError as e:
            logger.debug('No email set, skipping email notification ' +
                         str(e))

    def start(self):
        """Denotes start of task

           Creates task directory, along with token start file.
           If get_args() has email attribute then an email is
           sent denoting task start.  Also sets get_status()
           to D3RTask.START_STATUS.
           If there is an error creating task directory then
           end() is invoked and get_error() will be set with
           message denoting error
        """
        logger.info(self.get_dir_name() + ' task has started ')

        self.set_status(D3RTask.START_STATUS)

        self._send_start_email()
       
        try:
            self.create_dir() 
        except Exception as e:
            self.set_error('Caught exception trying to create directory ' +
                           str(e))
            self.end()
            return

        open(os.path.join(self.get_dir(),
                          D3RTask.START_FILE), 'a').close()

    def end(self):
        """Denotes task has completed

           If get_error() is not none then 'error' token file is 
           put in task directory and get_status() set to D3RTask.ERROR_STATUS
           Otherwise 'complete' token file is put in task directory.
           if get_args() email is set then a notification of task 
           completion is sent
        """

        logger.info(self.get_dir_name() + ' task has finished with status ' +
                    self.get_status())

        if self.get_error() is not None:
            logger.error(self.get_dir() + ' task failed with error ' +
                         self.get_error())
            self.set_status(D3RTask.ERROR_STATUS)
            try:
                open(os.path.join(self.get_dir(),
                                  D3RTask.ERROR_FILE), 'a').close()
            except:
                logger.exception('Caught exception')

        if self.get_status() == D3RTask.ERROR_STATUS:
            try:
                open(os.path.join(self.get_dir(),
                                  D3RTask.ERROR_FILE), 'a').close()
            except:
                logger.exception('Caught Exception')
            self._send_end_email()
            return

        self.set_status(D3RTask.COMPLETE_STATUS)
        open(os.path.join(self.get_dir(),
                          D3RTask.COMPLETE_FILE), 'a').close()
        self._send_end_email()

    def can_run(self):
        """Always returns False
            
           Derived classes should override this method
        """
        self._can_run = False
        return False

    def run(self):
        """Sees if task can run
      
           This is the base implementation and does not actually
           run anything.  Instead this method calls can_run()
           if the internal variable _can_run is None.  It is assumed
           can_run() will set _can_run variable.  If _can_run is False
           method will just return.  If _can_run is True then start()
           is called and after invocation get_error() is checked, if
           an error is found end() is called and _can_run is set to False
        """
        name = self._name
        if name is None:
            name = 'unset'
          
        logger.info(name + ' task is running')
        if self._can_run is None:
            logger.info("Running can_run() to check if its allright " +
                        "to run")
            self.can_run()

        if self._can_run is False:
            logger.info("can_run() came back with false cannot run")
            if self.get_error() is not None:
                self.end()
            return

        self.start()

        if self.get_error() is not None:
            self._can_run = False
            self.end()
            return

    def get_dir_name(self):
        """Gets directory name for task

           :raises: UnsetStageError, UnsetNameError
        """
        if self._stage is None:
            raise UnsetStageError('Stage must be set')

        if self._name is None:
            raise UnsetNameError('Name must be set')

        return (D3RTask.STAGE_DIRNAME_PREFIX + "." + str(self._stage) +
                "." + self._name)

    def get_dir(self):
        """Gets full path of Task

           :raises: UnsetPathError if path is not set,
                    and all exceptions from get_dir_name()
        """
        if self.get_path() is None:
            raise UnsetPathError('Path must be set')

        return os.path.join(self.get_path(),
                            self.get_dir_name())

    def update_status_from_filesystem(self):
        """Updates status by querying filesystem.

           Sets status based on contents of path on filesystem.
           If path does not exist then status is NOTFOUND_STATUS.
           If complete file exists under path then status is COMPLETE_STATUS
           If error file exists under path then status is ERROR_STATUS
           If start file exists under path then status is START_STATUS
           else status is UNKNOWN_STATUS
           """
        if self.get_path() is None:
            raise UnsetPathError('Path must be set')

        path_to_check = self.get_dir()

        self.set_status(self._get_status_of_task_in_dir(path_to_check))
        logger.debug(self.get_name() + ' task status set to ' +
                     self.get_status())
        return self.get_status()

    def create_dir(self):
        """Creates directory for task.

           Directory will be named stage.<stage>.<name>
           and located under get_path()
           :raises: UnsetPathError if path is not set and all exceptions
                    from get_dir_name(), and OSError if there is a
                    problem creating the directory
           """
        the_path = self.get_dir()

        logger.debug('Creating directory: ' + the_path)

        os.mkdir(the_path)

        return the_path

    def write_to_file(self, str, file_name):
        """Writes `str` to `file_name` under `task` directory

           If `str` is None file is created but nothing is written.
           File is written using 'w' mode so if file exists it will
           be overwritten.

           :raises: UnsetFileNameError if file_name is None
        """
        if file_name is None:
            raise UnsetFileNameError('file_name must be set')
        file_to_write = os.path.join(self.get_dir(), file_name)
        logger.debug('Writing file ' + file_to_write)
        f = open(file_to_write, 'w')

        if str is not None:
            f.write(str)

        f.close()

    def _get_status_of_task_in_dir(self, path):
        """Gets status of task based on existance of files in path

           Examines get_path() and returns status based on the following
           conditions
        """
        if not os.path.isdir(path):
            return D3RTask.NOTFOUND_STATUS

        if os.path.isfile(os.path.join(path, D3RTask.COMPLETE_FILE)):
            return D3RTask.COMPLETE_STATUS

        if os.path.isfile(os.path.join(path, D3RTask.ERROR_FILE)):
            return D3RTask.ERROR_STATUS

        if os.path.isfile(os.path.join(path, D3RTask.START_FILE)):
            return D3RTask.START_STATUS

        return D3RTask.UNKNOWN_STATUS


class DataImportTask(D3RTask):
    """Represents DataImport Task

       """
    NONPOLYMER_TSV = "new_release_structure_nonpolymer.tsv"
    SEQUENCE_TSV = "new_release_structure_sequence.tsv"

    def __init__(self, path, args):
        super(DataImportTask, self).__init__(path, args)
        self.set_name('dataimport')
        self.set_stage(1)
        self.set_status(D3RTask.UNKNOWN_STATUS)

    def get_nonpolymer_tsv(self):
        """Returns path to new_release_structure_nonpolymer.tsv file"""
        return os.path.join(self.get_dir(),
                            DataImportTask.NONPOLYMER_TSV)

    def get_sequence_tsv(self):
        """Returns path to new_release_structure_sequence.tsv file"""
        return os.path.join(self.get_dir(),
                            DataImportTask.SEQUENCE_TSV)


class MakeBlastDBTask(D3RTask):
    """Represents Blastable database

       This object does not follow the standard D3RTask
       structure.  This is because the blastable database
       is created externally in a legacy structure.

       """

    def __init__(self, path, args):
        """Constructor

           Constructor sets name to makeblastdb and ignores
           path set in <path> variable and instead sets
           path to args.blastdir. stage is set to 1

        """
        self.set_args(args)
        self.set_path(args.blastdir)
        self.set_name('makeblastdb')
        self.set_stage(1)
        self.set_status(D3RTask.UNKNOWN_STATUS)

    def create_dir(self):
        """Creates path set in get_path()

           """
        os.makedirs(os.path.join(self._path, 'current'))

    def get_dir_name(self):
        """Will always return current

           """
        return 'current'


class BlastNFilterTask(D3RTask):
    """Performs Blast and filter of sequences

    """

    def __init__(self, path, args):
        super(BlastNFilterTask, self).__init__(path, args)
        self.set_name('blastnfilter')
        self.set_stage(2)
        self.set_status(D3RTask.UNKNOWN_STATUS)

    def can_run(self):
        """Determines if task can actually run

           This method first verifies the `MakeBlastDBTask` task
           and `DataImportTask` both have `D3RTask.COMPLETE_STATUS` for
           status.  The method then verifies a `BlastNFilterTask` does
           not already exist.
        """
        self._can_run = False
        self._error = None
        # check blast
        make_blastdb = MakeBlastDBTask(self._path, self._args)
        make_blastdb.update_status_from_filesystem()
        if make_blastdb.get_status() != D3RTask.COMPLETE_STATUS:
            logger.info('Cannot run ' + self.get_name() + 'task ' +
                        'because ' + make_blastdb.get_name() + 'task' +
                        'has a status of ' + make_blastdb.get_status())
            if make_blastdb.get_status() == D3RTask.ERROR_STATUS:
                self.set_error(make_blastdb.get_name() + ' task has ' +
                               make_blastdb.get_status() + ' status')
            return False

        # check data import
        data_import = DataImportTask(self._path, self._args)
        data_import.update_status_from_filesystem()
        if data_import.get_status() != D3RTask.COMPLETE_STATUS:
            logger.info('Cannot run ' + self.get_name() + 'task ' +
                        'because ' + data_import.get_name() + 'task' +
                        'has a status of ' + data_import.get_status())
            if data_import.get_status() == D3RTask.ERROR_STATUS:
                self.set_error(data_import.get_name() + ' task has ' +
                               data_import.get_status() + ' status')
            return False

        # check blast is not complete and does not exist

        self.update_status_from_filesystem()
        if self.get_status() == D3RTask.COMPLETE_STATUS:
            logger.debug("No work needed for " + self.get_name() +
                         " task")
            return False

        if self.get_status() != D3RTask.NOTFOUND_STATUS:
            logger.warning(self.get_name() + " task was already " +
                           "attempted, but there was a problem")
            self.set_error(self.get_dir_name() + ' already exists and ' +
                           'status is ' + self.get_status())
            return False
        self._can_run = True
        return True

    def run(self):
        """Runs blastnfilter task after verifying dataimport was good

           Method requires can_run() to be called before hand with
           successful outcome
           Otherwise method invokes D3RTask.start then this method
           creates a directory and invokes blastnfilter script.  Upon
           completion results are analyzed and success or error status
           is set appropriately and D3RTask.end is invoked
           """
        super(BlastNFilterTask, self).run()

        if self._can_run is False:
            logger.debug(self.get_dir_name()+ ' cannot run cause _can_run flag '
                         'is False')
            return


        data_import = DataImportTask(self._path, self._args)

        cmd_to_run = (self.get_args().blastnfilter + ' --nonpolymertsv ' +
                      data_import.get_nonpolymer_tsv() +
                      ' --sequencetsv ' +
                      data_import.get_sequence_tsv() +
                      ' --outdir ' + self.get_dir())

        # Run the blastnfilter
        logger.info("Running command " + cmd_to_run)
        try:
            p = subprocess.Popen(shlex.split(cmd_to_run),
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        except Exception as e:
            logger.exception("Error caught exception")
            self.set_status(D3RTask.ERROR_STATUS)
            self.set_error("Caught Exception trying to run " +
                           cmd_to_run + " : " + str(e))
            self.end()
            return

        out, err = p.communicate()

        blastnfilter_name = os.path.basename(self.get_args().blastnfilter)
        self.write_to_file(err, blastnfilter_name + '.stderr')
        self.write_to_file(out, blastnfilter_name + '.stdout')

        if p.returncode == 0:
            self.set_status(D3RTask.COMPLETE_STATUS)
        else:
            self.set_status(D3RTask.ERROR_STATUS)
            self.set_error("Non zero exit code: " + str(p.returncode) +
                           "received. Standard out: " + out +
                           " Standard error : " + err)

        # assess the result
        self.end()
