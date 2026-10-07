# Video Demo Storyboard & Script (3 Minutes / 180 Seconds)

**Hackathon Constraint**: <= 3 minutes, public YouTube upload, demonstrating real runtime execution on sponsor tech (Nebius Token Factory + NVIDIA open-weight models).

**Visual Setup**: Browser window recording the live hosted split-screen interface (`webapp.py` / Hugging Face Space), displaying **🧑 Senior Side** on the left and **👩 Caregiver Side** on the right.

---

## ⏱️ Second-by-Second Breakdown

| Timestamp | Visual Action | Spoken Voiceover Narration | Core Feature Highlighted |
|---|---|---|---|
| **0:00 – 0:30** | Title card: *ForeverYours: The Eldercare Voice Companion That Involves the Family*.<br/>Show headline statistics: 14M seniors living alone, 53M family caregivers. | "Over fourteen million older adults live alone in the US. When loneliness or memory slips strike, family caregivers bear the emotional burnout. But general-purpose voice assistants like ChatGPT fail here: they either keep silent secrets, promise things they can't physically do, or report to families behind the senior's back without honest disclosure." | **The Problem & Differentiation** (Anti-isolation, honest disclosure) |
| **0:30 – 1:00** | On the right column (**👩 Caregiver Side**), click *Submit Caregiver Memo*.<br/>Type/Record memo: *"Dad loves jazz. His grandson is named Leo. Avoid talking about driving. Sarah is dropping off groceries at 4 PM."*<br/>Click **Save Memo**. | "Meet ForeverYours. Onboarding takes sixty seconds. Dad's daughter, Sarah, writes or records a quick briefing note from work. Instantly, our multi-tier clinical memory engine indexes core biographical anchors, expiring afternoon schedules, and strict safety guardrails—without complex forms." | **Beat 1: Caregiver Onboarding & Memory Engine** (Permanent & Temporary Badges) |
| **1:00 – 1:40** | On the left column (**🧑 Senior Side**), click the mic or sample clip *senior_jazz.wav* (*"I was listening to some music earlier..."*).<br/>Companion speaks back within 0.91 seconds. | "Now Dad speaks naturally. In under a second—powered by NVIDIA Nemotron-3-Nano-30B MoE on Nebius Token Factory—ForeverYours responds with genuine warmth, recalling his love for jazz while respecting family guardrails. Notice what it didn't do: it didn't dump memories awkwardly, and it didn't hallucinate that it could physically deliver groceries." | **Beat 2: Natural Recall & Sub-Second Latency** (Token Factory Nemotron MoE) |
| **1:40 – 2:20** | Dad says or types: *"I fell down earlier and I'm scared."*<br/>Watch both columns simultaneously.<br/>Left column plays immediate voice reassurance: *"I'm right here with you, Dad. I'm letting Sarah know right now..."*<br/>Right column instantly flashes the **🚨 HIGH PRIORITY SAFETY ALERT DISPATCHED** card with **✅ Disclosed to Senior in conversation**. | "Now, the defining moment. Dad experiences a fall. In less than ten milliseconds, our local offline safety fast-path responds with spoken reassurance. Look at both sides at once: the companion explicitly tells Dad it is notifying Sarah, while the caregiver panel lights up with a high-priority alert. No silent surveillance. Pure, transparent trust." | **Beat 3: Emergency Fall & Split-Screen Honest Disclosure** (Core Differentiator) |
| **2:20 – 2:45** | Switch tabs or show Day-2 recall / Caregiver private memo.<br/>Show private note: *"Surprise 80th birthday party"* tagged with 🔒 `[Caregiver Only]` remaining strictly hidden from Dad's view. | "ForeverYours evolves. When Dad's preferences change, memories are gracefully superseded. And sensitive family notes—like a surprise birthday party—remain protected behind our strict caregiver privacy firewall, with zero leakage across turns." | **Beat 4: Memory Evolution & Privacy Firewall** |
| **2:45 – 3:00** | Show the pipeline-info panel and closing slide: Architecture diagram (Nebius Token Factory, NVIDIA Nemotron MoE, Faster-Whisper, Offline Fast-Path). | "Built for the Nebius and NVIDIA Hackathon, ForeverYours combines sub-second token latency, resilient offline safety nets, and transparent family connection. It's not an AI replacement for family—it's the family's voice in Dad's day when they can't be there." | **Tech Stack & Final Impact Pitch** |

---

## 🎙️ Recording Tips for the Team
1. **Resolution**: 1080p (1920x1080) browser capture with high zoom (~110%) so memory badges and alert cards are crisp and readable on mobile devices.
2. **Audio Levels**: Normalize voiceover to -14 LUFS; let the synthesized companion voice play cleanly during Beats 2 and 3.
3. **Cursor Movement**: Smooth, deliberate clicks. Pause for 2 seconds on the split-screen alert pop so judges can read both columns side by side.
