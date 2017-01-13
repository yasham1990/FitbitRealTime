import os


def get_var(name):
    try:
        return os.environ[name]
    except KeyError:
        return False


try:
    from secrets import keys as SECRETS
except ImportError:
    SECRETS = {}

DEBUG = get_var("DEBUG") or False

basedir = os.path.abspath(os.path.dirname(__file__))

# get secret key for session
SECRET_KEY = SECRETS.get("SECRET_KEY", False) or get_var('SECRET_KEY') or "1234567890"

# flask-toolbar config
DEBUG_TB_INTERCEPT_REDIRECTS = False

