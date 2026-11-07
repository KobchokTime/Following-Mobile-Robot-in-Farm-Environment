# Motor wheel calibration

## Evidence — 2026-09-20

Raised-wheel 5 RPM / 0.5 s bench pulse showed that a positive write to the
controller's `LEFT_TARGET` register (`0x2088`) moved the **physical right wheel
backwards**.

The next left-wheel pulse therefore uses the observed correction:

| Logical wheel | Controller target register | RPM sign | Status |
| --- | --- | --- | --- |
| left | `0x2089` (right channel) | negative | bench-verified by operator after correction |
| right | `0x2088` (left channel) | positive | bench-verified by operator |

This is a bench calibration, not a final chassis configuration. Retain the
output from the corrected left test, then test the remaining channel at the
same raised-wheel 5 RPM / 0.5 s limit before enabling any two-wheel command.

## Corrected left-wheel result

The operator reported that the corrected raised-wheel pulse produced the
expected physical wheel and direction. This validates only the logical-left
bench mapping at 5 RPM for 0.5 s. The operator subsequently reported that the
logical-right wheel was also correct. It does not validate two-wheel motion,
encoder accuracy, braking distance, or operation with wheels on the ground.

## Reconciliation with the drive code — 2026-10-21 (T6)

Desk review only; nothing here was measured on the robot.

Two pieces of drive code agree on the forward mapping:

| Source | Forward command |
| --- | --- |
| `MAIN/Control/zlac_joystick_bridge.py` (straight part, unchanged since the recovered backup) | `0x2088` negative, `0x2089` positive |
| `control/Joystick.py`, stick forward (`axis1 = -1`) | `0x2088` negative, `0x2089` positive |

The 2026-09-20 evidence line also agrees: a positive write to `0x2088` moved the physical right
wheel backwards, so a negative write moves it forwards.

The table above lists `0x2089` as **negative** for the logical left wheel. That matches the forward
mapping only if the bench pulse was meant to turn the wheel backwards. The record does not say which
direction was "expected", so the table's signs are pulse signs, not forward signs.

With that forward mapping, a positive `angular.z` (counter-clockwise, REP-103) writes a negative
value to both registers. This is the bridge's default `turn_dir = +1`. Note that `Joystick.py` sends
the same sign to both registers from the **left/right** stick axis, and positive for stick-left. Its
axis comments are swapped (`axis1` drives the opposite-sign part), so it does not show which way the
robot spins.

**To settle on robot day:**

1. Lift the wheels.
2. Send `linear.x = 0.2` and confirm both wheels roll forwards.
3. Send `angular.z = 0.3` and confirm the robot would turn left: the right wheel forwards, the left
   wheel backwards.
4. If step 3 turns right, set `turn_dir:=-1` and record the result here.
