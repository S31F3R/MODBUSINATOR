import os
import sys
import json
import subprocess
import argparse
import time

def loadServiceConfig():
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    configPath = os.path.join(scriptDir, "serviceConfig.json")
    if os.path.exists(configPath):
        try:
            with open(configPath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return {
        "name": "DefaultService",
        "description": "",
        "targetScript": "",
        "displayName": "Default Service"
    }

def ensurePywin32():
    try:
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager
        return True
    except ImportError:
        print("pywin32 not found in current Python environment. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32", "--quiet"])
            print("pywin32 installed successfully.")
            scriptsDir = os.path.join(os.path.dirname(sys.executable), "Scripts")
            postScript = os.path.join(scriptsDir, "pywin32_postinstall.py")
            if os.path.exists(postScript):
                print("Running pywin32 post-install (this may take a moment)...")
                subprocess.check_call([sys.executable, postScript, "-install", "-silent"])
            print("pywin32 setup complete. You may need to re-run this command if import still fails.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Automatic install failed: {e}")
            print("Please manually install in your .venv:")
            print("  .venv\\Scripts\\python.exe -m pip install pywin32")
            print("  Then run: .venv\\Scripts\\pywin32_postinstall.py -install (elevated if prompted)")
            return False

def getServiceClass():
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager

    config = loadServiceConfig()

    class ScriptRunnerService(win32serviceutil.ServiceFramework):
        _svc_name_ = config.get("name", "ScriptRunnerService")
        _svc_display_name_ = config.get("displayName", config.get("name", "Script Runner Service"))
        _svc_description_ = config.get("description", "Python program hosted as Windows service")

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stopEvent = win32event.CreateEvent(None, 0, 0, None)
            self.isRunning = True
            self.childProcess = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stopEvent)
            self.isRunning = False

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "")
            )
            self.main()

        def main(self):
            try:
                cfg = loadServiceConfig()
                targetScript = cfg.get("targetScript", "")
                if not targetScript:
                    servicemanager.LogErrorMsg("No targetScript found in serviceConfig.json")
                    return

                baseDir = os.path.dirname(os.path.abspath(__file__))
                scriptPath = os.path.join(baseDir, targetScript)
                if not os.path.isfile(scriptPath):
                    servicemanager.LogErrorMsg(f"Target script missing: {scriptPath}")
                    return

                venvDir = os.path.join(baseDir, ".venv")
                pythonExe = os.path.join(venvDir, "Scripts", "python.exe")
                if not os.path.isfile(pythonExe):
                    pythonExe = sys.executable
                    servicemanager.LogWarningMsg(".venv python.exe not found, using current interpreter as fallback.")

                logDir = baseDir
                if not os.path.exists(logDir):
                    os.makedirs(logDir)
                logPath = os.path.join(logDir, "serviceWrapper.log")

                self.ReportServiceStatus(win32service.SERVICE_RUNNING)

                with open(logPath, "a", encoding="utf-8") as logFile:
                    logFile.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] === Service starting ===\n")
                    logFile.write(f"Launching: {targetScript} using {pythonExe}\n")

                    creationFlags = 0
                    if os.name == "nt":
                        creationFlags = subprocess.CREATE_NO_WINDOW

                    self.childProcess = subprocess.Popen(
                        [pythonExe, scriptPath],
                        cwd=baseDir,
                        stdout=logFile,
                        stderr=subprocess.STDOUT,
                        text=True,
                        creationflags=creationFlags
                    )
                    logFile.write(f"Child PID: {self.childProcess.pid}\n")

                    restartCount = 0
                    maxRestarts = 5
                    while self.isRunning:
                        if self.childProcess.poll() is not None:
                            exitCode = self.childProcess.returncode
                            logFile.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Child exited (code {exitCode}). ")
                            if restartCount < maxRestarts and self.isRunning:
                                logFile.write("Attempting restart...\n")
                                restartCount += 1
                                time.sleep(min(5 * restartCount, 30))
                                self.childProcess = subprocess.Popen(
                                    [pythonExe, scriptPath],
                                    cwd=baseDir,
                                    stdout=logFile,
                                    stderr=subprocess.STDOUT,
                                    text=True,
                                    creationflags=creationFlags
                                )
                                logFile.write(f"Restarted. New PID: {self.childProcess.pid}\n")
                                continue
                            else:
                                logFile.write("Max restarts reached or service stopping.\n")
                                break

                        waitResult = win32event.WaitForSingleObject(self.stopEvent, 2000)
                        if waitResult == win32event.WAIT_OBJECT_0:
                            logFile.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Stop signal received.\n")
                            break

                    if self.childProcess and self.childProcess.poll() is None:
                        logFile.write("Terminating child process...\n")
                        self.childProcess.terminate()
                        try:
                            self.childProcess.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            logFile.write("Child unresponsive, forcing kill.\n")
                            self.childProcess.kill()

            except Exception as err:
                try:
                    servicemanager.LogErrorMsg(f"Error in main loop: {str(err)}")
                except:
                    pass
            finally:
                try:
                    self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                except:
                    pass

    return ScriptRunnerService

