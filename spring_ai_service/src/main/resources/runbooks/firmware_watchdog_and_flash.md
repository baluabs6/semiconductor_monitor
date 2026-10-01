<!-- SAMPLE runbook: replace with your fab's approved procedure -->
# Firmware watchdog resets and flash errors

## WDT_RESET
A watchdog timeout means the main loop stopped responding. Causes include overheating, a brownout, a
blocked task, or a bug. If a reset appears together with FAB temperature or voltage alerts, treat the
environmental alert as the primary cause and fix it first.

## NULL_PTR_DEREF and PANIC
These indicate a firmware defect or memory corruption. Capture the log and build version, then open a
firmware ticket. Repeated panics in the same task point to a software bug and not to hardware.

## Flash write failures
Flash write errors during a supply dip are usually a power problem. Errors with a healthy supply
suggest worn or faulty flash; check the write-cycle counter.
