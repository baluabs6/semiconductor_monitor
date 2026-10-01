<!-- SAMPLE runbook: replace with your fab's approved procedure -->
# Power brownout

## Symptoms
Supply voltage below range, followed by Vdd_Parametric ATE failures and firmware flash write errors.
Several dies failing the same voltage-related test in quick succession suggests a supply problem.

## Likely causes
Failing power supply or regulator, loose connector, overloaded circuit, or an upstream facility
power dip. Check other tools on the same feeder: if they also dipped, the cause is upstream.

## Immediate checks
Measure the supply rails at the source and at the load. Inspect connectors and cabling. Check the UPS
and facility power logs for the time of the dip. Re-run a known-good golden die before releasing the
tool.
