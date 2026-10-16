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
encoder accuracy, braking distance, the physical E-stop under motion, or
operation with wheels on the ground.
