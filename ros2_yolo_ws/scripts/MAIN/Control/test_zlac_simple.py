#!/usr/bin/env python3
import minimalmodbus, time
from contextlib import suppress

PORT = "/dev/ttyUSB1"  # 👈 แก้ให้ตรงกับที่เจอ
SLAVE_ID = 1

def make_inst(baud):
    inst = minimalmodbus.Instrument(PORT, SLAVE_ID)
    inst.serial.baudrate = baud
    inst.serial.bytesize = 8
    inst.serial.parity   = minimalmodbus.serial.PARITY_NONE
    inst.serial.stopbits = 1
    inst.serial.timeout  = 0.3
    inst.mode = minimalmodbus.MODE_RTU
    inst.close_port_after_each_call = True
    return inst

bauds = [115200, 57600, 38400, 19200, 9600]

for b in bauds:
    print(f"\n=== Try baud {b} ===")
    try:
        inst = make_inst(b)
        # ลองอ่านอะไรเบา ๆ ก่อน เช่น register config
        with suppress(Exception):
            val = inst.read_register(0x200D, 0, functioncode=3)
            print(f"Read 0x200D OK, value={val}")
        # ลองสั่ง enable velocity
        inst.write_register(0x200D, 3, 0, functioncode=6)
        time.sleep(0.05)
        with suppress(Exception):
            inst.write_register(0x200E, 7, 0, functioncode=6)
        time.sleep(0.05)
        inst.write_register(0x200E, 8, 0, functioncode=6)
        print(f"✅ SUCCESS at baud {b}")
    except Exception as e:
        print(f"❌ ERROR at baud {b}: {e}")
