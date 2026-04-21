# Team Guide — CookTogether (Group 12.04)

**Who this is for:** the 5 of us, tomorrow and every coding session after.
**Read time:** 10 minutes. Read it before your first commit.

---

## 1. What we have now, and why it helps us

We already have a **working Streamlit app** — it opens in the browser, has 7 pages, and runs without crashing. It's mostly placeholder content, but the *skeleton* is there and every piece is wired up. What this means:

- We don't waste the first two sessions arguing about folder structure — it's decided.
- Each of the 8 grading requirements already has a specific file where it will live. Nobody has to wonder "where do I put the database stuff?" — it's in `src/data/database.py`.
- Because each feature is in its own file, **5 people can work at the same time without overwriting each other's code.** This is the single biggest reason this setup matters.

In short: we go from "blank page, panic" to "pick your file, add your code".

---

## 2. How the app works — a 5-minute tour

Open the project folder. The key things you'll see:

- **`app.py`** — the home page. Only edit this if you want to change the welcome text.
- **`pages/`** — contains 7 files, one per feature. Streamlit automatically turns each file into a tab in the sidebar (that's why they're numbered). If you add a file here named `8_MyThing.py`, it becomes a new tab. Magic.
- **`src/`** — shared helper code that pages import. Think of it as our team toolbox: database functions, API functions, ML logic, UI components.
- **`data/schema.sql`** — the list of database tables. Edit this when you need new columns.
- **`docs/`** — this guide, the contribution matrix (graded!), the git workflow.
- **`requirements.txt`** — the list of Python libraries we use. If you install a new library, add it here.

### What happens when someone opens the app

1. They run `streamlit run app.py` in the terminal.
2. Streamlit opens a browser tab at `http://localhost:8501`.
3. `app.py` runs — it creates the database (if missing) and sets up the memory defaults.
4. They see the home page and the sidebar with 7 tabs.
5. They click a tab, say "Recipes". Streamlit runs `pages/2_Recipes.py` top to bottom.
6. Every click or form submit **re-runs that page's file top to bottom**. This is Streamlit's quirk. Anything you want to persist between clicks has to go into `st.session_state`.

That's it. The whole mental model.

---

## 3. Setting up your laptop (one-time, ~10 minutes)

Everyone does this once:

```
# 1. clone the repo
git clone https://github.com/alecfremond-wq/CS-Group-12.04.git
cd CS-Group-12.04

# 2. create a Python virtual environment (keeps our libraries isolated)
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
# .venv\Scripts\activate           # Windows PowerShell

# 3. install the libraries we use
pip install -r requirements.txt

# 4. try running the app
streamlit run app.py
```

If the browser opens and you see "🍳 CookTogether", you're set. Press Ctrl+C in the terminal to stop the app.

**Get a code editor** if you don't have one. [VS Code](https://code.visualstudio.com) is free and the easiest for beginners. Install the Python extension.

---

## 4. Your daily workflow (do this every time you code)

This is the loop. Do it in this order, every time:

```
# 1. make sure you have the latest from GitHub
git checkout main
git pull

# 2. create a branch for what you're working on
git checkout -b feature/onboarding-allergies
#   naming: feature/<short-topic>, fix/<bug>, docs/<change>

# 3. edit YOUR file in your editor, save

# 4. test that the app still starts
streamlit run app.py       # Ctrl+C to stop

# 5. commit your work
git add .
git commit -m "Onboarding: add allergies dropdown"

# 6. push the branch to GitHub
git push -u origin feature/onboarding-allergies

# 7. go to GitHub in the browser, open a Pull Request (PR)
#    https://github.com/alecfremond-wq/CS-Group-12.04/pulls
#    ask a teammate to review, then click Merge.

# 8. update the contribution matrix
#    (docs/CONTRIBUTION_MATRIX.md, add a line under "Session log")
```

The only scary word here is "Pull Request". It's just a button on GitHub that says "hey team, can someone check this and merge it to main?" — see the screenshot walkthrough in CONTRIBUTING.md.

---

## 5. Golden rules — DO / DON'T

### DO

- **Always create a branch before editing.** `git checkout -b feature/<thing>`. Never work on `main` directly.
- **Test locally before pushing.** Run `streamlit run app.py` and make sure it starts. If it crashes, don't push.
- **Write comments on every non-trivial line** (requirement 6 of the grading — this is worth real points).
- **Commit often, push when stable.** Small commits are easier to review.
- **Pull before starting new work** (`git pull`). Avoids painful merge conflicts.
- **Update `CONTRIBUTION_MATRIX.md` at the end of every session.** Requirement 7 depends on it. If you don't document it, it didn't happen.
- **Use English for variable names, comments, and commit messages.** The tutors grade in English.
- **Cite external code.** If you copy something from Stack Overflow, ChatGPT, a tutorial — put a `# Source: <url>` comment above it. HSG plagiarism rules (Tutorial 2, slide 19).

### DON'T

