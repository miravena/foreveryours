# One-week trial: information and consent sheet

ForeverYours is a voice companion for an older adult, with a panel for the family caregiver. We
are asking one household to use it for seven days on a computer in your home, so we can learn
what really happens. It is a student-built prototype. You may say no, and you may stop at any
time without giving a reason.

## What is recorded, and where it lives

On your computer, in the `data/` folder of the install (the trial is run so that memory is
kept there; some temporary copies of audio and session files can also sit in the computer's
temporary folder and are cleared when the program is closed, or by us at the end):
- **Memory** (`data/local_senior.json`): facts the companion keeps (names, hobbies, family).
- **Caregiver flags** (`data/flags.json`): a note when a safety concern or distress is detected.
- **Conversation text** for the current session, and **voice audio** while it is processed.
  Speech is turned into text on your computer; audio is not sent anywhere.

The caregiver also keeps a two-line paper or text log each day (see `MEASUREMENTS.md`).

## What leaves your computer, in plain words

Every time the older adult speaks, the **text of what was said, the companion's reply, and the
remembered facts and caregiver notes used to answer** are sent over the internet to **Nebius
Token Factory**, a company that runs the AI models. This happens for two jobs: writing the
reply, and a second safety check on the same text. It uses your household's own Nebius key.
Nebius's own terms and privacy policy decide what it keeps; read them at
<https://nebius.com/privacy> before you sign, and ask us if anything is unclear. We have not
audited Nebius's practices ourselves.

Nothing else leaves by itself. At the end of the week, only the **daily counts** on
`MEASUREMENTS.md` (numbers, no names or conversation) come to us, **by hand, and only if the
family agrees** after reading them.

## Who can read it

The people in your household with access to the computer and the caregiver panel. The team
does not have remote access. We see only what you choose to hand over. We will not publish
anything that identifies you.

## Not a medical device, not an emergency service

The companion does not diagnose, treat or monitor health, and it can miss things, including
falls and distress. It cannot call anyone for help. **In an emergency call your local
emergency number (999 / 995 / 911) as you normally would.** The caregiver keeps all usual
arrangements for checking in on the older adult. Do not rely on this prototype for safety.

## Withdrawing and deletion

Tell the caregiver or us at any time and the trial stops that day. At the end, or on request
sooner, we will help you delete the `data/` folder, the temporary folder `foreveryours-sessions`, the `.env` file and the daily log, and you
should revoke the Nebius key in your Nebius account. Counts already handed over can be
removed on request.

## Agreement

I have read this sheet and had the chance to ask questions. I understand that what is said to
the companion is sent to Nebius to produce replies, and that I can stop at any time.

Older adult: ______________________  Date: ________
Caregiver:   ______________________  Date: ________
Team member: ______________________  Date: ________
