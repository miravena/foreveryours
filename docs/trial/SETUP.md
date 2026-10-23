# Setup guide for the caregiver

Plan on about 30 minutes, with a team member on the phone for the first time. You need a
computer (Windows, Mac or Linux) with a microphone and speakers, internet, and a Nebius
account with an API key. Your key is a password: never paste it into email, chat or a
document, and never read it out.

## 1. Install the basics
1. Install **Python 3.11 or newer** from python.org (on Windows, tick "Add Python to PATH").
2. Install **espeak-ng** (the speaking voice): Mac `brew install espeak-ng`; Ubuntu
   `sudo apt-get install -y espeak-ng`; Windows: follow the espeak-ng release page.
3. Download the ForeverYours folder (the team will give you the link or a USB stick) and open
   a terminal inside it.

## 2. Install the program
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
(Windows: use `.venv\Scripts\pip` and `.venv\Scripts\python` in place of `.venv/bin/...`.)
The first run downloads the speech model; wait for it.

## 3. Add your key
1. Copy the example file: `cp .env.example .env` (Windows: `copy .env.example .env`).
2. Open `.env` in a text editor (Notepad is fine). Find the line that starts
   `NEBIUS_API_KEY=` and replace everything after the `=` with your key, pasted from your
   Nebius account page. Save and close. Do not add quotes or spaces.
3. Check it without showing it: `scripts/key_status.sh`. It prints only
   `Nebius key: HTTP 200` when the key works. Any other result: redo step 3 or call us.
   Do not copy the `.env` file anywhere.
   (Windows: the two `scripts/*.sh` checks need Git Bash or WSL; install Git for Windows and
   run them from "Git Bash". If you cannot, the team member checks the key with you.)

## 4. Check it works
Run `scripts/smoke.sh`. It takes about 10 seconds and needs no internet key. It should end
without errors; if not, send us the last lines it prints (they never contain your key).

## 5. Start the companion
```
FY_SHARED_PROFILE=1 .venv/bin/python webapp.py
```
(Windows Command Prompt: `set FY_SHARED_PROFILE=1` on one line, then
`.venv\Scripts\python webapp.py`.) `FY_SHARED_PROFILE=1` is essential: it keeps the
household's memory in the install's `data/` folder from day to day. Without it each browser
visit starts a new, empty memory kept in the computer's temporary folder.
Open <http://localhost:7860> in your browser. Keep the terminal window open. Never use any
public web address for the trial. Try one spoken sentence. The program starts with made-up example facts (a caregiver "Sarah", a grandson "Leo", jazz,
a 4 PM errand). With the team member, remove them on the first call and add the real ones
(by voice or text memo, or by telling the companion to "forget" a fact) before the older adult
uses it. The right-hand panel shows what
the companion remembers and any flags: that is the caregiver panel.

## 6. Each day
Start it with step 5, let the older adult talk whenever they like, fill in the daily log
(`MEASUREMENTS.md`), and close the terminal window at night.

## If something goes wrong
No sound, no reply, or an error message: do not guess. Write down what you saw and call the
team member. To stop everything, close the terminal window.
