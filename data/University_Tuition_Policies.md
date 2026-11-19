# University Tuition Policies

**Document ID:** UNI-TUITION-2026-01  
**Version:** 1.0  
**Effective academic year:** 2026–2027  
**Status:** Fictitious teaching document for SE 4458

> This document contains general university policies. It does not contain student-specific balances, transactions, or scholarship eligibility records. The Tuition REST API and its database are the authoritative sources for live account information.

## 1. Scope and terminology

**Tuition total** is the assessed tuition for a student and academic term, before or after adjustments as recorded by the tuition system. **Outstanding balance** is the unpaid amount currently recorded for that student. **Term** identifies the academic billing period (for example, `2026-FALL` or `2027-SPRING`). **Payment confirmation** means the student explicitly approves the amount and term before the assistant submits a payment.

## 2. Payment deadlines

### 2.1 Fall term

The payment deadline for the Fall 2026 term is **September 30, 2026**. A student should settle the outstanding balance or have an approved installment arrangement by that date.

### 2.2 Spring term

The payment deadline for the Spring 2027 term is **February 15, 2027**. Deadlines apply in the university's local time zone.

### 2.3 Payment posting

Payments recorded through supported banking channels may take up to **two business days** to appear in the university account. Students should check their current balance through the Tuition Query API rather than assume a payment has already posted.

## 3. Installment policy

### 3.1 Eligibility

Students with an outstanding balance of at least **$300** may request an installment arrangement. An arrangement is subject to approval; this policy does not establish whether a particular student has been approved.

### 3.2 Number and size of installments

An approved balance may be divided into **up to three installments**. Installments should be equal where possible; any rounding difference is added to the final installment. For example, a $3,000 balance can be divided into three payments of $1,000.

### 3.3 Installment schedule

For Fall 2026, approved installment due dates are **September 30, October 31, and November 30, 2026**. For Spring 2027, approved installment due dates are **February 15, March 15, and April 15, 2027**.

### 3.4 Partial payments versus installment approval

The payment API can record a partial payment and retain the remaining balance. **A partial payment is not, by itself, approval of an installment plan.** The AI assistant must not promise approval based solely on the policy document or a balance lookup.

## 4. Late fees

### 4.1 Late fee rule

A **2% one-time late fee** may be assessed on an overdue amount after the applicable due date, unless an approved exception applies. This document describes the rule but does not calculate or post fees automatically.

### 4.2 Example

If $1,000 is overdue and no exception applies, the illustrative late fee is $20. Whether a fee has actually been posted must be checked in the tuition system.

### 4.3 Exceptions

Students with a documented university-approved deferral may be exempt. Approval status is not available from this document.

## 5. Scholarships and adjustments

### 5.1 Merit scholarship

The standard merit scholarship may reduce assessed tuition by **25%** for eligible students. Eligibility is decided by the university and recorded separately.

### 5.2 Scholarship balance questions

The assistant may explain the 25% rule using this document, but must use the Tuition Query API to report the student's actual tuition total and balance. It must not infer that a student has a scholarship without an authoritative record.

## 6. Refunds and withdrawals

### 6.1 Early withdrawal

A student who formally withdraws within **14 calendar days of the term start** may be eligible for a refund of **80% of tuition payments associated with that term**, subject to administrative review.

### 6.2 Later withdrawal

After the 14-day period, refunds are reviewed individually and are not guaranteed. The AI assistant should direct students to the university finance office for a formal decision.

### 6.3 Refund processing

Approved refunds are generally processed within **15 business days**. This document does not provide refund status for any individual student.

## 7. Banking and payment instructions

### 7.1 Supported workflow

Students can review tuition information through the university mobile app or a participating banking app. The banking app may query tuition and submit a payment record through the university's Pay Tuition API.

### 7.2 Required payment information

The payment request must identify the **student number, term, and amount**. The payment amount must be positive and must not exceed the current outstanding balance unless the implementation explicitly supports overpayments.

### 7.3 Confirmation and safety

Before initiating a payment, the AI assistant must display the student, term, amount, and current balance, then obtain explicit confirmation. A question such as “Can I pay $500?” is not authorization to submit a transaction.

### 7.4 Duplicate submissions

The payment integration should use an idempotency key or equivalent mechanism to prevent duplicate payment records on retries. The assistant must not claim a payment succeeded until the API returns success.

## 8. Frequently asked questions

### 8.1 When is the Fall tuition deadline?

September 30, 2026. See Section 2.1.

### 8.2 Can I pay my balance in three installments?

The policy permits up to three installments for eligible balances, subject to approval. Check the live balance through the Tuition Query API and see Sections 3.1–3.4.

### 8.3 Why does my balance still show a payment I made today?

Payment posting can take up to two business days. See Section 2.3. The live account status must come from the Tuition Query API.

### 8.4 Can the assistant pay my tuition automatically?

No. The assistant must obtain explicit confirmation before calling the payment API. See Section 7.3.

## 9. Guidance for AI/MCP implementation

The MCP tool `search_tuition_policies(query)` should return relevant passages with **section ID, heading, document ID, and text**. A suitable response might be:

```json
{
  "document": "University_Tuition_Policies.md",
  "matches": [
    {
      "section": "3.2",
      "heading": "Number and size of installments",
      "text": "An approved balance may be divided into up to three installments."
    }
  ]
}
```

The AI agent should use MCP for policy questions, the Tuition REST API for live balances and payment operations, and both for questions combining a student's balance with a policy. REST API requests must go through the required API Gateway. The document is not an account database.
