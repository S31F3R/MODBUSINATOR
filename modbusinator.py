# ==============================================
#  MODBUSINATOR v1.0
# ==============================================
#
# INPUT FORMAT for .update(inputString):
#   JSON string — single value or list of values.
#   Examples:
#       '25.34'                                 ← single parameter
#       '[25.34, 26.1, 27.0]'                   ← 3 parameters
#       '[{"v":25.34}, {"v":26.1}, {"v":27.0}]' ← also works
#       '{"v":25.34}'                           ← single dict also works

# ==============================================
#  CONFIGURATION OPTIONS (passed to __init__)
# ==============================================
#
# numParams=256              # How many parameters to support
# registersPerParam=2        # Stride in 16-bit registers. Floats always use 2;
#                            # values < 2 are raised to 2. Values > 2 leave padding.
# port=5020                  # TCP port
# host="0.0.0.0"
# comPort=None               # None = TCP only (recommended default)
# baudRate=9600
# unitID=1
# bytesize=8
# parity="E"                 # "N", "E", "O"
# stopbits=1
# framerType=FramerType.RTU  # FramerType.ASCII for very old devices
# registerType="HR"          # "HR" or "IR" (case-insensitive)
# appName="MODBUSINATOR"     # logger name; pass the host app name when embedded
#                            # e.g. appName="SCADA Data Link"
#                            # If omitted, uses the name from initLogging() when the
#                            # host already called it, otherwise "MODBUSINATOR".

import asyncio
import time
import json
import struct
from contextlib import suppress
from threading import Event, Thread
from pymodbus import FramerType
from pymodbus.server import ModbusTcpServer, ModbusSerialServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext
import logic
from logic import initLogging, logMessage

floatRegisters = 2  # IEEE-754 float is always two 16-bit registers (ABCD)

def asFramerType(framerType):
    if isinstance(framerType, FramerType):
        return framerType
    if isinstance(framerType, str):
        try:
            return FramerType[framerType.upper()]
        except KeyError:
            names = [m.name for m in FramerType]
            raise ValueError(f"Unknown framerType {framerType!r}; expected one of {names}") from None
    raise TypeError(f"framerType must be FramerType or str, got {type(framerType).__name__}")

