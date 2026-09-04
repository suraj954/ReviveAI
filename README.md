# ReviveAI

> **An AI-powered revenue recovery engine that detects failed payments, estimates recovery potential, and executes safe, bounded workflows to win revenue back.**

Built for the **Razorpay AI Builder Hackathon 2026** under the **AI Revenue Recovery** track.

---

## 🎯 The Problem

A failed payment does not always mean a lost customer.

Payments can fail because of:

- Temporary bank failures
- Network interruptions
- Authentication failures
- Payment gateway errors
- Insufficient funds at a specific moment
- Accidental checkout abandonment

For merchants, many of these failures eventually become permanently lost revenue.

Traditional payment systems primarily answer:

> Did the payment succeed?

ReviveAI asks a more valuable question:

> **Did revenue slip away, and can it be safely recovered?**

ReviveAI treats eligible payment failures as recovery opportunities rather than the end of a transaction.

---

# 🏆 Hackathon Track Alignment

## Razorpay AI Revenue Recovery

The AI Revenue Recovery track challenges builders to:

> Find revenue slipping away and win it back. Build an agent that detects revenue at risk, determines the right intervention, and executes a bounded recovery workflow.

ReviveAI is designed directly around this lifecycle.

| Track Requirement | ReviveAI Implementation |
|---|---|
| Detect revenue at risk | Razorpay payment failure webhooks |
| Determine intervention | ML recovery probability + policy evaluation |
| Apply AI intelligence | ML-based recovery scoring |
| Enforce safety | Guardrails and lifecycle validation |
| Execute workflow | Recovery checkout generation |
| Keep actions bounded | Maximum recovery attempt limits |
| Recover revenue | Secure Razorpay payment retry |
| Measure results | Merchant recovery intelligence dashboard |

> **ReviveAI is not simply a payment retry system. It is a decision-driven revenue recovery engine.**

---

# ⚡ Solution Overview

ReviveAI sits between payment failure detection and customer recovery.

