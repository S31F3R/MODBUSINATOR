# ==============================================
#  MODBUSINATOR v1.6 - XLINK 500 READY (wordSwap=True)
# ==============================================
#
# For XLink 500:
#   Use wordSwap=True
#   Reg Number = (Param - 1) * 2 + 1
#   MSW = Low Reg
#   Example: Param 1 → Reg 1
#            Param 100 → Reg 199
#
# All other devices usually work with wordSwap=False (default)

import time
import json
import struct
from threading import Thread
from pymodbus.server import StartTcpServer, StartSerialServer
from pymodbus import FramerType
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext

class MODBUSINATOR:
    def __init__(self, numParams=256, registersPerParam=2, port=502, host="0.0.0.0", 
                 comPort=None, baudRate=19200, wordSwap=False):
        self.numParams = numParams
        self.registersPerParam = registersPerParam
        self.totalRegisters = registersPerParam * numParams + 100
        self.port = port
        self.host = host
        self.comPort = comPort
        self.baudRate = baudRate
        self.wordSwap = wordSwap
        self.datablock = ModbusSequentialDataBlock(0, [0] * self.totalRegisters)
        self.deviceContext = ModbusDeviceContext(hr=self.datablock)
        self.context = ModbusServerContext(devices=self.deviceContext, single=True)
        self.threads = []

    def writeFloat(self, address: int, value: float):
        """IEEE 754 float - supports wordSwap for XLink 500"""
        floatBytes = struct.pack('>f', float(value))   # always big-endian first
        
        if self.wordSwap:
            # XLink wants low word first
            reg1 = int.from_bytes(floatBytes[2:4], 'big')   # LSW
            reg2 = int.from_bytes(floatBytes[0:2], 'big')   # MSW
        else:
            # Normal order
            reg1 = int.from_bytes(floatBytes[0:2], 'big')   # MSW
            reg2 = int.from_bytes(floatBytes[2:4], 'big')   # LSW
            
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
        if self.threads:
            print("MODBUSINATOR already running")
            return
        self.threads = []

        def _tcp():
            StartTcpServer(context=self.context, address=(self.host, self.port))
        t1 = Thread(target=_tcp, daemon=True)
        t1.start()
        self.threads.append(t1)
        print(f"MODBUSINATOR TCP listening on {self.host}:{self.port}")

        if self.comPort:
            def _serial():
                StartSerialServer(
                    context=self.context,
                    framer=FramerType.RTU,
                    port=self.comPort,
                    baudrate=self.baudRate,
                    bytesize=8,
                    parity="E",
                    stopbits=1
                )
            t2 = Thread(target=_serial, daemon=True)
            t2.start()
            self.threads.append(t2)
            print(f"MODBUSINATOR SERIAL listening on {self.comPort} @ {self.baudRate} 8E1")

    def stop(self):
        print("MODBUSINATOR stopped cleanly")
        self.threads = []