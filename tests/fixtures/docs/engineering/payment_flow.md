# Payment Processing System (Fixture)

## Overview

Internal note: **PaymentIntent**-based flow for tests. Describes create → confirm → webhook path.

---

## Key Components

- **PaymentIntent** service: state, retries, metadata
- **API Gateway**: auth, rate limits
- **Webhook handler**: `payment_succeeded`, `payment_failed`, `charge_refunded`

---

## Flow

### Create

`POST /v1/payment_intents` with amount, currency, payment_method, customer_id.

### Confirm

`POST /v1/payment_intents/{id}/confirm` → `succeeded`, `requires_payment_method`, or `processing`.

### Webhooks

Verify signature, idempotency, then update internal state.

---

## Retries

Max **3** attempts, exponential backoff **1m → 5m → 15m**. Do not retry hard declines (e.g. fraudulent).

---

## Idempotency

Always send **Idempotency-Key** to prevent duplicate charges on timeouts.

---

Last updated: fixture
