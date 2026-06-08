
from pymodbus.client import ModbusSerialClient
import struct

client = ModbusSerialClient(
    port="COM1",
    baudrate=9600,
    parity="E",
    stopbits=1,
    bytesize=8,
    timeout=2
)

if not client.connect():
    print("❌ Could not open COM1")
    exit()

print("✅ Connected to COM1 (loopback test)")

# Read Param 1 (raw address 0)
result = client.read_holding_registers(0, count=2)
if result.isError():
    print("❌ Read error on Param 1:", result)
else:
    v = struct.unpack('>f', result.registers[0].to_bytes(2,'big') + result.registers[1].to_bytes(2,'big'))[0]
    print(f"Param 1 (address 0) = {v:.2f}")

# Read Param 100 (raw address 198)
result = client.read_holding_registers(198, count=2)
if result.isError():
    print("❌ Read error on Param 100:", result)
else:
    v = struct.unpack('>f', result.registers[0].to_bytes(2,'big') + result.registers[1].to_bytes(2,'big'))[0]
    print(f"Param 100 (address 198) = {v:.2f}")

client.close()