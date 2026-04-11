# Refund Policy and Processing Guide (Fixture)

## Overview

Condensed refund rules for **2025** used in automated tests. Full policy lives in production data.

---

## Refund Eligibility

- transaction exists and is valid
- payment was successfully captured
- request falls within the refund window

### Refund Window

- refunds within **14 days** of the original transaction date

---

## Approval Rules

- refunds under **500 USD** do not require approval
- 500 USD or more require support lead approval

---

## Processing

POST /v1/refunds with `payment_intent_id` and optional `amount`.

Idempotency keys are required.

---

Last updated: 2025-03-10 (fixture)
