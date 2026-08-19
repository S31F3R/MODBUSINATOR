import logging
import os
from logging.handlers import RotatingFileHandler

loggingInitialized = False
loggerName = 'MODBUSINATOR'

def _logDir(appName):
    """Service-safe log directory: ProgramData on Windows, XDG state on POSIX."""
    if os.name == 'nt':
        base = os.environ.get("PROGRAMDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, appName, "logs")
    stateHome = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(stateHome, appName, "logs")

def initLogging(appName='MODBUSINATOR', debugMode=False):
    """
    Initializes logging exactly once.
    - Logs to %PROGRAMDATA%/<appName>/logs/app.log (Windows)
      or $XDG_STATE_HOME/<appName>/logs/app.log (POSIX)
    - File logging always DEBUG
    - Console logging DEBUG if debugMode=True, else WARNING
    - Handlers added only once (safe to import from any module)
    """
    global loggingInitialized, loggerName

    if loggingInitialized:
        return

    loggerName = appName
    logDir = _logDir(appName)
    os.makedirs(logDir, exist_ok=True)
    logPath = os.path.join(logDir, "app.log")

    logger = logging.getLogger(appName)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not logger.handlers:
        consoleHandler = logging.StreamHandler()
        consoleLevel = logging.DEBUG if debugMode else logging.WARNING
        consoleHandler.setLevel(consoleLevel)
        consoleFormatter = logging.Formatter('[%(levelname)s] %(message)s')
        consoleHandler.setFormatter(consoleFormatter)
        logger.addHandler(consoleHandler)

        fileHandler = RotatingFileHandler(
            logPath,
            maxBytes=1048576,
            backupCount=5,
            encoding='utf-8'
        )
        fileHandler.setLevel(logging.DEBUG)
        fileFormatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        fileHandler.setFormatter(fileFormatter)
        logger.addHandler(fileHandler)
    loggingInitialized = True

def logMessage(level, message):
    """
    Log a message at a specified level.
    Accepted levels: DEBUG, INFO, WARN, ERROR, CRITICAL
    """
    if not loggingInitialized:
        initLogging()
    logger = logging.getLogger(loggerName)
    lvl = level.upper()

    if lvl == 'DEBUG':
        logger.debug(message)
    elif lvl == 'INFO':
        logger.info(message)
    elif lvl in ('WARN', 'WARNING'):
        logger.warning(message)
    elif lvl == 'ERROR':
        logger.error(message)
    elif lvl == 'CRITICAL':
        logger.critical(message)
    else:
        logger.warning(f"Unknown log level '{level}': {message}")