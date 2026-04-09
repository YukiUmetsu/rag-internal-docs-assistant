# Incident Runbook: Elevated Payment Failure Rate

## Overview

This runbook describes how to investigate and mitigate incidents where payment
failure rates exceed normal thresholds.

This issue directly impacts:

- revenue
- checkout success rate
- customer experience

---

## Severity Classification

Incidents must be classified based on **impact and urgency**.

### SEV1 (Critical)

Definition:

- payment system is down or severely degraded
- failure rate greater than 20 percent
- widespread customer impact

Examples:

- all payments failing
- payment API unavailable

Response:

- immediate response required
- page on-call engineer
- escalate to engineering lead

---

### SEV2 (High)

Definition:

- partial degradation of payment system
- failure rate between 5 and 20 percent
- significant user impact

Examples:

- increased failures in one region
- specific payment method failing

Response:

- respond within 15 minutes
- assign on-call engineer

---

### SEV3 (Medium)

Definition:

- minor degradation
- limited customer impact

Examples:

- small increase in failure rate
- isolated retry issues

Response:

- investigate during working hours

---

### SEV4 (Low)

Definition:

- no immediate user impact
- informational or monitoring alerts

Examples:

- minor metric anomalies
- non-critical warnings

Response:

- backlog or monitor

---

## Detection

Incident is triggered when:

- payment failure rate exceeds 5 percent for 5 minutes
- alert fired: `payment_failure_rate_high`

---

## On-Call Responsibilities

### Primary On-Call (Engineering)

Responsible for:

- initial triage
- incident classification
- mitigation actions
- communication updates

---

### Secondary On-Call

Responsible for:

- assisting primary
- investigating deeper issues
- handling overflow tasks

---

### Support Team

Responsible for:

- handling customer tickets
- reporting patterns to engineering
- communicating with affected users

---

### Incident Commander (for SEV1 / SEV2)

Assigned when incident is high severity.

Responsibilities:

- coordinate response
- manage communication
- track progress
- ensure clear ownership

---

## Initial Triage

### Step 1: Confirm the Issue

Check:

- payment failure rate
- request volume
- success rate trends

Determine:

- real incident vs noise
- duration of issue

---

### Step 2: Assign Severity

Use severity classification:

- evaluate failure rate
- evaluate user impact
- determine urgency

---

### Step 3: Assign Owner

- primary on-call takes ownership
- assign incident commander if SEV1 or SEV2

---

## Investigation

### Step 4: Identify Failure Pattern

Break down by:

- error_code
- decline_code
- region
- payment method

---

### Step 5: Check External Dependencies

Verify payment provider status.

If provider issue:

- classify as external dependency
- reduce retry rate
- notify stakeholders

---

### Step 6: Inspect System Metrics

Check:

- latency (p95, p99)
- error rates
- timeout rates

---

### Step 7: Review Logs

Search by:

- `payment_intent_id`
- `request_id`

Look for:

- repeated failures
- retry loops
- idempotency conflicts

---

### Step 8: Check Retry System

Verify:

- retry queue backlog
- retry success rate

---

### Step 9: Validate Webhooks

Check:

- delivery delays
- failed events
- duplicate handling

---

## Mitigation

### External Issue

- reduce retries
- wait for provider recovery
- communicate status

---

### Internal Issue

- scale services
- restart failing components
- fix deployment issues

---

### Rate Limiting

- throttle requests
- increase backoff

---

## Escalation

Escalate when:

- SEV1 or SEV2 detected
- issue persists longer than 30 minutes
- root cause unclear

Escalation path:

- primary on-call → engineering lead
- engineering lead → incident commander
- notify leadership for SEV1

---

## Communication

### Internal Updates

Provide updates every:

- 15 minutes for SEV1
- 30 minutes for SEV2

---

### Customer Communication

- acknowledge issue
- avoid technical details
- provide timeline if known

---

## Resolution Criteria

Incident is resolved when:

- failure rate returns to baseline
- no new alerts triggered
- retry system stabilizes

---

## Post-Incident

After resolution:

- perform root cause analysis
- document timeline
- identify prevention steps
- update runbook if needed

---

## Notes

- always rely on webhook events as source of truth
- avoid assumptions from client-side success
- log all actions taken during incident

---

Last updated: 2026-02-01
