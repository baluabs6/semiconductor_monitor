<!-- SAMPLE runbook: replace with your fab's approved procedure -->
# ATE die test failures

## Reading the failures
Look at which test and which bin fails. One failing test across many dies suggests a tester, probe card
or process cause. Failures spread over many different tests suggest a contact or setup problem.

## Probe card and contact
Rising contact resistance, contamination or worn probe tips cause intermittent parametric failures.
Clean or replace the probe card and re-test a sample of failed dies before scrapping them.

## Leakage_Current failures
Leakage_Current failures that follow a temperature excursion are usually thermal. See the cooling
failure runbook. Isolated leakage failures with normal temperature suggest a process defect; check
recent lot history.