- **Don't push to `main` directly.** Always through a Pull Request.
- **Don't force-push** (`--force`) after the initial setup is done. It overwrites other people's work.
- **Don't commit `.venv/`, `__pycache__/`, `data/cooktogether.db`, or `.streamlit/secrets.toml`.** They're in `.gitignore` for a reason.
- **Don't commit API keys or passwords** in any file. If you need an API key, put it in `.streamlit/secrets.toml` (which is gitignored).
- **Don't delete or rename files you don't own** without telling the owner.
- **Don't copy large chunks of code from ChatGPT/AI without citing.** It's still plagiarism if uncredited (Tutorial 2, slide 20).
- **Don't fix merge conflicts blindly.** If you see a conflict, read both sides, or ask the other person in the group chat before deciding.
- **Don't break the app to make a point.** If `main` is broken, nobody on the team can work.

---

## 6. Who owns what (fill in names tomorrow)

Each person owns **one page file plus one shared module**. This gives everyone a clear, bounded piece of work.

| # | Person | Page file | Shared module |
|---|--------|-----------|---------------|
| TM1 | _______ | `pages/1_Onboarding.py` | `data/schema.sql` + `src/data/database.py` |
| TM2 | _______ | `pages/2_Recipes.py` + `pages/3_Pantry.py` | `src/data/api_client.py` |
| TM3 | _______ | `pages/4_Meal_Planner.py` | `src/components/ui.py` |
| TM4 | _______ | `pages/5_Nutrition_Analytics.py` + `pages/6_World_Map.py` | — |
| TM5 | _______ | `pages/7_Recommendations.py` | `src/models/recommender.py` |

Other responsibilities (project management, video editing, presentation slides) should be split separately — at least one person needs to own each.

---

## 7. How the 8 grading requirements map to our code

When your tutor grades us, they'll look for these 8 things. Here's where they live:

| # | Requirement                         | Where |
|---|-------------------------------------|-------|
| 1 | Problem clearly stated              | `README.md`, video |
| 2 | Data via API + database             | `src/data/api_client.py` + `src/data/database.py` + `data/schema.sql` |
| 3 | Data visualization                  | `pages/5_Nutrition_Analytics.py`, `pages/6_World_Map.py`, `pages/4_Meal_Planner.py` |
| 4 | User interactions                   | Every page — forms, buttons, dropdowns |
| 5 | Machine learning                    | `src/models/recommender.py` + `pages/7_Recommendations.py` |
| 6 | Code is well commented              | Every `.py` file — keep it up! |
| 7 | Contributions documented            | `docs/CONTRIBUTION_MATRIX.md` |
| 8 | 4-minute video demo                 | Recorded in week 11 |

---

## 8. When something goes wrong

**"The app won't start."** Check: did you activate the virtual environment? Did you `pip install -r requirements.txt`? Read the red error in terminal — it usually names the missing thing.

**"I have a merge conflict."** Don't panic. Open the conflicted file. Git marks the two versions with `<<<<<<< HEAD` and `>>>>>>>`. Keep the correct lines, delete the markers, save, `git add`, `git commit`.

**"I accidentally committed to main."** Tell the group chat immediately. We can unwind it together.

**"I pushed something secret (API key)."** Tell the group chat immediately. Rotate the key first, then we rewrite history.

**"I pulled and now my code is gone."** Git keeps everything. Run `git reflog` and call me / anyone more comfortable with git. Nothing is ever truly lost.

**"I broke `main`."** Revert: `git revert <bad-commit-hash>` creates a new commit that undoes the bad one. Push it. Don't force-push to "fix" it.

---

## 9. The contribution matrix — the most-forgotten deliverable

This is worth **up to 3 points out of your final grade** (requirement 7). Yet every group forgets it.

It lives at `docs/CONTRIBUTION_MATRIX.md`. There are two tables in it:

1. **Ownership overview** — who's the main contributor for each big area (page, module, documentation, video…). Fill this in at the first meeting.
2. **Session log** — one line per work session: `| 2026-04-22 | Alec | Added Onboarding form with allergies dropdown |`.

The rule: **every time you close your laptop after coding, add one line to the session log.** Takes 30 seconds. Saves 3 grade points.

---

## 10. Tomorrow's meeting — a suggested agenda

**0–20 min:** Everyone clones the repo, installs, and gets `streamlit run app.py` working. Nobody moves on until their laptop is green.

**20–40 min:** Tour the app together — click every sidebar tab, read the placeholder text, look at each page file in the editor. I explain the mental model from section 2 above.

**40–60 min:** Decide ownership. Fill in names in section 6 of this guide AND in `docs/CONTRIBUTION_MATRIX.md`. Commit + push.

**60–90 min:** Everyone creates their branch, makes a tiny change to their own page (e.g. change a title), opens a PR, merges it. This proves the workflow works for all 5 people before real work starts.

After this, you've de-risked the entire semester.

---

## 11. One-liner for each teammate

Send this in the group chat the night before:

> Tomorrow 15:00, we start coding. Bring your laptop with Python installed.
> Repo: https://github.com/alecfremond-wq/CS-Group-12.04
> Clone it tonight and run `pip install -r requirements.txt` + `streamlit run app.py`.
> If the browser opens showing "🍳 CookTogether", you're ready.
> Read `docs/TEAM_GUIDE.md` for 10 minutes before the meeting.

---

*This guide was drafted with help from an AI assistant (Anthropic Claude, 04/2026) and reviewed by Alec. See `README.md` for the full authorship note.*
