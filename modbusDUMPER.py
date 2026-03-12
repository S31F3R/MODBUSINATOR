# ==============================================
#  modbusDUMPER.py - Modbus Scanner
# ==============================================

import json
import time
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus import FramerType

# ================== DUMPER CONFIG ==================
connectionType = "TCP"          # "TCP" or "SERIAL"
comPort        = "COM1"         # only used if connectionType = "SERIAL"
baudRate       = 9600
parity         = "E"            # "N", "E", "O"
stopbits       = 1
bytesize       = 8
framerType     = FramerType.RTU # FramerType.RTU or FramerType.ASCII

registerType   = "HR"           # "HR" or "IR"
unitID         = 1

# What range to scan
startParam     = 1              # first parameter to show
numParamsToScan = 50            # how many parameters to dump (or set to 0 for all)
# =================================================

# ====================== SETUP =====================
if connectionType.upper() == "TCP":
    client = ModbusTcpClient("127.0.0.1", port=5025)
    connDesc = f"TCP 127.0.0.1:5025 (Unit ID {unitID})"
else:
    client = ModbusSerialClient(
        port=comPort,
        baudrate=baudRate,
        parity=parity,
        stopbits=stopbits,
        bytesize=bytesize,
        framer=framerType
    )
    connDesc = f"SERIAL {comPort} @ {baudRate} 8{parity}{stopbits} (Unit ID {unitID})"

if not client.connect():
    print("Failed to connect to Modbus device")
    exit()
regName = "Input Registers" if registerType.upper() == "IR" else "Holding Registers"
modiconBase = 30001 if registerType.upper() == "IR" else 40001
readFunc = client.read_input_registers if registerType.upper() == "IR" else client.read_holding_registers
print(f"\n=== MODBUSDUMPER STARTED ===")
print(f"Connection : {connDesc}")
print(f"Register Type : {regName}")
print(f"Scanning params {startParam} to {startParam + numParamsToScan - 1}\n")
print(f"{'Param':>5} | {'Raw Addr':>8} | {'Modicon Addr':>12} | Value")
print("-" * 55)

# ====================== SCAN =====================
for p in range(startParam, startParam + numParamsToScan):
    rawAddr = (p - 1) * 2
    modiconAddr = modiconBase + rawAddr
    result = readFunc(rawAddr, count=2)

    if result.isError():
        print(f"{p:5d} | {rawAddr:8d} | {modiconAddr:12d} | READ ERROR")
        continue
    reg1 = result.registers[0]
    reg2 = result.registers[1]
    floatBytes = reg1.to_bytes(2, 'big') + reg2.to_bytes(2, 'big')
    v = struct.unpack('>f', floatBytes)[0]
    print(f"{p:5d} | {rawAddr:8d} | {modiconAddr:12d} | {v:8.2f}")

print("\nScan complete.")
client.close()