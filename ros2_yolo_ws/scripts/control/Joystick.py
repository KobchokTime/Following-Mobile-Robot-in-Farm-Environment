import pygame, time
from contextlib import suppress
import minimalmodbus, serial

# ================= CONFIG =================
PORT = "/dev/ttyUSB0"
BAUD = 115200
SLAVE_ID = 1
MAX_RPM = 24
TURN_GAIN = 70   # ยิ่งมาก เลี้ยวยิ่งแรง

# ============== ZLAC DRIVER ===============
class ZLAC8015D:
    def __init__(self, port, sid, baud):
        self.inst = minimalmodbus.Instrument(port, sid)
        self.inst.serial.baudrate = baud
        self.inst.serial.bytesize = 8
        self.inst.serial.parity   = minimalmodbus.serial.PARITY_NONE
        self.inst.serial.stopbits = 1
        self.inst.serial.timeout  = 0.5
        self.inst.mode = minimalmodbus.MODE_RTU
        self.inst.close_port_after_each_call = True

    def enable_velocity(self):
        self.inst.write_register(0x200D, 3, 0, functioncode=6)
        time.sleep(0.05)
        with suppress(Exception): self.inst.write_register(0x200E, 7, 0, functioncode=6)
        time.sleep(0.05)
        self.inst.write_register(0x200E, 8, 0, functioncode=6)
        print("[Drive] Velocity mode enabled")

    def set_velocity(self, left, right):
        self.inst.write_register(0x2088, int(left), 0, functioncode=6, signed=True)
        self.inst.write_register(0x2089, int(right), 0, functioncode=6, signed=True)

    def stop(self):
        with suppress(Exception):
            self.inst.write_register(0x200E, 7, 0, functioncode=6)
        print("[Drive] Stopped")

# ============== MAIN LOOP =================
def main():
    zlac = ZLAC8015D(PORT, SLAVE_ID, BAUD)
    zlac.enable_velocity()

    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("❌ No joystick detected")
        return

    js = pygame.joystick.Joystick(0)
    js.init()
    print(f"✅ Joystick detected: {js.get_name()}")

    try:
        while True:
            pygame.event.pump()

            axis0 = js.get_axis(0)  # left/right
            axis1 = js.get_axis(1)  # forward/back

            base = -axis0 * MAX_RPM
            turn = axis1 * TURN_GAIN
            left = base + turn
            right = base - turn

            zlac.set_velocity(left, right)
            print(f"L={left:.1f} R={right:.1f}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        zlac.stop()
        pygame.quit()

if __name__ == "__main__":
    main()

