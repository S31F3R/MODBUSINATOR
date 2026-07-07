import logging
import os
from logging.handlers import RotatingFileHandler

loggingInitialized = False

def initLogging(appName='MODBUSINATOR', debugMode=False):
    """
    Initializes logging exactly once.
    - Logs to %LOCALAPPDATA%/<appName>/logs/app.log
    - File logging always DEBUG
    - Console logging DEBUG if debugMode=True, else WARNING
    - Handlers added only once (safe to import from any module)
    """
    global loggingInitialized

    if loggingInitialized:
        return

    # Use ProgramData for service-safe logging
    programData = os.environ.get("PROGRAMDATA", r"C:\ProgramData")

    # Build log directory
    logDir = os.path.join(programData, appName, "logs")
    os.makedirs(logDir, exist_ok=True)

    # Full path to log file
    logPath = os.path.join(logDir, "app.log")

    # Create logger
    logger = logging.getLogger(appName)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Prevent double addition of handlers
    if not logger.handlers:
        # Console Handler
        consoleHandler = logging.StreamHandler()
        consoleLevel = logging.DEBUG if debugMode else logging.WARNING
        consoleHandler.setLevel(consoleLevel)
        consoleFormatter = logging.Formatter('[%(levelname)s] %(message)s')
        consoleHandler.setFormatter(consoleFormatter)
        logger.addHandler(consoleHandler)

        # File Handler (rotating)
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
    logger = logging.getLogger('SCADA Data Link')
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