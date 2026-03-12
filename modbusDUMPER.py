# ==============================================
#  MODBUSDUMPER.PY - Modbus Scanner / Insight Tool
# ==============================================
#
# Usage examples:
#   python modbusDUMPER.py --help
#   python modbusDUMPER.py --connection TCP --register HR
#   python modbusDUMPER.py --connection SERIAL --comPort COM1 --baud 9600 --register IR

import argparse
import json
import time
import struct
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus import FramerType
from pymodbus.exceptions import ModbusIOException

# ====================== ARGUMENT PARSER ======================
parser = argparse.ArgumentParser(description="MODBUSDUMPER - Modbus Scanner & Insight Tool")

parser.add_argument("--connection",   choices=["TCP", "SERIAL"], default="TCP", help="Connection type")
parser.add_argument("--comPort",      default="COM1",           help="COM port (used only with SERIAL)")
parser.add_argument("--baud",         type=int, default=9600,   help="Baud rate")
parser.add_argument("--parity",       choices=["N", "E", "O"], default="E", help="Parity (N=None, E=Even, O=Odd)")
parser.add_argument("--stopbits",     type=int, choices=[1,2], default=1, help="Stop bits")
parser.add_argument("--bytesize",     type=int, default=8,      help="Byte size")
parser.add_argument("--framer",       choices=["RTU", "ASCII"], default="RTU", help="Framer type")
parser.add_argument("--register",     choices=["HR", "IR"], default="HR", help="Register type")
parser.add_argument("--unitID",       type=int, default=1,      help="Unit / Slave ID")
parser.add_argument("--startParam",   type=int, default=1,      help="First parameter to scan")
parser.add_argument("--numParams",    type=int, default=100,    help="Number of parameters to scan (0 = all)")

args = parser.parse_args()

# ====================== SETUP =====================
if args.connection.upper() == "TCP":
    client = ModbusTcpClient("127.0.0.1", port=5025)
    connDesc = f"TCP 127.0.0.1:5025 (Unit ID {args.unitID})"
else:
    client = ModbusSerialClient(
        port=args.comPort,
        baudrate=args.baud,
        parity=args.parity,
        stopbits=args.stopbits,
        bytesize=args.bytesize,
        framer=getattr(FramerType, args.framer)
    )
    connDesc = f"SERIAL {args.comPort} @ {args.baud} 8{args.parity}{args.stopbits} (Unit ID {args.unitID})"

if not client.connect():
    print("Failed to connect to Modbus device")
    exit()

regName = "Input Registers" if args.register.upper() == "IR" else "Holding Registers"
modiconBase = 30001 if args.register.upper() == "IR" else 40001
readFunc = client.read_input_registers if args.register.upper() == "IR" else client.read_holding_registers

print(f"\n=== MODBUSDUMPER STARTED ===")
print(f"Connection     : {connDesc}")
print(f"Register Type  : {regName}")
print(f"Scanning       : Param {args.startParam} → {args.startParam + args.numParams - 1}\n")
print(f"{'Param':>5} | {'Raw Addr':>8} | {'Modicon Addr':>12} | Value")
print("-" * 60)

# ====================== SCAN =====================
for p in range(args.startParam, args.startParam + args.numParams):
    rawAddr = (p - 1) * 2
    modiconAddr = modiconBase + rawAddr

    try:
        result = readFunc(rawAddr, count=2)

        if result.isError():
            print(f"{p:5d} | {rawAddr:8d} | {modiconAddr:12d} | READ ERROR")
            continue

        reg1 = result.registers[0]
        reg2 = result.registers[1]
        floatBytes = reg1.to_bytes(2, 'big') + reg2.to_bytes(2, 'big')
        v = struct.unpack('>f', floatBytes)[0]
        print(f"{p:5d} | {rawAddr:8d} | {modiconAddr:12d} | {v:8.2f}")

    except ModbusIOException:
        print(f"{p:5d} | {rawAddr:8d} | {modiconAddr:12d} | NO RESPONSE")
    except Exception as e:
        print(f"{p:5d} | {rawAddr:8d} | {modiconAddr:12d} | ERROR: {e}")

print("\nScan complete.")
client.close()