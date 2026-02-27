import json
import time
import struct
from modbusinator import MODBUSINATOR
from pymodbus.client import ModbusTcpClient

numParams = 100
registersPerParam = 2
port = 502

# Simulate 1 hour of time-series changes
baseTs = 173999999
testSnapshots = []
for m in range(5):
    minute = m * 15
    snapshot = [
        {"ts": baseTs + minute * 60, "v": round(25.0 + (minute / 10.0) + (p * 0.1), 2)}
        for p in range(numParams)
    ]
    testSnapshots.append(snapshot)

def readAndPrintRegisters(client, numParams, registersPerParam, currentMinute):
    print(f"\n=== MODBUSINATOR REGISTERS AFTER MINUTE {currentMinute} ===")
    totalToRead = registersPerParam * numParams
    allRegisters = []
    maxPerRead = 124 # safe limit

    for start in range(0, totalToRead, maxPerRead):
        count = min(maxPerRead, totalToRead - start)
        result = client.read_holding_registers(start, count=count) 

        if result.isError():
            print("Read error:", result)
            return
        allRegisters.extend(result.registers)

    for i in range(numParams):
        idx = i * registersPerParam
        reg1 = allRegisters[idx]
        reg2 = allRegisters[idx + 1]
        floatBytes = reg1.to_bytes(2, 'big') + reg2.to_bytes(2, 'big')
        v = struct.unpack('>f', floatBytes)[0]
        print(f"Param {i+1:2d} | v={round(v, 2)}")
    print("=" * 50)

mb = MODBUSINATOR(numParams=numParams, registersPerParam=registersPerParam, comPort="COM1", baudRate=115200)
#mb = MODBUSINATOR(numParams=numParams, registersPerParam=registersPerParam)
mb.runServer()
time.sleep(3) # let both servers start
client = ModbusTcpClient("127.0.0.1", port=port)

if not client.connect():
    print("Client could not connect")
    mb.stop()
    exit()
try:
    for idx, snapshot in enumerate(testSnapshots):
        currentMinute = idx * 15
        print(f"\n--- Feeding test snapshot {idx+1}/5 for minute {currentMinute} ---")
        inputString = json.dumps([p["v"] for p in snapshot])
        mb.update(inputString)
        time.sleep(2) # let registers update
        readAndPrintRegisters(client, numParams, registersPerParam, currentMinute)
        time.sleep(60)
except KeyboardInterrupt:
    print("\nTest interrupted by user")
finally:
    client.close()
    mb.stop()
    print("\n test finished. MODBUSINATOR stopped." )