```text
Customer Checkout
        |
        v
Razorpay Payment
        |
        | Payment Failed
        v
Verified Razorpay Webhook
        |
        v
ReviveAI Event Processing
        |
        v
AI Recovery Agent
        |
        +--> Payment Features
        |
        +--> ML Recovery Probability
        |
        +--> Policy Evaluation
        |
        +--> Guardrails
        |
        v
Recovery Decision
        |
        +--> Do Nothing
        |
        +--> Safe Recovery Workflow
                  |
                  v
           Recovery Checkout
                  |
                  v
           Customer Retry
                  |
                  v
           Verified Payment Event
                  |
                  v
           Revenue Recovered
🔥 End-to-End Recovery Proof

ReviveAI implements a complete provider-verified recovery lifecycle.

1. Customer starts checkout
            |
            v
2. Merchant creates Razorpay order
            |
            v
3. Customer attempts payment
            |
            v
4. Payment fails
            |
            v
5. Razorpay webhook received
            |
            v
6. Webhook signature verified
            |
            v
7. Payment event persisted
            |
            v
8. Recovery Agent evaluates payment
            |
            v
9. ML recovery probability calculated
            |
            v
10. Guardrails validate recovery
            |
            v
11. Recovery workflow approved
            |
            v
12. Recovery checkout generated
            |
            v
13. Customer retries payment
            |
            v
14. Razorpay webhook reconciles outcome
            |
            v
15. Revenue marked recovered
Important design principle

Recovery is not marked successful based only on a frontend callback.

Revenue is marked recovered only after the payment lifecycle is reconciled using a verified provider event.

🧠 Recovery Intelligence

ReviveAI does not blindly retry every failed payment.

Each failed payment passes through an intelligent decision pipeline.

1. Feature Extraction

Relevant payment signals are transformed into structured features.

Examples include:

Payment amount
Currency
Payment failure characteristics
Previous recovery attempts
Time since payment failure
Payment lifecycle state

These features are passed to the recovery intelligence layer.

2. ML Recovery Probability

The ML model estimates the likelihood that a failed payment can be successfully recovered.

Payment Failure
       |
       v
Feature Extraction
       |
       v
ML Recovery Model
       |
       v
Recovery Probability

ReviveAI uses a machine learning-based scoring pipeline to generate a recovery probability.

The probability is persisted with the recovery attempt for:

Observability
Decision transparency
Auditability
Merchant intelligence
3. Guardrails

A high recovery probability alone does not automatically trigger action.

ReviveAI applies business and safety constraints including:

Maximum recovery attempts
Payment lifecycle validation
Duplicate recovery prevention
Payment state validation
Recovery workflow expiration checks

Example bounded constraint:

MAX_RECOVERY_ATTEMPTS = 3

This ensures recovery workflows remain controlled and prevents aggressive retry loops.

4. Policy Decision

The policy layer combines intelligence with operational constraints.

ML Probability
      +
Business Guardrails
      +
Payment Lifecycle State
      |
      v
Recovery Decision

Possible outcomes include:

Recover
Do not recover
Recovery unavailable
Recovery expired
Payment already resolved
🏗️ Architecture
High-Level Architecture
                    +----------------------+
                    |   Demo Storefront    |
                    |    React + Vite      |
                    +----------+-----------+
                               |
                               | Create Order
                               v
                    +----------------------+
                    |      ReviveAI        |
                    |      FastAPI         |
                    +----------+-----------+
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
       Order Management   Recovery Agent   Dashboard API
              |                |                |
              v                v                v
          Razorpay        ML + Policy   Merchant Insights
                               |
                               v
                          Guardrails
                               |
                               v
                        Recovery Workflow
                               |
                               v
                      Recovery Checkout
                               |
                               v
                        Razorpay Webhooks
                               |
                               v
                     Lifecycle Reconciliation
✨ Key Features
1. Payment Failure Detection

ReviveAI receives Razorpay payment lifecycle events through webhooks.

Supported events include:

payment.failed
payment.captured
order.paid
payment_link.paid

Incoming events are validated before processing.

2. Webhook Signature Verification

Security is enforced using Razorpay webhook signatures.

Incoming Webhook
       |
       v
Extract Signature
       |
       v
HMAC SHA256 Verification
       |
       +--> Invalid → Reject
       |
       +--> Valid
              |
              v
        Process Event

This prevents unauthorized systems from triggering recovery workflows.

3. AI Recovery Agent

The Recovery Agent orchestrates the intelligence layer.

Responsibilities include:

Building payment features
Calling the recovery ML model
Calculating recovery probability
Applying recovery policy
Enforcing guardrails
Creating recovery decisions
RecoveryAgent
      |
      +--> Feature Builder
      |
      +--> ML Model
      |
      +--> Guardrails
      |
      +--> Policy Engine
4. Bounded Recovery Attempts

ReviveAI prevents uncontrolled retry loops.

MAX_RECOVERY_ATTEMPTS = 3

Before generating another recovery workflow, the system evaluates existing attempts and lifecycle state.

This protects:

Customers
Merchants
Payment infrastructure

And ensures the recovery agent behaves responsibly.

5. Secure Recovery Access

Customers are not exposed to internal merchant intelligence.

ReviveAI generates customer-scoped recovery access tokens.

Customers can access:

Recovery status
Recovery availability
Recovery checkout

Customers cannot access:

Internal ML probability
Merchant analytics
Other payment records
Recovery policy internals
6. Recovery Scheduler

Recovery workflows are processed asynchronously.

The scheduler:

Finds due recovery attempts
Evaluates lifecycle state
Triggers recovery execution
Prevents duplicate execution
Enforces bounded attempts

This separates event ingestion from recovery execution.

7. Recovery Audit Trail

Important lifecycle events are recorded for observability.

Examples include:

payment_failed
recovery_evaluated
recovery_approved
recovery_created
recovery_checkout_generated
recovery_payment_completed
revenue_recovered

This makes AI decisions observable and easier to debug and audit.

8. Provider-Driven Webhook Reconciliation

Recovery completion is not trusted solely from the frontend.

Customer completes payment
           |
           v
Razorpay sends webhook
           |
           v
ReviveAI verifies webhook
           |
           v
Payment lifecycle updated
           |
           v
Recovery attempt resolved
           |
           v
Revenue marked recovered

This keeps recovery state provider-driven rather than frontend-driven.

🛍️ Customer Demo Storefront

ReviveAI includes a dedicated customer-facing demo storefront.

The storefront demonstrates the complete recovery journey.

Browse Product
      |
      v
Buy Now
      |
      v
Razorpay Checkout
      |
      +--> Payment Success
      |
      +--> Payment Failure
               |
               v
        ReviveAI Monitoring
               |
               v
        Recovery Evaluation
               |
               v
        Recovery Available
               |
               v
        Secure Retry Checkout
               |
               v
        Payment Success

The customer experience is intentionally separated from the merchant intelligence layer.

📊 Merchant Recovery Intelligence Dashboard

ReviveAI includes a merchant-facing dashboard that provides visibility into revenue recovery.

The dashboard helps merchants understand:

Total payment activity
Failed payments
Recovery attempts
Successfully recovered payments
Recovery success rate
Revenue recovered
Revenue at risk
Recovery probability
Decision reasons
Recovery lifecycle state

Each payment can also expose detailed Recovery Intelligence, including:

Failure diagnosis
AI recovery decision
Recovery probability
Guardrail outcome
Recovery timeline
Audit events
Revenue flow

This transforms payment recovery from a black-box process into an observable business workflow.

📸 Demo Screenshots

Screenshots from the live end-to-end demo will be added here.

Suggested screenshots:

Customer storefront
Failed payment state
Recovery opportunity
Merchant dashboard
Recovery Intelligence view
Successfully recovered revenue
🛠️ Tech Stack
Backend
Python
FastAPI
SQLAlchemy
Pydantic
Uvicorn
Machine Learning
Scikit-learn
Logistic Regression
Feature engineering pipeline
Payments
Razorpay Orders API
Razorpay Checkout
Razorpay Webhooks
Frontend
Merchant Dashboard
React
Vite
Customer Demo Storefront
React
Vite
Razorpay Checkout
Infrastructure
PostgreSQL
Alembic migrations
zrok for secure webhook tunneling
📁 Project Structure
ReviveAI
│
├── backend
│   │
│   ├── alembic
│   │
│   ├── app
│   │   │
│   │   ├── agents
│   │   │   └── recovery_agent.py
│   │   │
│   │   ├── api
│   │   │   ├── dashboard.py
│   │   │   ├── insights.py
│   │   │   ├── orders.py
│   │   │   ├── recovery_checkout.py
│   │   │   └── webhooks.py
│   │   │
│   │   ├── db
│   │   │
│   │   ├── decisions
│   │   │   ├── guardrails.py
│   │   │   └── policy.py
│   │   │
│   │   ├── events
│   │   │
│   │   ├── guardrails
│   │   │
│   │   ├── ml
│   │   │   ├── dataset.py
│   │   │   ├── features.py
│   │   │   ├── recovery_model.py
│   │   │   └── train.py
│   │   │
│   │   ├── models
│   │   │   ├── payment.py
│   │   │   ├── recovery_attempt.py
│   │   │   ├── recovery_event.py
│   │   │   └── webhook_event.py
│   │   │
│   │   ├── razorpay
│   │   │   ├── client.py
│   │   │   ├── orders.py
│   │   │   └── recovery_gateway.py
│   │   │
│   │   └── services
│   │       ├── recovery_service.py
│   │       ├── recovery_executor.py
│   │       ├── recovery_scheduler.py
│   │       ├── recovery_scheduler_runner.py
│   │       ├── recovery_trigger.py
│   │       ├── recovery_audit_service.py
│   │       └── recovery_token.py
│   │
│   ├── tests
│   │
│   └── main.py
│
├── frontend
│   └── Merchant Recovery Intelligence Dashboard
│
├── demo-storefront
│   ├── src
│   │   ├── components
│   │   ├── data
│   │   └── services
│
├── .env.example
├── .gitignore
└── README.md
🚀 Local Setup
1. Clone Repository
git clone https://github.com/suraj954/ReviveAI.git
cd ReviveAI
2. Create Python Environment
cd backend
python -m venv .venv
Windows
.venv\Scripts\activate
Linux / macOS
source .venv/bin/activate
3. Install Backend Dependencies
pip install -r requirements.txt
4. Configure Environment

Create a .env file in the project root or backend configuration location as required.

RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

Never commit real secrets.

5. Database Setup

Run Alembic migrations:

cd backend
alembic upgrade head
6. Start Backend

From the backend directory:

uvicorn main:app --reload

Backend:

http://127.0.0.1:8000

Swagger API documentation:

http://127.0.0.1:8000/docs
🛍️ Running the Customer Storefront
cd demo-storefront
npm install
npm run dev

The storefront runs separately from the merchant dashboard.

This allows the demo to show two perspectives:

Customer
   |
   v
Demo Storefront
   |
   v
ReviveAI Backend
   |
   v
Merchant Intelligence Dashboard
🔗 Razorpay Webhook Setup

For local development, the backend must be publicly reachable.

ReviveAI uses zrok for secure webhook tunneling.

Example:

zrok2 share public http://127.0.0.1:8000

Configure the generated public URL in Razorpay.

Webhook endpoint:

https://YOUR_PUBLIC_URL/api/webhooks/razorpay

Recommended events:

payment.failed
payment.captured
order.paid
payment_link.paid
🧪 Testing

The backend contains automated tests covering critical components.

Examples include:

Configuration
Razorpay connection
Webhook verification
Recovery service
Recovery scheduler
Recovery lifecycle
ML model pipeline
Guardrails
Policy decisions

Run all tests:

pytest -q

Current verified test status:

92 passed
🎬 Recommended Demo Flow
Step 1 — Customer Checkout

Open the ReviveAI demo storefront.

Select a product and click:

Buy Now
Step 2 — Trigger Payment Failure

Open Razorpay Checkout and intentionally trigger a failed payment.

The storefront displays a payment interruption state.

Step 3 — Webhook Detection

Razorpay sends:

payment.failed

to:

/api/webhooks/razorpay

ReviveAI then:

Verifies the webhook
Records the failure
Triggers recovery evaluation
Step 4 — AI Evaluation

The Recovery Agent:

Build Features
      |
      v
Calculate Recovery Probability
      |
      v
Apply Guardrails
      |
      v
Run Recovery Policy

If recovery is approved:

Recovery Workflow Created
Step 5 — Customer Recovery

The storefront checks the customer-safe recovery endpoint.

When recovery becomes available, the customer receives a secure retry opportunity.

Step 6 — Successful Recovery

The customer completes payment through Razorpay Checkout.

Razorpay sends a verified payment event.

ReviveAI reconciles the lifecycle.

Result:

Revenue Recovered
Step 7 — Merchant Intelligence

The merchant dashboard reflects:

Failed payment
Recovery attempt
Recovery decision
Recovery probability
Guardrail decision
Verified recovery
Recovered revenue

This demonstrates measurable business impact.

🧪 Recovery Scenarios Tested

The complete recovery lifecycle has been tested across multiple scenarios.

Scenario 1 — Failed Payment → Recovery → Success
Payment Failed
      ↓
AI Evaluation
      ↓
Recovery Checkout
      ↓
Customer Retry
      ↓
Verified Success
      ↓
Revenue Recovered
Scenario 2 — Failed Payment → Recovery Awaiting Payment → Success
Payment Failed
      ↓
Recovery Created
      ↓
Awaiting Customer Payment
      ↓
Customer Completes Recovery
      ↓
Webhook Verification
      ↓
Revenue Recovered
Scenario 3 — Recovery Failure → Bounded Re-evaluation
Payment Failed
      ↓
Recovery Attempt
      ↓
Recovery Payment Failed
      ↓
Lifecycle Re-evaluation
      ↓
Bounded Next Attempt

These scenarios validate that ReviveAI handles both successful and unsuccessful recovery paths while maintaining bounded execution.

🧭 Design Principles
Do Not Recover Everything

Not every failed payment should be retried.

Recovery decisions depend on:

Recovery probability
Guardrails
Lifecycle state
Attempt limits
Keep AI Actions Bounded

Autonomous systems interacting with financial workflows require constraints.

ReviveAI limits:

Number of attempts
Valid lifecycle transitions
Recovery eligibility
Provider Events Are the Source of Truth

Frontend success callbacks are not sufficient.

Razorpay webhooks reconcile actual payment outcomes.

Separate Customer and Merchant Intelligence

Customers receive:

Recovery availability
Recovery checkout

Merchants receive:

Recovery probability
Decision reasons
Revenue analytics
Make AI Decisions Observable

Recovery decisions generate lifecycle and audit events.

This makes the system easier to:

Debug
Evaluate
Audit
Trust
🔮 Future Improvements

Potential future directions include:

Advanced Recovery Models
Gradient boosting recovery models
Temporal payment behavior models
Customer segmentation
Context-aware intervention selection
Agentic Intervention Strategies

Different recovery actions could be selected based on payment context:

Failure Type
     |
     v
AI Intervention Selection
     |
     +--> Immediate Retry
     +--> Delayed Retry
     +--> Payment Link
     +--> Alternative Payment Method
     +--> No Intervention
Revenue Optimization

The recovery agent could optimize:

Expected recovered revenue
Customer friction
Retry timing
Intervention cost
Production Infrastructure

Potential production improvements:

Redis queues
Distributed workers
Production scheduler infrastructure
Model monitoring
Automated model retraining
💡 Why ReviveAI Matters

Without intelligent recovery:

Payment Failed
      |
      v
Revenue Lost

With ReviveAI:

Payment Failed
      |
      v
AI Evaluation
      |
      v
Safe Recovery Decision
      |
      v
Bounded Intervention
      |
      v
Customer Retry
      |
      v
Verified Revenue Recovery

ReviveAI transforms payment failure handling from a passive event into an intelligent, observable, and bounded revenue recovery workflow.

🎯 Impact

ReviveAI demonstrates how AI agents can responsibly operate in financial workflows.

The system:

Detects revenue leakage
Evaluates recovery potential
Applies ML intelligence
Enforces guardrails
Executes bounded workflows
Protects customer access
Reconciles real provider events
Measures actual recovered revenue
🧠 ReviveAI in One Sentence

ReviveAI is an AI-powered revenue recovery agent that detects failed payments, intelligently determines whether recovery is worthwhile, and executes safe, bounded workflows to give lost revenue another chance.

👨‍💻 Built By

Suraj Dwivedi

Project Repository:

ReviveAI on GitHub

GitHub:

Suraj Dwivedi's GitHub

License

Built as a hackathon project for the Razorpay AI Builder Hackathon 2026.