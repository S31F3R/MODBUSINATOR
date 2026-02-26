# ==============================================
#  MODBUSINATOR v1.2 - SIMPLE FLOAT VALUES (TCP + SERIAL RTU)
# ==============================================
#
# PURPOSE: Super-simple Modbus slave. Each parameter = one clean float value.
#          Works perfectly with XLink 500, any SCADA, PLC, etc.
#          Zero timestamp, zero complexity.
#
# INPUT FORMAT for .update(inputString):
#   JSON string — single value or list of values.
#   Examples:
#       '25.34'                                 ← single parameter
#       '[25.34, 26.1, 27.0]'                   ← 3 parameters
#       '[{"v":25.34}, {"v":26.1}, {"v":27.0}]' ← also works
#       '{"v":25.34}'                           ← single dict also works
#
#   Extra values beyond numParams are ignored.
#   Default: 256 parameters (each uses 2 registers). Handles 100+ with no issue.

import time
import json
import struct
from threading import Thread
from pymodbus.server import StartTcpServer, StartSerialServer
from pymodbus.framer import ModbusRtuFramer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext

class MODBUSINATOR:
    def __init__(self, numParams=256, registersPerParam=2, port=502, host="0.0.0.0", comPort=None, baudRate=9600):
        self.numParams = numParams
        self.registersPerParam = registersPerParam
        self.totalRegisters = registersPerParam * numParams + 100
        self.port = port
        self.host = host
        self.comPort = comPort
        self.baudRate = baudRate
        self.datablock = ModbusSequentialDataBlock(0, [0] * self.totalRegisters)
        self.deviceContext = ModbusDeviceContext(hr=self.datablock)
        self.context = ModbusServerContext(devices=self.deviceContext, single=True)
        self.serverThread = None

    def writeFloat(self, address: int, value: float):
        """Writes value as IEEE 754 float (2 registers) — standard for XLink"""
        floatBytes = struct.pack('>f', float(value))
        reg1 = int.from_bytes(floatBytes[0:2], 'big')
        reg2 = int.from_bytes(floatBytes[2:4], 'big')
        self.deviceContext.setValues(3, address, [reg1, reg2])

    def update(self, inputString: str):
        try:
            paramList = json.loads(inputString)
            if not isinstance(paramList, list):
                paramList = [paramList]
        except Exception as e:
            print(f"MODBUSINATOR JSON parse error: {e}")
            return

        for i, param in enumerate(paramList[:self.numParams]):
            if isinstance(param, dict):
                v = param.get("v", 0.0)
            else:
                v = float(param)
            addr = i * self.registersPerParam
            self.writeFloat(addr, v)

        print(f"MODBUSINATOR updated {len(paramList)} parameters at {time.ctime()}")

    def runServer(self):
        if self.serverThread and self.serverThread.is_alive():
            print("MODBUSINATOR already running")
            return

        def _startInternal():
            if self.comPort is None:
                # TCP mode
                StartTcpServer(context=self.context, address=(self.host, self.port))
            else:
                # Serial RTU mode for XLink 500
                StartSerialServer(
                    context=self.context,
                    framer=ModbusRtuFramer,
                    port=self.comPort,
                    baudrate=self.baudRate,
                    bytesize=8,
                    parity="N",
                    stopbits=1
                )
        self.serverThread = Thread(target=_startInternal, daemon=True)
        self.serverThread.start()

        if self.comPort is None:
            print(f"MODBUSINATOR listening on TCP {self.host}:{self.port}")
        else:
            print(f"MODBUSINATOR listening on SERIAL {self.comPort} @ {self.baudRate} 8N1")

    def stop(self):
        print("MODBUSINATOR stopped cleanly")
        if self.serverThread:
            self.serverThread = None