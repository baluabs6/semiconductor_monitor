<!-- SAMPLE runbook: replace with your fab's approved procedure -->
# Tool controller health

## High CPU or memory usage
Sustained high CPU or memory on the tool controller can delay data collection and trigger firmware
timeouts. Identify the busiest process, check for a runaway job, and restart the offending service in a
maintenance window.

## Low disk space
Log volumes filling up can stop data logging. Archive or rotate old logs, and check for a service writing
excessive debug output.
