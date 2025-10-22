# 🎤 Demo Script for Billing Managers

**Time**: 10 minutes
**Goal**: Get pilot commitment

---

## Before Demo (Setup)

- [ ] Backend running: `docker-compose up -d`
- [ ] Frontend deployed to Cloudflare Pages
- [ ] Test patient created in Medplum
- [ ] Tested eligibility check works
- [ ] Tested AI scrubber works
- [ ] ROI spreadsheet ready

---

## Introduction (1 min)

"Hi [Name], thanks for taking time to chat. I'm building an AI-powered billing platform that cuts denials in half and increases collections by 20%+.

I want to show you two features that save 100+ minutes per day for billing staff. This is a live demo, not slides."

**[Share screen with app]**

---

## Demo 1: Real-Time Eligibility Check (2 min)

### Setup
"Right now, your staff probably calls insurance companies to verify eligibility. Takes 5-10 minutes per patient, right?"

### Action
1. Enter test patient ID
2. Enter provider NPI
3. Click "Check Eligibility"
4. **[Wait <3 seconds]**
5. Results appear

### Talk Track
"See that? 3 seconds. Not 5 minutes. And look at what we get:
- Coverage status: Active
- Plan name: Immediately visible
- Copay: $30 - your front desk knows to collect
- Deductible: $1,500 - patient owes this first
- Out-of-pocket max: $5,000

The system caches this for 24 hours, so you don't pay for duplicate checks."

### Value Prop
"If your staff checks 20 patients per day:
- Old way: 20 × 5 min = 100 minutes wasted
- New way: 20 × 10 seconds = 3 minutes
- **Savings: 97 minutes per day = 8 hours per week = $400/month in staff time**

And that's just ONE feature."

---

## Demo 2: AI Claim Scrubber (3 min)

### Setup
"The bigger problem is denials, right? Industry average is 15%. Every denied claim costs $150 to fix.

Let me show you how AI catches errors BEFORE you submit."

### Action - Show Error
1. Create test claim:
   - CPT: 99213 (office visit level 3)
   - ICD-10: Z23 (immunization encounter)
   - Payer: Aetna

2. Submit to AI scrubber
3. **[Wait 2 seconds]**
4. AI flags error: "Medical necessity mismatch. CPT 99213 requires acute/chronic condition diagnosis. Z23 is preventive."

### Talk Track
"See that? The AI caught it. This claim would've been denied.

That's because insurance companies want to see that a level 3 visit (99213) is medically necessary - meaning the patient has an actual condition. Z23 is just an immunization code.

Without AI, your biller submits this, it gets denied 2 weeks later, then someone spends 30 minutes fixing and resubmitting it."

### Action - Show Fix
1. Change ICD-10 to J06.9 (Upper respiratory infection)
2. Submit again
3. AI approves: "Ready to submit. No errors found."

### Talk Track
"Fixed. Ready to go. Clean claim.

Here's the math on denials:
- 200 claims/month × 15% denial rate = 30 denials
- 30 denials × $150 per fix = **$4,500 lost per month**

Our AI reduces denials to 7%:
- 200 claims × 7% = 14 denials
- **Saves 16 denials = $2,400 per month**"

---

## Demo 3: ROI Calculator (2 min)

**[Open spreadsheet or show on screen]**

```
Current State (Your Practice):
- Claims per month: 200
- Denial rate: 15%
- Denials: 30
- Cost per denial: $150
- Monthly loss: $4,500

With Our AI:
- Claims per month: 200
- Denial rate: 7%
- Denials: 14
- Monthly savings: $2,400

Plus:
- Eligibility time saved: $400/month
- Total savings: $2,800/month

Our cost: $199/month

ROI: $2,800 / $199 = 14X return
```

### Talk Track
"So you save $2,800 per month. We charge $199. That's a 14X return on investment.

Most billing software costs $450-600/month and doesn't have AI. We're giving you AI automation for $199."

---

