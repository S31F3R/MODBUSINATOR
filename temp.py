def readAndPrintRegisters(client, numParams, registersPerParam, currentMinute):
    print(f"\n=== MODBUSINATOR REGISTERS AFTER MINUTE {currentMinute} ===")
    totalToRead = registersPerParam * numParams
    allRegisters = []
    maxPerRead = 124   # safe limit

    for start in range(0, totalToRead, maxPerRead):
        count = min(maxPerRead, totalToRead - start)
        result = client.read_holding_registers(start, count=count)   # ← FIXED: use 'start' not '0'

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