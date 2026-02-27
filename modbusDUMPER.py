# ==============================================
#  modbusDUMPER v1.0
#  Scans and dumps ALL holding registers from any Modbus server
#  Stops automatically when the device returns an error
# ==============================================

import argparse
import struct
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus import FramerType

def regsToFloat(msw: int, lsw: int) -> float | None:
    """Decode two registers (MSW-first, big-endian) → IEEE 754 float"""
    try:
        return struct.unpack('>f', struct.pack('>HH', msw, lsw))[0]
    except:
        return None

def main():
    parser = argparse.ArgumentParser(description="modbusDUMPER - dump all available holding registers")
    parser.add_argument("--mode", choices=["tcp", "serial"], default="tcp", help="tcp or serial (default: tcp)")
    parser.add_argument("--host", default="localhost", help="TCP host (default: localhost)")
    parser.add_argument("--port", type=int, default=502, help="TCP port (default: 502)")
    parser.add_argument("--com", default=None, help="Serial COM port e.g. COM3 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=19200, help="Serial baudrate (default: 19200)")
    parser.add_argument("--maxAddr", type=int, default=1024, help="Maximum address to scan")
    parser.add_argument("--chunk", type=int, default=100, help="Registers per read request (max \~125 on most devices)")
    parser.add_argument("--decodeFloats", action="store_true", help="Also decode every 2 registers as float")
    parser.add_argument("--unit", type=int, default=1, help="Modbus unit/slave ID (default 1)")
    args = parser.parse_args()

    if args.mode == "serial" and not args.com:
        print("ERROR: --com is required when using --mode serial")
        return

    # === Create client ===
    if args.mode == "tcp":
        client = ModbusTcpClient(args.host, port=args.port, timeout=3)
        print(f"Connecting TCP → {args.host}:{args.port} (unit {args.unit})")
    else:
        client = ModbusSerialClient(
            port=args.com,
            baudrate=args.baud,
            bytesize=8,
            parity="E",
            stopbits=1,
            timeout=3,
            framer=FramerType.RTU
        )
        print(f"Connecting Serial → {args.com} @ {args.baud} 8E1 (unit {args.unit})")
    if not client.connect():
        print("Failed to connect to the Modbus server!")
        return
    print("Connected. Scanning holding registers from 0...\n")

    registers = {}
    addr = 0
    lastGood = -1

    while addr <= args.maxAddr:
        count = min(args.chunk, args.maxAddr - addr + 1)

        try:
            result = client.read_holding_registers(address=addr, count=count, device_id=args.unit)

            if result.isError():
                print(f"Server returned error at address {addr} → stopping scan.")
                break
            for i, value in enumerate(result.registers):
                regAddr = addr + i
                registers[regAddr] = value
                print(f"HR {regAddr:05d} :  {value:6d}  (0x{value:04X})")
            lastGood = addr + count - 1
        except Exception as e:
            print(f"Exception at address {addr}: {e}")
            break
        addr += count
    client.close()
    print(f"\n=== Scan finished ===")
    dumpedMsg = f"Dumped {len(registers)} holding registers"

    if lastGood >= 0:
        dumpedMsg += f" (0–{lastGood})"
    print(dumpedMsg)

    if args.decodeFloats and lastGood >= 1:
        print("\n=== Decoded Floats ===")

        for i in range(0, lastGood, 2):
            msw = registers.get(i)
            lsw = registers.get(i + 1)

            if msw is not None and lsw is not None:
                fval = regsToFloat(msw, lsw)
                if fval is not None:
                    print(f"Float {i:05d}-{i+1:05d} :  {fval:.6f}   (HR{i} + HR{i+1})")

if __name__ == "__main__":
    main()