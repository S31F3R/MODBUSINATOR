# ==============================================
#  MODBUSDUMPER.PY - Modbus Scanner / Insight Tool
# ==============================================
#
# Usage examples:
#   python modbusDUMPER.py --help
#   python modbusDUMPER.py --port 5020 --connection TCP --register HR
#   python modbusDUMPER.py --connection SERIAL --comPort COM1
#   python modbusDUMPER.py --dataType FLOAT32 --byteOrder CDAB
#   python modbusDUMPER.py --dataType UINT16

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
parser.add_argument("--framer", choices=["RTU", "ASCII", "SOCKET"], type=str.upper, default=None,
                    help="Framer type (default SOCKET for TCP, RTU for SERIAL). Use RTU for RTU-over-TCP tunnels.")
parser.add_argument("--register", choices=["HR", "IR"], type=str.upper, default="HR", help="Register type")
parser.add_argument("--dataType", choices=["INT16", "UINT16", "INT32", "UINT32", "FLOAT32"], type=str.upper, default="FLOAT32", help="Data type to decode (default FLOAT32)")
parser.add_argument("--byteOrder", choices=["ABCD", "CDAB", "BADC", "DCBA"], type=str.upper, default="ABCD", help="Byte/word order for 32-bit types (default ABCD). Ignored for 16-bit types")
parser.add_argument("--unitID", type=int, default=1, help="Unit / Slave ID")
parser.add_argument("--startParam", type=int, default=1, help="First parameter to scan")
parser.add_argument("--numParams", type=int, default=0, help="Number of parameters to scan (0 = scan ALL)")
parser.add_argument("--host", default="127.0.0.1", help="IP address of the Modbus server (default 127.0.0.1 for localhost)")
args = parser.parse_args()

# ====================== DATA TYPE INFO =====================
# regCount = how many 16-bit registers this type consumes
# is32bit  = whether byteOrder applies
typeInfo = {
    "INT16":   {"regCount": 1, "is32bit": False},
    "UINT16":  {"regCount": 1, "is32bit": False},
    "INT32":   {"regCount": 2, "is32bit": True},
    "UINT32":  {"regCount": 2, "is32bit": True},
    "FLOAT32": {"regCount": 2, "is32bit": True},
}
regCount = typeInfo[args.dataType]["regCount"]
is32bit = typeInfo[args.dataType]["is32bit"]

# ====================== DECODE HELPERS =====================
def orderBytes(reg1, reg2, order):
    # reg1 = first register read, reg2 = second register read
    # Each register is 2 bytes big-endian: reg -> (hi, lo)
    a, b = reg1.to_bytes(2, 'big')   # bytes A, B
    c, d = reg2.to_bytes(2, 'big')   # bytes C, D
    layout = {
        "ABCD": bytes([a, b, c, d]),
        "CDAB": bytes([c, d, a, b]),
        "BADC": bytes([b, a, d, c]),
        "DCBA": bytes([d, c, b, a]),
    }
    return layout[order]

def decodeValue(registers):
    if not is32bit:
        raw = registers[0]
        if args.dataType == "INT16":
            return struct.unpack('>h', raw.to_bytes(2, 'big'))[0]
        else:  # UINT16
            return raw
    orderedBytes = orderBytes(registers[0], registers[1], args.byteOrder)
    if args.dataType == "INT32":
        return struct.unpack('>i', orderedBytes)[0]
    elif args.dataType == "UINT32":
        return struct.unpack('>I', orderedBytes)[0]
    else:  # FLOAT32
        return struct.unpack('>f', orderedBytes)[0]

# ====================== SETUP =====================
if args.framer is None:
    args.framer = "RTU" if args.connection.upper() == "SERIAL" else "SOCKET"
framer = getattr(FramerType, args.framer)

if args.connection.upper() == "TCP":
    client = ModbusTcpClient(args.host, port=args.port, framer=framer)
    connDesc = f"TCP {args.host}:{args.port} framer={args.framer} (Unit ID {args.unitID})"
else:
    client = ModbusSerialClient(
        port=args.comPort,
        baudrate=args.baud,
        parity=args.parity,
        stopbits=args.stopbits,
        bytesize=args.bytesize,
        framer=framer
    )

    connDesc = f"SERIAL {args.comPort} @ {args.baud} {args.bytesize}{args.parity}{args.stopbits} framer={args.framer} (Unit ID {args.unitID})"
if not client.connect():
    print("Failed to connect to Modbus device")
    exit()
regName = "Input Registers" if args.register.upper() == "IR" else "Holding Registers"
modiconBase = 30001 if args.register.upper() == "IR" else 40001
readFunc = client.read_input_registers if args.register.upper() == "IR" else client.read_holding_registers

# If user passes 0, scan ALL (up to 256)
numToScan = args.numParams if args.numParams > 0 else 256

orderDesc = args.byteOrder if is32bit else "N/A (16-bit)"

print(f"\n=== MODBUSDUMPER STARTED ===")
print(f"Connection     : {connDesc}")
print(f"Register Type  : {regName}")
print(f"Data Type      : {args.dataType}")
print(f"Byte Order     : {orderDesc}")
print(f"Scanning       : Param {args.startParam} → {args.startParam + numToScan - 1}\n")

# ====================== SCAN =====================
for p in range(args.startParam, args.startParam + numToScan):
    rawAddr = (p - 1) * regCount
    modiconAddr = modiconBase + rawAddr

    try:
        result = readFunc(rawAddr, count=regCount, device_id=args.unitID)

        if result.isError():
            print(f"Raw:{rawAddr:8d} | Modicon:{modiconAddr:12d} | READ ERROR")
            continue
        v = decodeValue(result.registers)
        if is32bit and args.dataType == "FLOAT32":
            print(f"Raw:{rawAddr:8d} | Modicon:{modiconAddr:12d} | v={v:8.2f}")
        else:
            print(f"Raw:{rawAddr:8d} | Modicon:{modiconAddr:12d} | v={v}")
    except ModbusIOException:
        print(f"Raw:{rawAddr:8d} | Modicon:{modiconAddr:12d} | NO RESPONSE")
    except Exception as e:
        print(f"Raw:{rawAddr:8d} | Modicon:{modiconAddr:12d} | ERROR: {e}")
print("\nScan complete.")
client.close()