## The Ask (1 min)

"Here's what I'm offering:

**90-day free pilot**
- You use the platform free for 3 months
- We process your claims
- We track metrics: denial rate, clean claim rate, days in AR
- After 90 days, I show you the results

If we don't improve your metrics by at least 15%, you pay nothing.

If we do improve your metrics (which I'm confident we will), you pay $199/month after the pilot.

Zero risk. Guaranteed results. What do you say?"

---

## Objections & Responses

### "We already use [Kareo/AdvancedMD]"
**Response**: "Great! Our AI works alongside any PM system. We check eligibility before you schedule, scrub claims before you submit through Kareo, and help with denials. Think of us as an AI layer on top of what you already have."

### "We don't have time to learn new software"
**Response**: "It's literally 2 screens - eligibility check and claim scrubber. I can train your entire team in 15 minutes. And it SAVES you time - 97 minutes per day on eligibility alone."

### "What if the AI makes a mistake?"
**Response**: "Great question. The AI flags potential issues, but your billers still review and submit. Think of it like spell-check - it catches errors, but humans have final say. And we track AI accuracy - it's currently 93% accurate, better than most human billers."

### "We need to think about it"
**Response**: "Totally understand. But here's the thing - it's a FREE pilot. No credit card, no contract. Worst case, you get 90 days of free eligibility checks and claim scrubbing. Best case, you save $2,800/month and cut denials in half. Can I at least get you set up for the pilot?"

### "We're too busy right now"
**Response**: "I hear you. But that's exactly WHY you need this. You're busy BECAUSE of denials and manual work. This frees up time. The pilot takes 10 minutes to set up, then runs in the background. Can we start with just eligibility checks for your front desk?"

---

## Closing (1 min)

"So can I count you in for the 90-day pilot? I'll get you set up this week, train your team in 15 minutes, and you'll start seeing results immediately."

**[Get verbal YES or schedule follow-up]**

If YES:
- Get practice info (NPI, billing manager name, email)
- Schedule 30-min onboarding call
- Send pilot agreement

If NO/MAYBE:
- Ask what would make them comfortable
- Offer to just set up eligibility checks first
- Schedule follow-up for next week

---

## Post-Demo Follow-Up

**Same Day:**
- Send thank you email
- Attach one-pager with ROI summary
- Include Calendly link for onboarding

**2 Days Later:**
- Check in: "Any questions?"
- Offer to demo to their billing staff directly

**1 Week Later:**
- Final follow-up
- "Still have 3 pilot spots open this month..."

---

## One-Pager Template (Send After Demo)

```
AI-Powered Medical Billing Platform
Cut Denials in Half • 14X ROI • 90-Day Free Pilot

WHAT WE DO:
✓ Real-time eligibility verification (3 seconds vs 5 minutes)
✓ AI claim scrubbing (catches errors before submission)
✓ Automated denial management (coming Month 2)

YOUR SAVINGS:
• Eligibility time: $400/month
• Denied claims: $2,400/month
• Total: $2,800/month
• Our cost: $199/month
• ROI: 14X

90-DAY FREE PILOT:
• No credit card required
• Full platform access
• 15-minute training
• Guaranteed 15% improvement or free forever

NEXT STEPS:
1. Schedule onboarding: [Calendly link]
2. We set up your account (10 min)
3. Train your team (15 min)
4. Start saving money Day 1

Questions? Text/call: [Your number]
```

---

## Success Metrics

**Good Demo:**
- Asked 3+ questions
- Engaged with ROI calculation
- Mentioned current pain points
- Said "that would save us time"

**Great Demo:**
- Immediately said "when can we start"
- Brought up specific denial issues
- Asked about other practices using it
- Verbal YES to pilot

**Conversion Rate Goal:**
- 50%+ should commit to pilot after demo
- If <50%, revise demo script based on objections

---

**Remember: You're not selling software. You're selling saved time and money. Keep it real, show the value, close the deal.** 🚀
