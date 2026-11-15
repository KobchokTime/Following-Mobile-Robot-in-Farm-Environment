import pygame, time

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("❌ No joystick found")
    exit()

js = pygame.joystick.Joystick(0)
js.init()
print(f"✅ Joystick detected: {js.get_name()}")

try:
    while True:
        pygame.event.pump()
        axes = [js.get_axis(i) for i in range(js.get_numaxes())]
        buttons = [js.get_button(i) for i in range(js.get_numbuttons())]
        print("axes:", ["% .2f" % a for a in axes], "buttons:", buttons)
        time.sleep(0.2)
except KeyboardInterrupt:
    pass
finally:
    pygame.quit()

