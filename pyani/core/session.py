import os
import logging
import pyani.core.util
import pyani.core.appvars


logger = logging.getLogger()


class AniSession:
    """
    Creates a session, currently that means writing to disk a json file to store the session so other apps
    can access. Flexible enough to change how a session is created later on. Apps create a session object,
    then call create_session(). Then they can get_session() which returns a tuple of the environment
    variables - currently sequence and shot. Always of format:
    {
        "App Name" : {
            "variable": "value"
        }
    }
    there is an app session called Core that is shared by all apps. It has this data:
    {
        "core" : {
            "seq": "Seq###"
            "shot": "Shot###"
        }
    }
    """
    def __init__(self):
        self.app_vars = pyani.core.appvars.AppVars()

        # session vars
        self.__seq = None
        self.__shot = None

        # format for env vars, defines format that get_session() will return
        self.env_format = {
            "core": {
                "seq": "",
                "shot": ""
            }
        }

    def create_session(self):
        """
        Creates a json with the environment variables apps need (if its not created),
        like nuke which needs a seq and shot to build plugin paths.
        :return: any errors, or none
        """
        if not os.path.exists(self.app_vars.session_file):
            return pyani.core.util.write_json(self.app_vars.session_file, self.env_format, indent=1)
        return None

    def load_session(self):
        """
        Loads the session off disk. Sets to show level if can't load session and logs error.
        """
        session = pyani.core.util.load_json(self.app_vars.session_file)
        # if errors loading, set to show level session
        if not isinstance(session, dict):
            logger.error("Could not load session. Error is {0}".format(session))
            self.__seq = "show"
            self.__shot = "show"
        # no session but file exists
        elif not session['core']['seq']:
            self.__seq = "show"
            self.__shot = "show"
        # there is a session set
        else:
            self.__seq = session['core']['seq']
            self.__shot = session['core']['shot']

    def get_core_session(self):
        """
        This returns the core session data as a tuple of (sequence, shot)
        :return: a tuple containing the sequence and shot - if no shot environment set then defaults to "show"
        """
        self.load_session()
        return self.__seq, self.__shot

    def get_sequence(self):
        """
        Returns the sequence stored in the session. If no session is stored defaults to show
        """
        self.load_session()
        return self.__seq

    def get_shot(self):
        """
        Returns the shot stored in the session. If no session is stored defaults to show
        """
        self.load_session()
        return self.__shot

    def set_session(self, seq, shot):
        """
        Sets the session vars for apps. there is a session called Core that is shared by all apps.
        :param seq: seq num
        :param shot: shot num
        :return: None if successful, Error string if errors
        """
        self.__seq = seq
        self.__shot = shot

        session = self.env_format.copy()
        # save new seq and shot
        session['core']['seq'] = seq
        session['core']['shot'] = shot
        # write and check for errors. no error then wrote successfully
        data = pyani.core.util.write_json(self.app_vars.session_file, session)
        if data:
            return data
        return None
