# Refund Policy and Processing Guide

## Overview

This document defines the refund handling rules used in the Acme Payments
system. It outlines eligibility criteria, approval rules, and processing steps
for issuing refunds.

---

## Refund Eligibility

A refund can be issued if all of the following conditions are met:

- the transaction exists and is valid
- the payment was successfully captured
- the request falls within the allowed refund window

### Refund Window

- refunds are allowed within 14 days of the original transaction date

Requests outside this window should be rejected unless explicitly approved.

---

## Refund Types

### Full Refund

A full refund returns the entire transaction amount.

Used when:

- the order is canceled
- duplicate charges occur

---

### Partial Refund

A partial refund returns a portion of the original payment.

Used when:

- only part of the order is returned
- partial service issues occur

---

## Approval Rules

Refund approval requirements:

- refunds under 500 USD do not require approval
- refunds of 500 USD or more require support lead approval

---

## Refund Processing Flow

### Step 1: Validate Transaction

Verify:

- `transaction_id` exists
- payment status is `succeeded`

---

### Step 2: Confirm Eligibility

Check:

- request is within 14-day window
- no prior refund has been issued

---

### Step 3: Issue Refund

Refund is created via API:

POST /v1/refunds

Required fields:

- `payment_intent_id`
- `amount` (optional for full refund)

---

### Step 4: Update Records

- mark transaction as refunded
- log refund in billing system

Customer notification may not be immediate.

---

## Processing Time

Expected timelines:

- card payments: 7 to 14 business days
- bank transfers: up to 10 business days

Processing times may vary depending on provider delays.

---

## Failure Handling

Refund failures may occur due to:

- invalid payment details
- processor errors

If a refund fails:

- log the failure
- retry only if the error is transient

---

## Idempotency

All refund requests must include an idempotency key.

Purpose:

- prevent duplicate refunds
- ensure safe retries during network failures

If duplicate requests are received:

- return the original response
- do not issue multiple refunds

---

## Risk Considerations

Refund requests should be reviewed for:

- unusually high refund frequency
- high-value transactions

---

## Known Limitations

### Duplicate Refund Attempts

Cause:

- repeated requests due to retries or UI issues

Handling:

- rely on idempotency keys to prevent duplication

---

### Limited Fraud Controls

Some refund scenarios may not include full risk evaluation.

---

## Notes

- always verify transaction details before issuing refunds
- follow approval rules for high-value refunds

---

Last updated: 2025-03-10
