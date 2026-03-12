# ==============================================
#  MODBUSDUMPER.PY - Modbus Scanner / Insight Tool
# ==============================================
#
# Usage examples:
#   python modbusDUMPER.py --help
#   python modbusDUMPER.py --port 5020 --connection TCP --register HR
#   python modbusDUMPER.py --port 5020 --connection SERIAL --comPort COM1

import argparse
import struct
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus import FramerType
from pymodbus.exceptions import ModbusIOException

# ====================== ARGUMENT PARSER ======================
parser = argparse.ArgumentParser(description="MODBUSDUMPER - Modbus Scanner & Insight Tool")
parser.add_argument("--port", type=int, default=5020, help="TCP port (default 5020)")
parser.add_argument("--connection", choices=["TCP", "SERIAL"], type=str.upper, default="TCP", help="Connection type")
parser.add_argument("--comPort", default="COM1", help="COM port (used only with SERIAL)")
parser.add_argument("--baud", type=int, default=9600, help="Baud rate")
parser.add_argument("--parity", choices=["N", "E", "O"], type=str.upper, default="E", help="Parity (N=None, E=Even, O=Odd)")
parser.add_argument("--stopbits", type=int, choices=[1,2], default=1, help="Stop bits")
parser.add_argument("--bytesize", type=int, default=8, help="Byte size")
parser.add_argument("--framer", choices=["RTU", "ASCII"], type=str.upper, default="RTU", help="Framer type")
parser.add_argument("--register", choices=["HR", "IR"], type=str.upper, default="HR", help="Register type")
parser.add_argument("--unitID", type=int, default=1, help="Unit / Slave ID")
parser.add_argument("--startParam", type=int, default=1, help="First parameter to scan")
parser.add_argument("--numParams", type=int, default=0, help="Number of parameters to scan (0 = scan ALL)")
parser.add_argument("--host", default="127.0.0.1", help="IP address of the Modbus server (default 127.0.0.1 for localhost)")
args = parser.parse_args()

# ====================== SETUP =====================
if args.connection.upper() == "TCP":
    client = ModbusTcpClient(args.host, port=args.port)
    connDesc = f"TCP {args.host}:{args.port} (Unit ID {args.unitID})"
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

# If user passes 0, scan ALL (up to 256)
numToScan = args.numParams if args.numParams > 0 else 256

print(f"\n=== MODBUSDUMPER STARTED ===")
print(f"Connection     : {connDesc}")
print(f"Register Type  : {regName}")
print(f"Scanning       : Param {args.startParam} → {args.startParam + numToScan - 1}\n")

# ====================== SCAN =====================
for p in range(args.startParam, args.startParam + numToScan):
    rawAddr = (p - 1) * 2
    modiconAddr = modiconBase + rawAddr

    try:
        result = readFunc(rawAddr, count=2)

        if result.isError():
            print(f"{rawAddr:8d} | {modiconAddr:12d} | READ ERROR")
            continue
        reg1 = result.registers[0]
        reg2 = result.registers[1]
        floatBytes = reg1.to_bytes(2, 'big') + reg2.to_bytes(2, 'big')
        v = struct.unpack('>f', floatBytes)[0]
        print(f"Raw:{rawAddr:8d} | Modicon:{modiconAddr:12d} | v={v:8.2f}")
    except ModbusIOException:
        print(f"Raw:{rawAddr:8d} | Modicon:{modiconAddr:12d} | NO RESPONSE")
    except Exception as e:
        print(f"Raw:{rawAddr:8d} | Modicon:{modiconAddr:12d} | ERROR: {e}")
print("\nScan complete.")
client.close()