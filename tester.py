import json
import time
from modbusinator import MODBUSINATOR
from pymodbus.client import ModbusTcpClient

numParams = 3
registersPerParam = 32
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
    result = client.read_holding_registers(0, count=totalToRead)

    if result.isError():
        print("Read error:", result)
        return
    dataBytes = b''.join(reg.to_bytes(2, 'big') for reg in result.registers)

    for i in range(numParams):
        start = i * registersPerParam * 2
        end = start + registersPerParam * 2
        rawBytes = dataBytes[start:end]
        rawString = rawBytes.decode('utf-8', errors='ignore').rstrip('\0').strip()

        if rawString:
            try:
                parsed = json.loads(rawString)
                print(f"Param {i+1:2d} | ts={parsed.get('ts')} | v={parsed.get('v')}")
            except:
                print(f"Param {i+1:2d} | (bad JSON) {rawString[:80]}...")
        else:
            print(f"Param {i+1:2d} | empty")
    print("=" * 50)

mb = MODBUSINATOR(numParams=numParams, registersPerParam=registersPerParam, port=port)
mb.runServer()
time.sleep(3) # let server start
client = ModbusTcpClient("127.0.0.1", port=port)

if not client.connect():
    print("Client could not connect")
    mb.stop()
    exit()
try:
    for idx, snapshot in enumerate(testSnapshots):
        currentMinute = idx * 15
        print(f"\n--- Feeding test snapshot {idx+1}/5 for minute {currentMinute} ---")
        inputString = json.dumps(snapshot)
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
