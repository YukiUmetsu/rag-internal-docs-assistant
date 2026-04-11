# Incident Runbook: Elevated Payment Failure Rate (Fixture)

## Overview

Condensed runbook for tests when payment **failure rates** spike.

---

## Severity (summary)

- **SEV1**: system down or failure rate **> 20%** — page on-call immediately
- **SEV2**: **5–20%** failures or regional impact — respond within **15 minutes**
- **SEV3** / **SEV4**: limited impact — investigate in business hours

---

## First steps

- confirm alert and time window
- check `payment_intent` error codes and processor status
- compare to baseline success rate

---

## Mitigation ideas

- scale or fail over API tier if internal
- communicate with processor if external outage
- enable safe retries only for transient errors

---

Last updated: fixture
