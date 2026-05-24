# Stripe Setup Guide

## 1. Create Stripe Account
Go to https://dashboard.stripe.com and create an account.

## 2. Get API Keys
Dashboard → Developers → API keys

Copy:
- **Secret key** → `sk_live_...` (or `sk_test_...` for testing)
- **Publishable key** → `pk_live_...`

Add to `backend/.env`:
```
STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
```

## 3. Create Products & Prices
Dashboard → Products → Add product

Create 3 products:
| Product | Price | Billing |
|---------|-------|---------|
| UniOps Starter | $49/month | Recurring |
| UniOps Professional | $149/month | Recurring |
| UniOps Enterprise | Contact | — |

After creating each price, copy the **Price ID** (starts with `price_`).

## 4. Update Price IDs
Edit `backend/app/integrations/stripe/client.py`:

```python
PLAN_PRICE_IDS = {
    "starter":      "price_XXXXX",      # ← paste your real Price ID
    "professional": "price_XXXXX",      # ← paste your real Price ID
    "enterprise":   "price_XXXXX",      # ← or remove if custom pricing
}
```

## 5. Setup Webhook
Dashboard → Developers → Webhooks → Add endpoint

- **URL**: `https://yourdomain.com/webhooks/stripe`
- **Events to listen**:
  - `checkout.session.completed`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`

Copy the **Webhook signing secret** → add to `.env`:
```
STRIPE_WEBHOOK_SECRET=whsec_YOUR_SECRET_HERE
```

## 6. Test Locally with Stripe CLI
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/webhooks/stripe

# Trigger test events
stripe trigger checkout.session.completed
stripe trigger invoice.payment_succeeded
```

## 7. Test Cards
Use these card numbers in test mode:
- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Requires 3D Secure**: `4000 0025 0000 3155`

Expiry: any future date. CVC: any 3 digits.

## Flow Summary
```
User clicks "Upgrade" 
  → POST /billing/checkout 
  → Stripe creates checkout session 
  → User redirected to Stripe-hosted page
  → User enters card details
  → Stripe charges card
  → Stripe sends webhook to /webhooks/stripe
  → checkout.session.completed event
  → BillingService._on_checkout_completed()
  → Subscription created in DB
  → Tenant plan upgraded
  → User redirected back to /settings/billing?success=1
```