if __name__ == "__main__":
    hasCustom = any(
        arg in ["--name", "--script", "--description", "--displayName", "--start", "--stop", "--remove", "--install"]
        for arg in sys.argv
    )

    if hasCustom:
        if not ensurePywin32():
            sys.exit(1)

        ScriptRunnerService = getServiceClass()

        parser = argparse.ArgumentParser(
            description="Universal Windows Service wrapper. Place in program root next to .venv and your main .py"
        )
        parser.add_argument("--name", type=str, default=None, help="Service name (internal, no spaces recommended)")
        parser.add_argument("--description", type=str, default="Python program running as Windows service")
        parser.add_argument("--script", dest="targetScript", type=str, default=None, help="Main .py filename to execute (e.g. main.py)")
        parser.add_argument("--displayName", dest="displayName", type=str, default=None, help="Friendly display name")
        parser.add_argument("--start", action="store_true", help="Start the service (requires --name or config)")
        parser.add_argument("--stop", action="store_true", help="Stop the service (requires --name or config)")
        parser.add_argument("--remove", action="store_true", help="Remove/uninstall the service (requires --name or config)")

        args = parser.parse_args()

        if args.targetScript and args.name:
            # INSTALL / SETUP
            configData = {
                "name": args.name,
                "description": args.description,
                "targetScript": args.targetScript,
                "displayName": args.displayName or args.name
            }
            scriptDir = os.path.dirname(os.path.abspath(__file__))
            configPath = os.path.join(scriptDir, "serviceConfig.json")
            with open(configPath, "w", encoding="utf-8") as f:
                json.dump(configData, f, indent=2)
            print(f"Configuration written: {configPath}")

            try:
                moduleBase = os.path.splitext(os.path.basename(__file__))[0]
                pythonClassString = f"{moduleBase}.ScriptRunnerService"

                win32serviceutil = __import__("win32serviceutil")
                win32service = __import__("win32service")

                win32serviceutil.InstallService(
                    pythonClassString=pythonClassString,
                    serviceName=args.name,
                    displayName=configData["displayName"],
                    description=args.description,
                    startType=win32service.SERVICE_AUTO_START,
                    errorControl=win32service.SERVICE_ERROR_NORMAL,
                )
                print(f"\nService '{args.name}' installed successfully!")
                print("To start: sc start " + args.name)
                print("Or: python service.py start")
                print("Logs will appear in ./logs/ next to this script.")
            except Exception as ex:
                print(f"InstallService failed: {ex}")
                print("Tip: If service already exists, run with --remove first (using same --name).")

        elif args.start and (args.name or True):
            serviceName = args.name or loadServiceConfig().get("name")
            if serviceName:
                try:
                    win32serviceutil = __import__("win32serviceutil")
                    win32serviceutil.StartService(serviceName)
                    print(f"Start requested for '{serviceName}'")
                except Exception as ex:
                    print(f"Start failed: {ex}")
            else:
                print("No service name provided or in config.")

        elif args.stop and (args.name or True):
            serviceName = args.name or loadServiceConfig().get("name")
            if serviceName:
                try:
                    win32serviceutil = __import__("win32serviceutil")
                    win32serviceutil.StopService(serviceName)
                    print(f"Stop requested for '{serviceName}'")
                except Exception as ex:
                    print(f"Stop failed: {ex}")
            else:
                print("No service name provided or in config.")

        elif args.remove and (args.name or True):
            serviceName = args.name or loadServiceConfig().get("name")
            if serviceName:
                try:
                    win32serviceutil = __import__("win32serviceutil")
                    win32serviceutil.RemoveService(serviceName)
                    print(f"Service '{serviceName}' removed.")
                    configPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceConfig.json")
                    if os.path.exists(configPath):
                        os.remove(configPath)
                        print("Local config file also deleted.")
                except Exception as ex:
                    print(f"Remove failed: {ex}")
            else:
                print("No service name provided or in config.")

        else:
            print("Usage for install:")
            print("  .venv\\Scripts\\python.exe service.py --name MyService --script main.py --description \"Does cool stuff\"")
            print("\nAfter install, manage with:")
            print("  python service.py start")
            print("  python service.py stop")
            print("  python service.py remove")
            print("  (or add --name MyService to any of the above)")

    else:
        # Standard path: python service.py start | stop | debug | install (after config exists)
        try:
            ScriptRunnerService = getServiceClass()
        except ImportError:
            print("pywin32 is required.")
            print("Run once with --name and --script using your .venv python to auto-install it.")
            sys.exit(1)

        import win32serviceutil
        win32serviceutil.HandleCommandLine(ScriptRunnerService)
