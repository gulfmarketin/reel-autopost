# Reel Autopost

Every 3 hours, GitHub Actions picks the next unposted row from the Google Sheet, renders it as a 9:16 reel (glowing motion graphics, sound effects only, no music), and publishes it to Instagram with the row's Caption.

- **Video text** = the `Text` column: the hook first, then the `Payoff:` line with an arrow pointing to the caption.
- **Duplicates are skipped automatically.** Identical `Text` rows are posted once.
- Set a row's `Status` to `SKIP` to exclude it. Only `READY` or empty rows are posted.
- What's already posted is tracked in `state/posted.json` (the bot commits it after each post).
- The visual changes between 4 motifs in rotation, so consecutive reels don't look identical.

## One-time setup

### 1. Repo secrets and variables
Settings → Secrets and variables → Actions:

| Type | Name | Value |
|---|---|---|
| Variable | `SHEET_CSV_URL` | `https://docs.google.com/spreadsheets/d/1jgRdVLZr_02XpWACLEo7wLIgc8SGMUTI5KSK50ypQ9w/export?format=csv` (sheet must stay "Anyone with the link can view") |
| Variable | `HANDLE` | optional, e.g. `@yourpage`, shown small at the bottom |
| Secret | `IG_USER_ID` | your Instagram professional account ID |
| Secret | `IG_ACCESS_TOKEN` | a Page access token with publishing permission |

### 2. Get a token that doesn't expire (recommended)
1. Go to developers.facebook.com → **Create app** → type **Business**. Add the **Instagram** product with Facebook Login for Business.
2. In **Meta Business Suite → Settings → Users → System users**, add a system user (Admin). Assign it your **Facebook Page** and **Instagram account** with full control, and assign the app.
3. Click **Generate token** → choose the app → tick `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`, `pages_show_list` → set expiry to **Never**.
4. Find your IG user ID: open
   `https://graph.facebook.com/v21.0/me/accounts?fields=name,instagram_business_account&access_token=TOKEN`
   and copy `instagram_business_account.id`.

### 3. Test before going live
Actions → **Autopost reel** → **Run workflow** → tick **Render only**. Download the `reel` artifact and check the video.
Then run it once without the tick to post the first reel. After that, it runs on its own every 3 hours.

## Change things
- **Frequency:** edit the `cron` line in `.github/workflows/autopost.yml` (UTC). `17 */3 * * *` = every 3 h.
- **Pause:** Actions → Autopost reel → ⋯ → **Disable workflow**.
- **Look:** colours, fonts and motifs are in `template/reel.html`.
- **Test locally:** `DRY_RUN=1 python scripts/autopost.py --csv sheet.csv --row 5`

## Limits
- Instagram allows a limited number of API posts per 24 hours. At 8 a day, you stay well under it.
- GitHub can start scheduled runs several minutes late at busy times.
- If a run fails, nothing is marked as posted; the next run tries the same row again.
