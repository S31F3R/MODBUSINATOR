# ==============================================
#  MODBUSINATOR v1.0
# ==============================================

import time
import json
from threading import Thread
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext

class MODBUSINATOR:
    def __init__(self, numParams=20, registersPerParam=32, port=502, host="0.0.0.0"):
        self.numParams = numParams
        self.registersPerParam = registersPerParam
        self.totalRegisters = registersPerParam * numParams + 100
        self.port = port
        self.host = host
        self.datablock = ModbusSequentialDataBlock(0, [0] * self.totalRegisters)
        self.deviceContext = ModbusDeviceContext(hr=self.datablock)
        self.context = ModbusServerContext(devices=self.deviceContext, single=True)
        self.server = None
        self.serverThread = None

    def updateParameter(self, address: int, dataString: str):
        """Takes a JSON string (value+timestamp) and writes it to a fixed register block"""
        maxBytes = self.registersPerParam * 2
        byteData = dataString.encode('utf-8')

        if len(byteData) > maxBytes:
            byteData = byteData[:maxBytes]
        else:
            byteData = byteData.ljust(maxBytes, b'\0')
        registerList = []

        for i in range(0, len(byteData), 2):
            registerList.append(int.from_bytes(byteData[i:i+2], 'big'))
        self.deviceContext.setValues(3, address, registerList)

    def update(self, inputString: str):
        try:
            paramList = json.loads(inputString)
            if not isinstance(paramList, list):
                paramList = [paramList]
        except Exception as e:
            print(f"MODBUSINATOR JSON parse error: {e}")
            return
        base = 0

        for i, param in enumerate(paramList[:self.numParams]):
            addr = base + (i * self.registersPerParam)
            dataString = json.dumps({
                "ts": param.get("ts", int(time.time())),
                "v": param.get("v", 0.0)
            })
            self.updateParameter(addr, dataString)   # ← THIS WAS MISSING - NOW FIXED

        print(f"MODBUSINATOR updated {len(paramList)} parameters at {time.ctime()}")

    def runServer(self):
        """Starts the MODBUS TCP server in background thread"""
        if self.serverThread and self.serverThread.is_alive():
            print("MODBUSINATOR already running")
            return

        def _startInternal():
            StartTcpServer(
                context=self.context,
                address=(self.host, self.port)
            )
        self.serverThread = Thread(target=_startInternal, daemon=True)
        self.serverThread.start()
        print(f"MODBUSINATOR listening on {self.host}:{self.port}")

    def stop(self):
        """Cleanly stops the server"""
        if self.serverThread and self.serverThread.is_alive():
            print("MODBUSINATOR shutdown command sent (daemon thread will end when program finishes)")
        if self.serverThread:
            self.serverThread = None
        print("MODBUSINATOR stopped cleanly")