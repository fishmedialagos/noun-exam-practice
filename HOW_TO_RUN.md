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
