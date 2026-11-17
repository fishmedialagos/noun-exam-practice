# How to Run NOUN Exam Mock Platform

## 1. Download the Project

Download the file: **noun_exam_platform.zip**

Extract it to any folder (e.g. Desktop or Documents).

---

## 2. Install Python (if you don't have it)

### Windows
1. Go to: https://www.python.org/downloads/
2. Download the latest Python 3
3. **Important**: During installation, tick ✅ **"Add Python to PATH"**
4. Click Install

### Mac
Python is usually already installed.  
If not, install from: https://www.python.org/downloads/

### Check if Python is installed
Open Terminal (Mac/Linux) or Command Prompt (Windows) and type:

```bash
python --version
```
or
```bash
python3 --version
```

You should see something like `Python 3.10` or higher.

---

## 3. Run the Platform

### Windows
1. Open the extracted folder (`noun_exam_platform`)
2. Hold **Shift** + Right-click inside the folder → **Open PowerShell window here**
3. Run these commands one by one:

```bash
pip install -r requirements.txt
python app.py
```

### Mac / Linux
1. Open Terminal
2. Go into the project folder:

```bash
cd Desktop/noun_exam_platform
```
(or wherever you extracted it)

3. Run:

```bash
pip3 install -r requirements.txt
python3 app.py
```

---

## 4. Open in Browser

After you see:

```
🚀 NOUN Exam Mock Platform is running!
   Open: http://127.0.0.1:5000
```

Open your browser and go to:

**http://127.0.0.1:5000**

---

## Default Login Accounts

| Role     | Username   | Password     |
|----------|------------|--------------|
| Admin    | admin      | admin123     |
| Teacher  | teacher1   | teacher123   |

Students should click **Register** on the website.

---

## Common Problems & Solutions

### "python is not recognized"
→ Python is not added to PATH. Reinstall Python and tick "Add to PATH".

### "pip is not recognized"
→ Try `python -m pip install -r requirements.txt`

### Port already in use
→ Change the last line in `app.py` from `port=5000` to `port=5001`, then open `http://127.0.0.1:5001`

### ModuleNotFoundError
→ Run `pip install -r requirements.txt` again.

---

## How to Stop the Server
Press `Ctrl + C` in the terminal.

## Configure AI Question Generation

The upgraded mock question generator needs an AI API key to create university-standard questions. Set **one** of these environment variables before starting the app:

**Windows PowerShell (current terminal only):**

```powershell
$env:GROQ_API_KEY="your_groq_api_key"
python app.py
```

Or use OpenAI instead:

```powershell
$env:OPENAI_API_KEY="your_openai_api_key"
python app.py
```

For a permanent/local setup, place the key in a `.env` file only if your deployment loads that file, and never upload the key to GitHub. The default models are `gpt-4o-mini` for OpenAI and `llama-3.3-70b-versatile` for Groq. OpenAI is selected first if both keys are present. Set `QUESTION_AI_PROVIDER=openai` to force OpenAI.

Without either key, the platform deliberately refuses to create a mock exam rather than generating weak questions. It also refuses to publish an exam unless the full target count passes validation (70 questions for courses of up to 2 credit units; 100 for courses above 2 units), with MCQ and fill-in questions balanced and interwoven.


### Recommended OpenAI setup (local testing)

1. Copy `.env.example` to `.env`.
2. Put your secret key after `OPENAI_API_KEY=`. Keep the key private.
3. Keep `QUESTION_AI_PROVIDER=openai` and `OPENAI_MODEL=gpt-4o-mini`.
4. Install dependencies: `pip install -r requirements.txt`.
5. Check API access: `python check_openai_api.py`.
6. If the check succeeds, start the platform: `python app.py`.

The API check reports whether the key and selected model work; it never prints the key. For Render, add the same variables under the service's Environment settings instead of uploading `.env`.
