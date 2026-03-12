import json
import time
import struct
from datetime import datetime
from modbusinator import MODBUSINATOR
from pymodbus.client import ModbusTcpClient

# ================== TESTER CONFIG ==================
numParams          = 100
registersPerParam  = 2
port               = 5020
comPort            = None            # None = TCP only (recommended for testing)
baudRate           = 9600
unitID             = 1
bytesize           = 8
parity             = "E"
stopbits           = 1
framerType         = "RTU"           # "RTU" or "ASCII"
registerType       = "HR"            # "HR" or "IR"
runMinutes         = "INF"           # number of minutes OR "INF" for infinite
intervalSeconds    = 60              # update interval in seconds
# =================================================

# ====================== SETUP =====================
mb = MODBUSINATOR(
    numParams=numParams,
    registersPerParam=registersPerParam,
    port=port,
    comPort=comPort,
    baudRate=baudRate,
    unitID=unitID,
    bytesize=bytesize,
    parity=parity,
    stopbits=stopbits,
    framerType=framerType,
    registerType=registerType
)

mb.runServer()
time.sleep(3)

client = ModbusTcpClient("127.0.0.1", port=port)
if not client.connect():
    print("Client could not connect")
    mb.stop()
    exit()

# Choose correct read function
readFunc = client.read_input_registers if registerType.upper() == "IR" else client.read_holding_registers
regName  = "Input Registers" if registerType.upper() == "IR" else "Holding Registers"
print(f"\n=== TESTER STARTED ===\nUsing {regName} (Unit ID {unitID})\n")

# ====================== READ FUNCTION =====================
def readAndPrintRegisters(client, numParams, registersPerParam, currentTs):
    print(f"\n=== MODBUSINATOR REGISTERS AT {currentTs} ===")
    totalToRead = registersPerParam * numParams
    allRegisters = []
    maxPerRead = 124

    for start in range(0, totalToRead, maxPerRead):
        count = min(maxPerRead, totalToRead - start)
        result = readFunc(start, count=count)

        if result.isError():
            print("Read error:", result)
            return
        allRegisters.extend(result.registers)

    # Choose correct Modicon base (30001 for IR, 40001 for HR)
    modiconBase = 30001 if registerType.upper() == "IR" else 40001

    for i in range(numParams):
        rawAddr = i * registersPerParam
        modiconAddr = modiconBase + rawAddr
        idx = rawAddr
        reg1 = allRegisters[idx]
        reg2 = allRegisters[idx + 1]
        floatBytes = reg1.to_bytes(2, 'big') + reg2.to_bytes(2, 'big')
        v = struct.unpack('>f', floatBytes)[0]
        print(f"Raw:{rawAddr:4d} | Modicon:{modiconAddr:5d} | v={round(v, 2):6.2f}")

    print("=" * 50)

# ====================== MAIN LOOP =====================
try:
    startTime = time.time()
    iteration = 0

    while True:
        currentTs = datetime.now().strftime("%H:%M:%S")
        snapshot = [round(25.0 + (iteration * 0.1) + (p * 0.05), 2) for p in range(numParams)]
        inputString = json.dumps(snapshot)
        mb.update(inputString)
        readAndPrintRegisters(client, numParams, registersPerParam, currentTs)
        param100Reg = ((numParams - 1) * registersPerParam) + 1
        print(f">>> FORCE REG {param100Reg} NOW — should show exactly {snapshot[-1]} (Param 100) <<<")

        if runMinutes != "INF":
            elapsedMinutes = (time.time() - startTime) / 60

            if elapsedMinutes >= runMinutes:
                print(f"\nReached {runMinutes} minutes — stopping test.")
                break
        time.sleep(intervalSeconds)
        iteration += 1

except KeyboardInterrupt:
    print("\nTest interrupted by user")
finally:
    client.close()
    mb.stop()
    print("\nTest finished. MODBUSINATOR stopped.")