# ForeverYours Privacy Notice

ForeverYours is designed with a strict "companionship without surveillance" invariant. To provide this service, we process and store specific data on your local machine or private cloud instance.

## What is Stored & Where
1. **Audio Recordings (`data/audio/`)**: Your voice is recorded when you speak to the AI. These `.wav` files are processed locally by the transcription engine. On the hosted web demo, the household session directory is removed about an hour after you close the webapp tab (Gradio's fixed closed-session cleanup timer), or after an hour of inactivity if the close event never arrives. Both recorded/uploaded input audio and Gradio's cached copies of served reply audio are separate: they remain in Gradio's own file cache, which is swept every 10 minutes and removes files older than 60 minutes, so an audio clip can live up to about 70 minutes. These are cleanup timers, not an instant tab-close deletion promise. We do **not** derive or store voiceprints (biometrics) from your audio.
2. **Conversation Transcripts (`data/*.json`)**: The text of your conversation is temporarily stored to provide context to the AI. This is wiped when the session ends.
3. **Memory (`data/local_senior.json`)**: Facts you share (name, hobbies, relationships) are stored permanently in a local database so the AI remembers you. You can ask the AI to forget any fact at any time.
4. **Caregiver Flags (`data/flags.json`)**: If you express a safety concern (e.g., a fall) or significant distress, a flag is stored and displayed on the caregiver dashboard. 

## Data Sharing
We do not sell your data. 
Text transcripts are sent to the Nebius Inference API to generate AI responses. Nebius does not retain or train on this data. Audio is never sent to the cloud.

## Your Rights
You own your memory. You may delete your profile at any time by deleting the `data/` folder on your machine. You may ask the AI to "Forget X", and it will permanently scrub that fact from its memory store.
