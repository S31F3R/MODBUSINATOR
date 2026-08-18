# plan.md — MODBUSINATOR / DUMPER upgrade + correctness

## Goal
Get both tools onto a single, current pymodbus (3.9.x) with clean, consistent API usage, and fix the correctness bugs found in review.

---

## 0. Pin a target version first
- CONFIRMED: currently running **pymodbus 3.12.1**. Target this — do not downgrade.
- Pin it: add `pymodbus==3.12.1` to `requirements.txt`.
- The "newer versions broke my code" issue was almost certainly the DUMPER
  *client* calls (`slave=`, positional `count`), NOT the server. MODBUSINATOR
  already uses the modern `ModbusDeviceContext`/`devices=` API and is fine on 3.12.
  Fix is to bring DUMPER forward to match, not to hold anything back.

---

## 1. API changes to expect across pymodbus 3.x → 3.12
These are the renames/signature changes most likely to have broken you:

| Area | Old | New (3.12) |
|------|-----|-----------|
| Slave/device context | `ModbusSlaveContext` | `ModbusDeviceContext` |
| Server context kwarg | `ModbusServerContext(slaves={...})` | `ModbusServerContext(devices={...})` |
| Client read unit arg | `slave=` | `device_id=` |
| Framer import | `from pymodbus.transaction import ModbusRtuFramer` | `from pymodbus import FramerType` |
| `count` on reads | positional allowed | keyword-only (`count=`) |

MODBUSINATOR already uses the new context names, so it needs no version work.
DUMPER is the one that needs the client-side updates.

NOTE: verify the exact `device_id=` keyword against your installed 3.12.1
(`python -c "help(ModbusTcpClient.read_holding_registers)"`) before committing —
the arg name settled during 3.7/3.8 but confirm it on your build rather than trust this table.

---

## 2. DUMPER fixes (client / scanner)
1. **Pass the framer on the TCP path** (currently ignored):
   ```python
   client = ModbusTcpClient(args.host, port=args.port,
                            framer=getattr(FramerType, args.framer))
   ```
   Needed for RTU-over-TCP against a raw serial tunnel (e.g. NPort in TCP Server mode).
2. **Actually send the unit/device ID** (currently parsed, printed, never used):
   ```python
   result = readFunc(rawAddr, count=regCount, device_id=args.unitID)
   ```
   Use `device_id=` on 3.9. (`slave=` on older 3.x — pick based on pinned version.)
3. After pinning the version, re-check every read call still uses `count=` as a keyword.

---

## 3. MODBUSINATOR fixes (server / publisher)
1. **Make stop() actually stop the servers (priority bug).**
   - `stopSerial()` / `stop()` currently just drop references while the blocking
     `Start*Server` threads keep running and holding the port.
   - Switch to holding the server instance and shutting it down, e.g. keep a
     reference to the `ModbusTcpServer` / `ModbusSerialServer` and call
     `.shutdown()`, or move to the async API with `ServerAsyncStop`.
   - Verify: after `stop()`, the TCP port and COM port can be re-bound.
2. **Simplify the framer conversion.**
   - Replace `framerStr = str(self.framerType).lower().split('.')[-1]`
     with passing `framer=self.framerType` directly to `StartSerialServer`
     (or `self.framerType.value` if a string is required). Remove the string munging.
3. **Honor `registersPerParam` in `writeFloat`** (or remove the option).
   - Today it always writes 2 registers regardless of the configured value.
4. **Log the active register bank clearly** so a client pointed at the wrong
   HR/IR type produces an obvious message, not a mystery error.
5. **(Optional) Guard multi-register writes** if fast polling of live floats
   matters — avoid a client reading one old + one new register mid-update.

---

## 4. Cross-tool consistency checks
- Confirm both tools agree on **register type** (HR vs IR).
- Confirm both agree on **unit/device ID** (default 1 on both — keep aligned).
- Confirm **addressing/zero_mode** matches on both ends. Current setup is
  symmetric (param 0 → wire address 0); don't set `zero_mode` on only one side.
- Confirm **float word order** end to end (server packs `>f` as ABCD; DUMPER's
  `--byteOrder` must match, e.g. CDAB for word-swapped devices).

---

## 5. Verification steps
1. Run MODBUSINATOR (TCP), push a known value via `update("[25.34]")`.
2. Scan with DUMPER (`--connection TCP --dataType FLOAT32`) → expect 25.34.
3. Flip `--byteOrder` to confirm decode path; confirm ABCD is correct for your server.
4. Test `stop()` → re-run server on same port to prove the port was released.
5. Test non-default `--unitID` end to end to prove the device-ID fix works.
6. If using the NPort: MODBUSINATOR is not part of that path — the NPort
   scenario is DUMPER reading an *external* slave. Keep the two use cases separate.