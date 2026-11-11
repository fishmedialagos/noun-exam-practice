# Deploy NOUN Exam Platform Online (Free)

This guide shows you how to put the platform on the internet so any NOUN student can use it with a link.

---

## Best Free Option: Render.com

### Step-by-step

1. Create a free account at: https://render.com

2. Click **New +** → **Web Service**

3. Connect your GitHub account (or upload the code)

4. If using GitHub:
   - Create a new repository
   - Upload all the files from `noun_exam_platform` folder
   - Connect that repo to Render

5. Configure the service:

   | Setting              | Value                          |
   |----------------------|--------------------------------|
   | Name                 | noun-exam-platform             |
   | Runtime              | Python 3                       |
   | Build Command        | `pip install -r requirements.txt` |
   | Start Command        | `python app.py`                |
   | Instance Type        | Free                           |

6. Click **Create Web Service**

7. Wait 2–5 minutes for it to build and start.

8. Render will give you a public link like:  
   `https://noun-exam-platform.onrender.com`

Share that link with students.

---

## Important Notes for Render

- Free plan sleeps after 15 minutes of inactivity (first load may be slow).
- The SQLite database works, but data may reset if the free instance restarts.  
  For permanent data, later upgrade or use a free PostgreSQL database.

---

## Alternative: Railway.app

1. Go to https://railway.app
2. Login with GitHub
3. Click **New Project** → **Deploy from GitHub**
4. Select your repo
5. Railway will auto-detect Python and deploy

---

## Alternative: Temporary Public Link with ngrok (Quick Testing)

1. Download ngrok: https://ngrok.com/download
2. Run your app locally: `python app.py`
3. Open another terminal and run:

```bash
ngrok http 5000
```

4. Copy the `https://xxxx.ngrok.io` link and share it.  
   (Link expires when you close ngrok)

---

## Recommendation

- Just testing with friends → use **ngrok**
- Want a permanent link for NOUN students → use **Render.com**
