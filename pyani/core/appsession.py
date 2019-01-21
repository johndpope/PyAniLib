import os
import logging
import pyani.core.util
import pyani.core.anivars


logger = logging.getLogger()


class AniSession:
    """
     Creates a session, currently that means writing to disk a json file to store the session so other apps
    can access. Flexible enough to change how a session is created later on. Apps create a session object,
    then call create_session(). Then they can get_session() which returns a dict of apps and their environment
    variables. Always of format:
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
    # class variables so all instances get same data
    __seq = ""
    __shot = ""

    def __init__(self):
        self.ani_vars = pyani.core.anivars.AniVars()

        # format for env vars, defines format that get_session() will return
        self.env_format = {
            "core": {
                "seq": "",
                "shot": ""
            }
        }

    def create_session(self):
        """
        Creates a json with the environment variables apps need, like nuke which needs a seq and shot to build
        plugin paths.
        :return: any errors, or none
        """
        return pyani.core.util.write_json(self.ani_vars.session_vars_json, self.env_format, indent=1)

    def get_session(self):
        """
        This returns the session data, as the dict described above ine the class doc string
        :return: a dict of dicts
        """
        return pyani.core.util.load_json(self.ani_vars.session_vars_json)

    def set_session(self, seq, shot):
        """
        Sets the session vars for apps. there is an app session called Core that is shared by all apps.
        :param seq: seq num
        :param shot: shot num
        :return: None if successful, Error string if errors
        """
        __seq = seq
        __shot = shot

        data = pyani.core.util.load_json(self.ani_vars.session_vars_json)
        # no dict then it is a string error
        if not isinstance(data, dict):
            return data
        # save new seq and shot
        data['core']['seq'] = seq
        data['core']['shot'] = shot
        # write and check for errors. no error then wrote successfully
        data = pyani.core.util.write_json(self.ani_vars.session_vars_json, data, indent=1)
        if data:
            return data
        return None
