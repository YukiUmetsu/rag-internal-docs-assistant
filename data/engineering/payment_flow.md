# Payment Processing System (Internal)

## Overview

Acme Payments uses a PaymentIntent-based architecture to handle all payment transactions. This allows us to support synchronous and asynchronous payment methods, manage retries, and ensure consistent state transitions across services.

This document describes the end-to-end payment lifecycle, including system components, state transitions, and failure handling.

---

## Key Components

### 1. PaymentIntent Service

Responsible for:

- Creating and tracking payment state
- Managing retries and confirmations
- Storing metadata (customer_id, order_id)

### 2. API Gateway

Handles:

- Authentication
- Rate limiting
- Request validation

### 3. Payment Processor (External)

Third-party provider responsible for:

- Card authorization
- Fund capture
- Fraud checks

### 4. Webhook Handler

Processes asynchronous events:

- payment_succeeded
- payment_failed
- charge_refunded

### 5. Billing Service

Internal system responsible for:

- Logging transactions
- Triggering retries
- Updating order status

---

## Payment Flow

### Step 1: Create PaymentIntent

Client sends request:

POST /v1/payment_intents

Required fields:

- amount
- currency
- payment_method
- customer_id

Response:

- payment_intent_id
- status = "requires_confirmation"

---

### Step 2: Confirm Payment

Client confirms payment:

POST /v1/payment_intents/{id}/confirm

Possible outcomes:

- success → status = "succeeded"
- failure → status = "requires_payment_method"
- async → status = "processing"

---

### Step 3: External Processing

The payment processor performs:

- card authorization
- fraud detection
- fund capture (if auto-capture enabled)

Latency:

- synchronous: < 2 seconds
- asynchronous: up to several minutes

---

### Step 4: Webhook Events

Webhook events are the source of truth.

Key events:

- payment_intent.succeeded
- payment_intent.payment_failed
- charge.refunded

Webhook handler must:

- verify signature
- ensure idempotency
- update internal state

---

### Step 5: Order Finalization

Once payment is successful:

- Billing service updates order status → "paid"
- Confirmation email is triggered
- Inventory is reserved

---

## State Machine

PaymentIntent states:

- requires_payment_method
- requires_confirmation
- processing
- succeeded
- canceled

Transitions must be:

- idempotent
- logged
- traceable

---

## Retry Strategy

Retries are handled by Billing Service.

Rules:

- max_attempts = 3
- backoff: exponential (1m → 5m → 15m)

Do NOT retry:

- stolen_card
- lost_card
- fraudulent

Retry triggers:

- network errors
- rate limits (429)
- temporary processor failures

---

## Error Handling

Common error codes:

| Code | Meaning | Action |
|------|--------|--------|
| 402  | Insufficient funds | Ask customer to use another card |
| 429  | Rate limited | Retry with backoff |
| 500  | Internal error | Retry and alert |

---

## Idempotency

Without idempotency

User clicks “Pay” → request sent
Network times out → user clicks again

Two requests hit your system:

Charge $100

Charge $100

Result: customer charged twice

With idempotency

Client sends:
Idempotency-Key: abc123

System logic:

first request → processed → stored with key
second request → same key → return previous result

-> Result: only one charge happens

All payment requests must include:
Idempotency-Key header

Purpose:

- prevent duplicate charges
- ensure safe retries

---

## Observability

Logs must include:

- payment_intent_id
- customer_id
- error_code
- retry_count

Metrics to monitor:

- success rate
- failure rate
- retry success rate

Alerts:

- failure rate > 5%
- retry exhaustion spike

---

## Known Failure Modes

1. Webhook delays
   - cause: queue backlog
   - impact: delayed order confirmation

2. Duplicate webhook events
   - must handle idempotently

3. Partial failures
   - payment succeeds but order not updated

---

## Notes for Engineers

- Never trust client-side success — always rely on webhooks
- Avoid synchronous assumptions
- Always log before retrying
