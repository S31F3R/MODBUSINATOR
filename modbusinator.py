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
# registersPerParam=2        # 2 = Float (recommended)
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

import time
import json
import struct
from threading import Thread
from pymodbus.server import StartTcpServer, StartSerialServer
from pymodbus import FramerType
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext
from logic import initLogging, logMessage

# Enable logging
initLogging()

class MODBUSINATOR:
    def __init__(self, numParams=256, registersPerParam=2, port=5020, host="0.0.0.0",
                 comPort=None, baudRate=9600, unitID=1,
                 bytesize=8, parity="E", stopbits=1, framerType=FramerType.RTU,
                 registerType="HR"):
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
        self.framerType = framerType
        self.registerType = registerType.upper() # normalize to HR/IR
        self.datablock = ModbusSequentialDataBlock(0, [0] * self.totalRegisters)
        self.deviceContext = ModbusDeviceContext(**{self.registerType.lower(): self.datablock})
        self.context = ModbusServerContext(devices={self.unitID: self.deviceContext}, single=False)
        self.threads = []
        self.serialThread = None

    def writeFloat(self, address: int, value: float):
        floatBytes = struct.pack('>f', float(value))
        reg1 = int.from_bytes(floatBytes[0:2], 'big')
        reg2 = int.from_bytes(floatBytes[2:4], 'big')
        funcCode = 4 if self.registerType == "IR" else 3
        self.deviceContext.setValues(funcCode, address, [reg1, reg2])

    def update(self, inputString: str):
        try:
            paramList = json.loads(inputString)
            if not isinstance(paramList, list):
                paramList = [paramList]
        except Exception as e:
            logMessage('ERROR', f"MODBUSINATOR JSON parse error: {e}")
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

            # Address: zero-based; two 16-bit registers per 32-bit float
            addr = i * self.registersPerParam
            self.writeFloat(addr, val)
            writes += 1
        logMessage('INFO', f"MODBUSINATOR updated {writes} parameters at {time.ctime()}")

    def runServer(self):
        if self.threads:
            logMessage('INFO', "MODBUSINATOR already running")
            return
        self.threads = []

        def _tcp():
            StartTcpServer(context=self.context, address=(self.host, self.port))
        t1 = Thread(target=_tcp, daemon=True)
        t1.start()
        self.threads.append(t1)
        logMessage('INFO', f"MODBUSINATOR TCP listening on {self.host}:{self.port} (Unit ID {self.unitID})")

    def startSerial(self):
        if self.serialThread and self.serialThread.is_alive():
            logMessage('INFO', "Serial already running")
            return        

        # Convert framerType.RTU (or ASCII) to 'rtu' or 'ascii'
        framerStr = str(self.framerType).lower().split('.')[-1]
        
        def _serial():
            StartSerialServer(
                context=self.context,
                framer=framerStr,
                port=self.comPort,
                baudrate=self.baudRate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits
            )
        self.serialThread = Thread(target=_serial, daemon=True)
        self.serialThread.start()
        regName = "Input Registers" if self.registerType == "IR" else "Holding Registers"
        logMessage('INFO', f"MODBUSINATOR SERIAL listening on {self.comPort} @ {self.baudRate} {self.bytesize}{self.parity}{self.stopbits} ({regName}, Unit ID {self.unitID})")

    def stopSerial(self):
        if self.serialThread:
            logMessage('INFO', f"MODBUSINATOR SERIAL stopped on {self.comPort}")
            self.serialThread = None
            self.comPort = None

    def stop(self):
        logMessage('INFO', "MODBUSINATOR stopped cleanly")
        self.stopSerial()
        self.threads = []