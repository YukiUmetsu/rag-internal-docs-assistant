# Refund Policy and Processing Guide

## Overview

This document defines the current refund handling rules used in the Acme
Payments system. It outlines eligibility criteria, approval requirements, and
processing steps for issuing refunds.

These guidelines are used by support agents, finance teams, and backend
services.

---

## Refund Eligibility

A refund can be issued if all of the following conditions are met:

- the transaction exists and is valid
- the payment was successfully captured
- the request falls within the allowed refund window
- the transaction is not flagged for fraud or investigation

### Refund Window

- refunds are allowed within 30 days of the original transaction date

Requests outside this window require explicit approval.

---

## Refund Types

### Full Refund

A full refund returns the entire transaction amount.

Used when:

- the order is canceled
- the product was not delivered
- duplicate charges occurred

---

### Partial Refund

A partial refund returns a portion of the original payment.

Used when:

- only part of the order is returned
- service degradation occurred
- pricing adjustments are required

---

## Approval Rules

Refund approval requirements:

- refunds under 100 USD do not require approval
- refunds between 100 and 1000 USD require manager approval
- refunds over 1000 USD require finance team review

Approval must be recorded in the system before processing.

---

## Refund Processing Flow

### Step 1: Validate Transaction

Verify:

- `transaction_id` exists
- payment status is `succeeded`
- refund has not already been issued or exceeded limits

---

### Step 2: Confirm Eligibility

Check:

- request is within the 30-day window
- transaction is eligible for refund
- no active fraud or risk flags are present

---

### Step 3: Determine Refund Amount

- full refund if entire order is canceled
- partial refund based on returned items or service impact

Ensure total refunded amount does not exceed original payment.

---

### Step 4: Issue Refund

Refund is created via API:

POST /v1/refunds

Required fields:

- `payment_intent_id`
- `amount` (optional for full refund)

---

### Step 5: Update Records

- update transaction status to `refunded` or `partially_refunded`
- log refund event in billing system
- trigger customer notification

---

## Processing Time

Expected timelines:

- card payments: 5 to 10 business days
- bank transfers: 3 to 7 business days
- digital wallets: up to 2 business days

Delays may occur due to:

- banking systems
- weekends and holidays
- additional fraud checks

---

## Failure Handling

Refunds may fail due to:

- invalid or closed payment accounts
- processor errors
- network failures

If a refund fails:

- log the failure
- notify support team
- retry only for transient errors

Do not retry:

- invalid account details
- permanently failed payment methods

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

## Fraud and Risk Controls

Refund requests must be evaluated for:

- high refund frequency
- high-value transactions
- mismatched customer data

Do not issue refunds if:

- the transaction is under investigation
- the account is flagged for abuse

Escalate suspicious cases to the risk team.

---

## Observability

Track the following metrics:

- refund rate
- refund failure rate
- average processing time

Alert conditions:

- refund rate exceeds baseline thresholds
- refund failures increase significantly

---

## Known Edge Cases

### Duplicate Refund Requests

Cause:

- repeated submissions due to network retries or UI issues

Handling:

- rely on idempotency keys
- return existing refund result

---

### Partial Refund Conflicts

Cause:

- multiple partial refunds exceeding total amount

Handling:

- enforce total refund limits
- reject excess refund attempts

---

### Delayed Refund Visibility

Cause:

- bank processing delays

Handling:

- inform customer of expected timelines
- avoid duplicate refund attempts

---

## Notes

- refunds are irreversible once processed
- always verify transaction details before issuing refunds
- follow approval rules for high-value transactions

---

Last updated: 2026-01-15
