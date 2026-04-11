# Failed Payment Playbook (Fixture)

## Overview

Short support/engineering playbook for **failed payment** scenarios in tests.

---

## When to use

- customer reports failure
- PaymentIntent `requires_payment_method`
- failure spike or alert

---

## Step 1: Gather

- `payment_intent_id`, `error_code`, `decline_code`, `retry_count`

---

## Step 2: By category

**Card declines** (`insufficient_funds`, `expired_card`, `do_not_honor`): no blind retries; customer updates card.

**System errors** (`500`, `502`, `503`): retry with backoff where appropriate.

**Rate limits** (`429`): backoff and retry.

---

Last updated: fixture
