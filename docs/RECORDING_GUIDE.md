# Recording the 5-minute pitch video

You have two options. Option A is fastest (10 minutes of work).

## Option A — record the auto-pitch deck (recommended)

The deck at `pitch/index.html` auto-advances through 12 slides in **4 min 40 s** and
narrates each slide aloud using your browser's built-in voices.

1. Open `pitch/index.html` in **Edge or Chrome** (double-click it)
2. Start your screen recorder:
   - **Xbox Game Bar** (already on Windows): `Win + Alt + R` — records the active window
   - or **OBS Studio**: add a "Window Capture" source for the browser
3. Click **▶ Start pitch** on the slide
4. Let it play through all 12 slides (~4:40). Don't touch anything.
5. Stop recording (`Win + Alt + R` again) — trim the start/end if needed

**Controls while recording:** `→` next slide · `←` previous · `P` pause/resume
(only use these if you deliberately want to jump around)

### Better video: intercut the live demo

For a stronger submission, pause the deck before the last slide (`P`), switch windows
and screen-record 60–90 s of the live product, then resume:

```powershell
# terminal 1
cd E:\Project\Rozarpayy\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# terminal 2
cd E:\Project\Rozarpayy\dashboard
npm run dev
# browser: http://localhost:3000 , then:
curl -X POST http://localhost:8000/api/v1/admin/simulator/start -H "X-API-Key: change-me-demo-key"
```

Show, in this order:
1. Live feed going green → a flagged card with rule chips + explanation appears
2. Review queue → resolve one as fraud → AI follow-up suggestion appears
3. Audit page → chain badge green; open `/audit/verify` in another tab
4. Metrics page → quote PR-AUC and precision/recall out loud

## Option B — narrate over the deck yourself

Same as Option A but don't click "Start pitch" (avoids TTS voice); advance slides manually
with `→` while you talk. The narration text is simply each slide's content — or read
`docs/PITCH.md` which has the same story with timestamps.

## Checklist before uploading

- [ ] Fresh run: delete `backend/data/sentipay.db`, boot API, start simulator ~90 s early so flagged items exist
- [ ] `artifacts/metrics.json` numbers match what the deck/voice says (retrain if unsure)
- [ ] Close Slack/email notifications (Win + A → Do Not Disturb / Focus assist)
- [ ] Browser zoom ~110% so text is readable in 1080p
- [ ] Audio check: TTS voice audible in recording (Game Bar records system audio by default)
- [ ] Final length ≤ 5:30
- [ ] Upload to YouTube (unlisted) or Google Drive, paste link in the application form along with the repo URL

## If the voice sounds robotic

Install better Windows voices: Settings → Time & Language → Speech → Manage voices →
add e.g. "Microsoft Guy Online (Natural)" or "Aria", then pick it in Edge
(edge://settings → Accessibility isn't needed; Chrome picks the default).
Or skip TTS entirely (Option B) — a human voice scores better anyway.
