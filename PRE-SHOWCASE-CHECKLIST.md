# Pre-Showcase Checklist ✅

Use this checklist before sharing your KnowLedge repo with judges, collaborators, or the world.

---

## 🔐 SECURITY CHECKS (Run These Commands)

- [ ] **No secrets in git history:**
  ```bash
  git log -p | grep -iE "api_key|password|secret|token" | wc -l
  # Should return: 0
  ```

- [ ] **No database files tracked:**
  ```bash
  git ls-files | grep -E "\.db|chroma_store|cdt_vectorstore"
  # Should return: (empty)
  ```

- [ ] **No .env files committed:**
  ```bash
  git log --all --name-status | grep "\.env" | wc -l
  # Should return: 0
  ```

- [ ] **No service account keys:**
  ```bash
  git ls-files | grep -E "\.key|invoker-key"
  # Should return: (empty)
  ```

---

## 📦 FILES TO REMOVE

- [ ] ❌ `US-Curriculum-Guide-2020-2021-UPDATED-061620.pdf`
  ```bash
  git rm US-Curriculum-Guide-2020-2021-UPDATED-061620.pdf
  git commit -m "Remove curriculum guide PDF from public repo"
  ```

- [ ] ⚠️ `TECHNICAL_PRESENTATION.html` (if not needed)
  ```bash
  # Option: Move to docs/
  git mv TECHNICAL_PRESENTATION.html docs/
  
  # OR: Remove entirely
  git rm TECHNICAL_PRESENTATION.html
  ```

---

## 📝 FILES TO ADD/CREATE

- [ ] Create `SECURITY.md` with:
  - What NOT to commit
  - How to handle credentials
  - Pre-deployment checklist

- [ ] Enhance `.env.example`:
  - Add header comment about not committing
  - Label sensitive vs. non-sensitive variables
  - Add explanation for each variable

- [ ] Update `README.md`:
  - Add link to SECURITY.md
  - Add note about demo vs. production mode
  - Clarify where credentials go

---

## ✅ WHAT SHOULD BE PUBLIC (Verify Present)

- [ ] `README.md` - Clear and professional
- [ ] `LICENSE` - Apache-2.0
- [ ] `requirements.txt` - Dependencies listed
- [ ] `.env.example` - Template (no real values)
- [ ] `knowledge/` source code - All Python files
- [ ] `knowledge-mobile/` - Mobile app code
- [ ] `hf_space/` - Hugging Face Space code
- [ ] `tests/` - Test files
- [ ] `cloud-run/` - Deployment scripts with placeholder IDs
- [ ] `docs/` or documentation files

---

## 🚀 DEPLOYMENT INFO TO VERIFY

- [ ] Project ID in `cloud-run/deploy-ollama.sh` is placeholder (`your-gcp-project-id`)
- [ ] `.env` is listed in `.gitignore`
- [ ] No real Render URLs or API endpoints in code
- [ ] No real Google Cloud project IDs visible
- [ ] Database location defaults to local path (not production)

---

## 🎯 FINAL CHECKS

- [ ] Run: `git status` - Should show clean working directory
- [ ] Run: `git log --oneline | head -5` - Recent commits look good
- [ ] Visit your GitHub repo page - Files look professional
- [ ] README displays correctly on GitHub
- [ ] No warnings from GitHub about exposed secrets
- [ ] Clone repo fresh and verify it works:
  ```bash
  cd /tmp
  git clone https://github.com/Charan-suresh/KnowLedge.git test-clone
  cd test-clone
  # Try to run basic commands to verify nothing's missing
  ```

---

## 📋 CLEANUP COMMANDS (Copy & Paste)

### Step 1: Remove PDF
```bash
git rm US-Curriculum-Guide-2020-2021-UPDATED-061620.pdf
git commit -m "Remove curriculum guide from public repo"
```

### Step 2: Handle HTML (Choose one)
```bash
# Option A: Move to docs
git mv TECHNICAL_PRESENTATION.html docs/

# Option B: Remove
git rm TECHNICAL_PRESENTATION.html

git commit -m "Organize presentation file"
```

### Step 3: Push changes
```bash
git push origin main
```

### Step 4: Verify
```bash
git ls-files | wc -l  # Check file count
git log -1 --name-status  # See what was removed
```

---

## ⚠️ IF YOU FIND SECRETS IN GIT HISTORY

**Do NOT ignore this!** Use BFG to clean history:

```bash
# Install BFG (if not already installed)
brew install bfg  # macOS
# or: apt-get install bfg  # Linux
# or: Download from https://rtyley.github.io/bfg-repo-cleaner/

# Remove all .env files from history
bfg --delete-files '.env' 

# Remove all .key files
bfg --delete-files '*.key'

# Force push
git reflog expire --expire=now --all && git gc --prune=now
git push --force-with-lease
```

---

## 🎉 YOU'RE READY WHEN:

✅ All checkboxes above are checked  
✅ `git status` shows clean  
✅ No `.env`, `.key`, or database files in repo  
✅ PDF and unnecessary HTML files removed  
✅ Security.md created with guidelines  
✅ Fresh clone works without errors  

---

## 📞 QUICK REFERENCE

**Common files to keep:**
- ✅ All `.py` files in knowledge/
- ✅ All `.tsx`/`.ts` files in knowledge-mobile/
- ✅ `requirements.txt`, `package.json`
- ✅ `.gitignore`, `.env.example`
- ✅ `README.md`, `LICENSE`

**Common files to remove:**
- ❌ `.env` (never should be committed)
- ❌ `*.db` (database files)
- ❌ `.key`, `*.pem` (keys)
- ❌ `chroma_store/` (local data)
- ❌ Copyrighted PDFs

---

Last updated: May 9, 2026
