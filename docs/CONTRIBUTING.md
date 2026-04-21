# Contributing — team workflow

Short version: **each person works on their own branch, opens a pull request,
and at least one other teammate reviews before merging to `main`**.
This keeps `main` always runnable.

## One-time setup

```bash
git clone <repo-url>
cd CS-Groupe-Project
python -m venv .venv
source .venv/bin/activate          # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
streamlit run app.py                # make sure the app starts before you change anything
```

## Day-to-day workflow

```bash
# 1. always start from an up-to-date main
git checkout main
git pull

# 2. make a branch named after what you're doing
git checkout -b feature/onboarding-form          # pattern: feature/<short-topic>
#   or: fix/meal-planner-crash, docs/readme-update

# 3. edit files — usually just YOUR page in pages/ + maybe your src/ module

# 4. test that the app still starts
streamlit run app.py

# 5. commit in small, descriptive chunks
git add <files>
git commit -m "Onboarding: add allergies multiselect"

# 6. push and open a pull request on GitHub
git push -u origin feature/onboarding-form
#   → open https://github.com/<your-repo>/pulls and click "New pull request"

# 7. ask a teammate to review, then Merge
```

## Branch naming

| Prefix      | When to use                           |
|-------------|---------------------------------------|
| `feature/`  | Any new functionality                 |
| `fix/`      | Bug fixes                             |
| `docs/`     | README, comments, contribution matrix |
| `refactor/` | Moving code around, no new behaviour  |

## Commit messages

Short, present-tense, in English. Prefix with the area so it's easy to scan:

```
Onboarding: save profile to DB
Recipes: handle empty API response
Planner: bar chart shows over-budget in red
Docs: update contribution matrix for week 9
```

## Merging to `main`

* `main` must **always** start with `streamlit run app.py` without errors.
* Before merging your PR, pull `main`, rebase (or merge) into your branch,
  re-run the app, then merge.
* Never force-push to `main`.

## Don't commit

* `.venv/` — in `.gitignore`
* `data/*.db` — generated locally, in `.gitignore`
* `.streamlit/secrets.toml` — API keys, in `.gitignore`
* Anything over ~10 MB — put it in a cloud storage link instead

## If there's a merge conflict

Because each person owns their own page file, conflicts should be rare. When
they happen they'll be in shared files (`src/data/database.py`,
`data/schema.sql`, `README.md`). Resolve them locally, re-run the app,
then push:

```bash
git pull --rebase origin main     # or: git merge origin/main
# open the conflicted file, pick/combine the right pieces
git add <file>
git rebase --continue             # or: git commit
git push
```

Ping the team in the group chat if you're unsure — better to ask than to
clobber someone's work.

## Contribution matrix

After every work session, open `docs/CONTRIBUTION_MATRIX.md` and add a row
for yourself. Requirement 7 of the grading rubric depends on this.