class MODBUSINATOR:
    def __init__(self, numParams=256, registersPerParam=2, port=5020, host="0.0.0.0",
                 comPort=None, baudRate=9600, unitID=1,
                 bytesize=8, parity="E", stopbits=1, framerType=FramerType.RTU,
                 registerType="HR", appName=None):
        if appName:
            initLogging(appName=appName)
            self.appName = appName
        elif logic.loggingInitialized:
            self.appName = logic.loggerName
        else:
            initLogging(appName='MODBUSINATOR')
            self.appName = 'MODBUSINATOR'
        if registersPerParam < floatRegisters:
            self.log('WARN', f"registersPerParam={registersPerParam} is too small for FLOAT32; using {floatRegisters}")
            registersPerParam = floatRegisters
        self.numParams = numParams
        self.registersPerParam = registersPerParam
        self.totalRegisters = registersPerParam * numParams + 100
        self.port = port
        self.host = host
        self.comPort = comPort
        self.baudRate = baudRate
        self.unitID = unitID
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.framerType = asFramerType(framerType)
        self.registerType = registerType.upper()
        if self.registerType not in ("HR", "IR"):
            raise ValueError(f"registerType must be 'HR' or 'IR', got {registerType!r}")
        self.datablock = ModbusSequentialDataBlock(0, [0] * self.totalRegisters)
        self.deviceContext = ModbusDeviceContext(**{self.registerType.lower(): self.datablock})
        self.context = ModbusServerContext(devices={self.unitID: self.deviceContext}, single=False)
        self.tcpServer = None
        self.tcpThread = None
        self.tcpReady = Event()
        self.serialServer = None
        self.serialThread = None
        self.serialReady = Event()
        self.threads = []

    def log(self, level, message):
        logMessage(level, message, appName=self.appName)

    def registerBankName(self):
        return "Input Registers" if self.registerType == "IR" else "Holding Registers"

    def writeFloat(self, address: int, value: float):
        # IEEE-754 big-endian float → two registers (ABCD). Stride is registersPerParam.
        floatBytes = struct.pack('>f', float(value))
        regs = [
            int.from_bytes(floatBytes[0:2], 'big'),
            int.from_bytes(floatBytes[2:4], 'big'),
        ]
        funcCode = 4 if self.registerType == "IR" else 3
        self.deviceContext.setValues(funcCode, address, regs)

    def update(self, inputString: str):
        try:
            paramList = json.loads(inputString)
            if not isinstance(paramList, list):
                paramList = [paramList]
        except Exception as e:
            self.log('ERROR', f"MODBUSINATOR JSON parse error: {e}")
            return
        writes = 0
        limit = min(len(paramList), self.numParams)

        for i in range(limit):
            param = paramList[i]

            # Normalize value for both list and dict forms
            if isinstance(param, dict):
                raw = param.get("v", None)
            else:
                raw = param

            # Treat "", whitespace-only strings, or None as blank → skip write
            if raw is None or (isinstance(raw, str) and raw.strip() == ""):
                continue

            # Convert to float safely; if conversion fails, skip this position
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue

            addr = i * self.registersPerParam
            self.writeFloat(addr, val)
            writes += 1
        self.log('INFO', f"MODBUSINATOR updated {writes} parameters at {time.ctime()}")

    def shutdownServer(self, server, thread, name):
        if server is not None:
            try:
                loop = server.loop
                if loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(server.shutdown(), loop)
                    future.result(timeout=5)
            except Exception as e:
                self.log('ERROR', f"MODBUSINATOR {name} shutdown error: {e}")
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)

    def runServer(self):
        if self.tcpThread and self.tcpThread.is_alive():
            self.log('INFO', "MODBUSINATOR already running")
            return

        self.tcpReady.clear()

        def runTcp():
            async def serve():
                server = ModbusTcpServer(
                    self.context,
                    address=(self.host, self.port),
                )
                self.tcpServer = server
                if not await server.listen():
                    raise RuntimeError(f"Could not bind {self.host}:{self.port}")
                self.tcpReady.set()
                with suppress(asyncio.exceptions.CancelledError):
                    await server.serving

            try:
                asyncio.run(serve())
            except Exception as e:
                self.log('ERROR', f"MODBUSINATOR TCP server error: {e}")
            finally:
                self.tcpReady.set()

        self.tcpThread = Thread(target=runTcp, daemon=True, name="modbusinator-tcp")
        self.tcpThread.start()
        if not self.tcpReady.wait(timeout=5) or self.tcpServer is None or not self.tcpThread.is_alive():
            self.log('ERROR', f"MODBUSINATOR TCP failed to start on {self.host}:{self.port}")
            self.tcpServer = None
            self.tcpThread = None
            return
        self.threads = [self.tcpThread]
        self.log(
            'INFO',
            f"MODBUSINATOR TCP listening on {self.host}:{self.port} "
            f"({self.registerBankName()}, Unit ID {self.unitID})"
        )

    def startSerial(self, comPort=None):
        if comPort is not None:
            self.comPort = comPort
        if not self.comPort:
            self.log('ERROR', "MODBUSINATOR SERIAL start requested with no COM port")
            return
        if self.serialThread and self.serialThread.is_alive():
            self.log('INFO', "Serial already running")
            return

        port = self.comPort
        self.serialReady.clear()

        def runSerial():
            async def serve():
                server = ModbusSerialServer(
                    self.context,
                    framer=self.framerType,
                    port=port,
                    baudrate=self.baudRate,
                    bytesize=self.bytesize,
                    parity=self.parity,
                    stopbits=self.stopbits,
                )
                self.serialServer = server
                if not await server.listen():
                    raise RuntimeError(f"Could not open serial port {port}")
                self.serialReady.set()
                with suppress(asyncio.exceptions.CancelledError):
                    await server.serving

            try:
                asyncio.run(serve())
            except Exception as e:
                self.log('ERROR', f"MODBUSINATOR SERIAL server error: {e}")
            finally:
                self.serialReady.set()

        self.serialThread = Thread(target=runSerial, daemon=True, name="modbusinator-serial")
        self.serialThread.start()
        if not self.serialReady.wait(timeout=5) or self.serialServer is None or not self.serialThread.is_alive():
            self.log('ERROR', f"MODBUSINATOR SERIAL failed to start on {port}")
            self.serialServer = None
            self.serialThread = None
            return
        if self.serialThread not in self.threads:
            self.threads.append(self.serialThread)
        self.log(
            'INFO',
            f"MODBUSINATOR SERIAL listening on {self.comPort} @ {self.baudRate} "
            f"{self.bytesize}{self.parity}{self.stopbits} "
            f"({self.registerBankName()}, Unit ID {self.unitID})"
        )

    def stopSerial(self):
        server, thread, port = self.serialServer, self.serialThread, self.comPort
        self.serialServer = None
        self.serialThread = None
        if server is None and thread is None:
            return
        self.shutdownServer(server, thread, "SERIAL")
        if thread in self.threads:
            self.threads.remove(thread)
        self.log('INFO', f"MODBUSINATOR SERIAL stopped on {port}")

    def stop(self):
        self.stopSerial()
        server, thread = self.tcpServer, self.tcpThread
        self.tcpServer = None
        self.tcpThread = None
        self.shutdownServer(server, thread, "TCP")
        self.threads = []
        self.log('INFO', "MODBUSINATOR stopped cleanly")
