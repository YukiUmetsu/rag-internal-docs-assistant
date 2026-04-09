# Failed Payment Playbook

## Overview

This document provides a standardized procedure for handling failed payment
events. It is intended for both support agents and engineers.

The goal is to:

- identify the root cause of failure
- resolve customer issues efficiently
- prevent repeated failures
- escalate when necessary

## When to Use This Playbook

Use this playbook when:

- a customer reports a failed payment
- a payment intent has status `requires_payment_method`
- there is a spike in payment failures
- alerts indicate elevated error rates

## Step 1: Identify the Failure Type

Retrieve the following:

- `payment_intent_id`
- `error_code`
- `decline_code` if available
- `retry_count`

### Common Failure Categories

#### 1. Card Declines

Examples:

- `insufficient_funds`
- `expired_card`
- `do_not_honor`

#### 2. System Errors

Examples:

- `500` internal error
- `502` upstream failure
- `processing_error`

#### 3. Rate Limiting

Example:

- `429` too many requests

## Step 2: Take Action Based on Error Type

### Card Declines

| Decline Code         | Meaning            | Action                           |
| -------------------- | ------------------ | -------------------------------- |
| `insufficient_funds` | Not enough balance | Ask for another card             |
| `expired_card`       | Card expired       | Ask user to update card          |
| `do_not_honor`       | Issuer declined    | Suggest a different payment method |
| `incorrect_cvc`      | Wrong security code | Ask user to retry               |

Rules:

- do not retry automatically
- require customer action before a new attempt

### System Errors

| Error Code | Meaning        | Action      |
| ---------- | -------------- | ----------- |
| `500`      | Internal error | Retry       |
| `502`      | Gateway error  | Retry       |
| `503`      | Service down   | Retry later |

Rules:

- safe to retry up to 3 times
- use exponential backoff

### Rate Limiting

| Error Code | Meaning           | Action            |
| ---------- | ----------------- | ----------------- |
| `429`      | Too many requests | Retry after delay |

Rules:

- wait at least 60 seconds before retry
- avoid burst retries

## Step 3: Check Retry History

Retrieve retry logs from `billing-service`.

### Retry Rules

- `max_attempts = 3`
- backoff schedule:
  - attempt 1 to 1 minute
  - attempt 2 to 5 minutes
  - attempt 3 to 15 minutes

If `retry_count >= 3`:

- stop retrying
- escalate to support or engineering

## Step 4: Verify External Dependencies

Check the payment provider status page.

Investigate:

- regional outages
- degraded performance
- latency spikes

If the provider is degraded:

- inform the customer
- delay retries
- monitor recovery

## Step 5: Inspect Logs

Search logs using:

- `payment_intent_id`
- `customer_id`

Look for:

- repeated failures
- timeout errors
- webhook delays
- duplicate events

## Step 6: Validate Webhook Processing

Ensure:

- the webhook was received
- signature verification passed
- the event processed successfully

Common issues:

- delayed webhook delivery
- duplicate events
- processing failures

## Step 7: Resolution Paths

### Case 1: Customer Action Required

Examples:

- insufficient funds
- expired card

Action:

- notify the customer
- request an updated payment method

### Case 2: System Retry

Examples:

- transient network errors
- processor timeouts

Action:

- allow the retry system to proceed
- monitor the retry outcome

### Case 3: Escalation Required

Escalate if:

- the error code is unknown
- retry attempts are exhausted
- repeated failures occur across users
- a system bug is suspected

Escalation path:

- Level 1 to Support Lead
- Level 2 to Engineering On-Call

## Step 8: Communication Guidelines

When responding to customers:

- avoid technical jargon
- provide clear next steps
- set expectations on timing

Example:

> Your payment failed due to insufficient funds. Please try another payment
> method or contact your bank.

## Step 9: Metrics and Monitoring

Track:

- failure rate
- retry success rate
- decline distribution by type

Alert thresholds:

- failure rate greater than 5 percent
- retry success rate below 50 percent

## Known Issues

### Duplicate Failures

Cause:

- repeated retries without a state update

Fix:

- verify idempotency handling

### Webhook Delays

Cause:

- queue backlog

Impact:

- delayed order confirmation

## Notes

- always rely on webhook events as the source of truth
- do not assume client-side success
- ensure all actions are logged
