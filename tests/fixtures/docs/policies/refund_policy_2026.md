# Refund Policy and Processing Guide (Fixture)

## Overview

Condensed refund rules for **2026** used in automated tests.

---

## Refund Eligibility

- transaction exists and is valid
- payment was successfully captured
- request falls within the refund window
- transaction is not flagged for fraud

### Refund Window

- refunds within **30 days** of the original transaction date

---

## Approval Rules

- under **100 USD**: no approval
- **100–1000 USD**: manager approval
- over **1000 USD**: finance review

---

## Processing

POST /v1/refunds with `payment_intent_id` and optional `amount`.

Idempotency keys are required.

---

Last updated: 2026-01-15 (fixture)
