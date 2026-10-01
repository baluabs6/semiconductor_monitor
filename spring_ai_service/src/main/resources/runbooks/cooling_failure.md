<!-- SAMPLE runbook: replace with your fab's approved procedure -->
# Cooling failure

## Symptoms
Chamber temperature rises above its normal range, usually followed by pressure drift. A firmware
watchdog reset (WDT_RESET) and a burst of ATE Leakage_Current failures shortly afterwards point to the
same thermal cause rather than four separate faults.

## Likely causes
Loss of coolant flow, a failing chiller or pump, a fouled heat exchanger, a blocked filter, or a
temperature sensor fault. A sensor fault is likely if temperature jumps while pressure and
other channels stay normal.

## Immediate checks
Confirm chiller and pump status, coolant flow and inlet temperature. Compare redundant temperature
sensors. Check whether the excursion started with a recipe step change. Hold new lots on the tool until
temperature is back in range.

## Escalation
Page the equipment engineer if the temperature is critical for more than a few minutes or if
Leakage_Current failures continue after recovery. Quarantine lots processed during the excursion.
