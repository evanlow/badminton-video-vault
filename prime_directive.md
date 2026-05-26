# Prime Directive: Development Guidelines

**Last Updated:** April 27, 2026  
**Purpose:** Ensure high-quality, maintainable code by learning from past experiences and establishing best practices for all team members, AI agents, and contributors.

**Scope:** This directive is designed for use across all software projects. Project-specific case studies and stack/tool profiles are explicitly labeled as optional examples.

---

## 📋 Quick Reference - Before Every Commit

```markdown
Pre-Commit Checklist:
□ Virtual environment active (Principle 0)
□ Every new/modified module has a smoke test file (Principle 1 — Coverage Rule)
□ Full regression suite passes: .\Scripts\python.exe tests/run_all_smoke.py — X/X passed, 0 failures (Principle 1) [run via run_in_terminal — never via execution_subagent (Principle 9)]
□ No secrets or credentials in the diff (Principle 12)
□ Change is on a feature branch, not directly on main (Principle 13)

For Backend-Only Changes:
□ Tests added/updated for new code
□ All tests pass
□ Any strange behavior investigated (Principle 8)
→ Ready to commit

For UI Changes (HTML/CSS/JavaScript):
□ Backend tests passing
□ Manual smoke test completed (Principle 5)
□ Browser console checked (F12) - 0 errors
□ Critical user flows tested
□ Input validation: Frontend (UX) + Backend (Security) (Principle 7)
□ Date/time inputs use proper controls (datetime-local or picker library)
□ Any strange behavior investigated (Principle 8)
□ Manual testing documented in commit message
□ No Python code with braces/f-strings passed via PowerShell -c (Principle 10)
□ Every new/modified API endpoint has a test (Principle 1 — Route Coverage Rule)
□ Every new mock enforces argument types with assert/isinstance (Principle 11)
□ At least one test for each "adopt/create/instantiate" flow uses the real class (Principle 11)
□ Any CDN integrity hash computed fresh from live URL — never copied from docs or memory (Principle 14)
→ Ready to commit

Session Log Cadence (Mandatory):
□ Append `session_log.md` at start, each test run, each major implementation cycle, and handoff (include KPI delta)

Commit Message Format:
  <type>: <description>
  
  <body with details>
  
  Backend Tests: X/X passed, 0 warnings [PASS]
  Smoke test files: smoke_auth, smoke_export, smoke_validators, smoke_mapper, smoke_excel_gen, ...
  New smoke tests added: <list exact filenames, or "none">
  Manual Testing: [PASS] (for UI changes only)
    - [What you tested]
    - [Results]

**Important:** Use ASCII characters only in commit messages (no Unicode/emoji).
  ✅ [PASS], [OK], [DONE], [FAIL]
  ❌ ✓, ✗, �	 (causes PowerShell encoding errors)
```

---

## 📊 Live Directive Compliance KPI (Session-Level)

Use a live compliance score throughout every working session to make adherence observable and auditable in real time.

### KPI Score Model

**Score format:** `X/8 green`

- **Green** = Requirement satisfied and evidenced in this session
- **Yellow** = Not yet applicable or pending the relevant step
- **Red** = Violated; must be flagged and corrected before continuing

### Required KPI Checklist (Track Live)

1. **Track directive compliance live**
2. **Verify venv before Python actions** (Principle 0)
3. **Confirm baseline tests pass clean** (Principle 1)
4. **Require post-change tests clean** (Principle 1)
5. **Enforce UI manual smoke checks** for UI changes (Principle 5)
6. **Validate input handling: Frontend (UX) + Backend (Security)** for form inputs (Principle 7)
7. **Investigate anomalies, don't work around them** (Principle 8)
8. **Record compliance status in updates**

### Session Reporting Protocol

- Report the KPI score in progress updates and handoffs
- Update checklist state immediately after each meaningful action
- If any item turns **Red**, stop new implementation work, fix the issue, then resume
- If an item is **Yellow**, state what trigger/action will move it to **Green**

### Checkpoint Cadence Rule (Mandatory)

Append an entry to `session_log.md` at the following minimum cadence:

1. **Session Start** - before implementation begins
2. **Environment/Test Gate** - after venv verification and baseline test run
3. **Each Major Implementation Cycle** - after meaningful code changes and their verification
4. **Every Test Execution** - when running targeted tests or full suite tests
5. **Any State Change to Red** - immediately when a violation is detected, plus correction outcome
6. **Session Handoff/Close** - final status and next steps

**Checkpoint metadata required per entry:**
- Checkpoint type (start, test, implementation, risk, handoff)
- Trigger event (what caused this entry)
- KPI delta (what changed since prior entry)

**Guideline:** prefer more frequent short entries over infrequent large summaries.

### Session Log File Requirement (Per Project)

Every project must maintain a dedicated session log file at repository root:

- **Required file:** `session_log.md`
- **Created when:** project initialization (or first work session if missing)
- **Updated when:** at session start, after major checkpoints, and at handoff/close

**Minimum entry fields:**

1. Date and session identifier
2. Directive Compliance KPI score (`X/8 green`)
3. Green/Yellow/Red breakdown with reasons
4. Checkpoint type and trigger event
5. KPI delta since previous entry
6. Actions completed since last entry
7. Risks, blockers, or corrective actions
8. Next planned steps

**Bootstrap instructions for new projects:**

1. Create `session_log.md` at repo root
2. Add a reusable entry template with KPI checklist fields
3. Add first baseline entry before implementation begins
4. Continue appending entries chronologically (newest at bottom)

**Rule:** if a session performs work and `session_log.md` is not updated, session compliance is incomplete.

### Example Status Update

```markdown
Directive Compliance KPI: 6/8 green
- Green: #1, #2, #3, #5, #7, #8
- Yellow: #4 (awaiting post-change test run), #6 (no form input changes yet)
- Red: none
```

---

## 🎯 Core Principles

### 0. **Virtual Environment Verification - ALWAYS FIRST**
**CRITICAL:** Before ANY pip install, pytest, or Python execution, VERIFY you are in the virtual environment.

**The Protocol:**
1. ✅ **Check Python path** - run `python -c "import sys; print(sys.executable)"`
2. ✅ **Verify it points to project venv** - path should contain `\<project-folder>\Scripts\python.exe`
3. ❌ **If using global Python** - path will be `C:\Users\...\AppData\Local\Programs\Python\...`
4. ✅ **Activate venv if needed** - run `.\Scripts\Activate.ps1` (Windows) or `source Scripts/activate` (Unix) **AS A SEPARATE COMMAND**
5. ✅ **Re-verify after activation** - check Python path again to confirm activation worked

**IMPORTANT - Activation Must Be Separate:**
```powershell
# ❌ WRONG - Chaining activation with other commands doesn't work
.\Scripts\Activate.ps1; python -c "..."  # Activation doesn't persist!

# ✅ CORRECT - Run activation first, then run subsequent commands separately
# Command 1: Activate
.\Scripts\Activate.ps1

# Command 2: Verify (in next command)
python -c "import sys; print(sys.executable)"

# Command 3: Now run your work (in next command)
pip install -r requirements.txt
```

**Why Separate Commands?**
- PowerShell activation scripts modify the current session environment
- Chaining with semicolons creates sub-shells that don't persist environment changes
- Each terminal command invocation is a fresh session unless activation is explicit

**CRITICAL - DO NOT CREATE NEW VENV WHEN ONE EXISTS:**
```powershell
# ❌ NEVER - Do not create new venv if project already has one
# Check for existing venv indicators FIRST:
# - Scripts/ directory exists
# - Lib/ directory exists  
# - Include/ directory exists
# - pyvenv.cfg file exists
# If these exist at project root, the venv is already set up!

# ❌ WRONG - Creating new venv when one exists
python -m venv .venv  # Creates duplicate venv!
configure_python_environment  # Tool that creates new venv!

# ✅ CORRECT - Use existing venv
.\Scripts\Activate.ps1  # Just activate what exists
pip install <missing-package>  # Install missing dependencies
```

**Detecting Existing Virtual Environment:**
1. Check if `Scripts/`, `Lib/`, `Include/`, `pyvenv.cfg` exist at project root
2. If YES → venv exists, just activate it with `.\Scripts\Activate.ps1`
3. If NO → venv doesn't exist, safe to create one
4. **Common mistake:** Seeing "ModuleNotFoundError" and creating new venv
   - **Correct response:** Install missing package: `pip install <package>`
   - **Wrong response:** Create new venv with configure_python_environment

**Why This Matters:**
- Creating duplicate venv wastes disk space (hundreds of MB)
- Creates confusion about which venv to use
- May have different package versions than existing venv
- Tests may pass in one venv but fail in another
- **Never use configure_python_environment or python -m venv if venv structure exists**

**Background Tasks and Virtual Environments:**
```powershell
# ❌ WRONG - Background tasks start NEW sessions without venv
python -m streamlit run app.py  # If run as background, uses global Python!

# ✅ CORRECT - Use Scripts executables directly for background tasks
.\Scripts\streamlit.exe run app.py  # Works without activation!
.\Scripts\python.exe -m pytest test_file.py  # Explicit venv Python

# ✅ ALSO CORRECT - Activate first, then run in foreground/same session
.\Scripts\Activate.ps1  # Command 1
python -m streamlit run app.py  # Command 2 in same session
```

**Key Insight - Scripts Executables:**
- When packages install in venv, they create executables in `.\Scripts\` directory
- These executables (`.exe`, `.cmd`) know their Python environment path automatically
- Using `.\Scripts\executable.exe` works from ANY session (activated or not)
- Examples: `streamlit.exe`, `pytest.exe`, `python.exe`, `pip.exe`
- **Benefit:** No activation needed when using direct paths to Scripts executables

**When to Use Each Method:**

| Scenario | Method | Example |
|----------|--------|---------|
| **Venv already exists (Scripts/, Lib/, etc.)** | **Activate existing venv** | **`.\Scripts\Activate.ps1` → never create new one** |
| **Missing package error** | **Install package** | **`pip install <package>` → don't create new venv** |
| Background task (server, watch mode) | Direct Scripts path | `.\Scripts\streamlit.exe run app.py` |
| Quick one-off command | Direct Scripts path | `.\Scripts\python.exe -m pytest` |
| Multiple sequential commands | Activate once, then run | Activate → run command 1 → run command 2 |
| Interactive work session | Activate once | Activate → work with `python`, `pip`, etc. |

**❌ NEVER:**
- Run `pip install` without checking Python path first
- Assume the environment is active because it "should be"
- Install packages into global Python (pollutes base environment)
- Run tests or code with global Python when venv exists
- Chain activation with other commands using semicolons (`;`)
- Run background tasks assuming they inherit venv activation
- Try to install packages when tests already passed (indicates packages exist!)
- Create new virtual environment (`.venv`, `venv`, etc.) when Scripts/Lib/Include/pyvenv.cfg already exist
- Use `configure_python_environment` tool when venv structure already exists at project root
- Use `python -m venv` command when virtual environment is already set up

**✅ ALWAYS:**
- **Check for existing venv FIRST** (Scripts/, Lib/, Include/, pyvenv.cfg in project root)
- If venv exists → activate it, don't create a new one
- If missing package → `pip install <package>`, don't create new venv
- Run activation as a standalone command first (if not using Scripts paths)
- Verify Python executable path AFTER activation in a new command
- Use `.\Scripts\executable.exe` for background tasks or when activation is unclear
- Check for venv indicators: `(venv)` or your project-name prompt prefix
- Verify packages exist before attempting installation (check `pip list` or test results)
- Document which environment was used if reporting issues

**Recovery from Global Install:**
```powershell
# Uninstall from global Python
python -m pip uninstall package1 package2 -y

# Activate venv
.\Scripts\Activate.ps1

# Verify venv is active
python -c "import sys; print(sys.executable)"  # Should show ...\<project-folder>\Scripts\python.exe

# Install to venv
pip install -r requirements.txt
```

### 1. **100% Test Pass Rate + Zero Warnings - Non-Negotiable**
All tests must pass AND produce zero warnings before AND after ANY code changes. No exceptions.

**MANDATORY: Tests Must Exist Before Code Changes**
- ❌ **Never make code changes without test coverage**
- ✅ **Write tests FIRST for new features (TDD)**
- ✅ **Add tests IMMEDIATELY when fixing bugs**
- ✅ **Create test file alongside new modules**
- ❌ **Never commit untested code** - tests prevent regressions

**MODULE → SMOKE TEST HARD RULE:**
Every new Python module under `app/routes/` or `app/services/` MUST have a corresponding `tests/smoke_<module>.py` file created in the **same commit**. A new module with no smoke test file is treated as a failed commit — equivalent to failing tests.

**Test file naming convention (enforced):**

| New module | Required test file |
|---|---|
| `app/routes/auth.py` | `tests/smoke_auth.py` |
| `app/routes/export.py` | `tests/smoke_export.py` |
| `app/services/validators.py` | `tests/smoke_validators.py` |
| `app/services/mapper.py` | `tests/smoke_mapper.py` |
| `app/routes/<name>.py` | `tests/smoke_<name>.py` |
| `app/services/<name>.py` | `tests/smoke_<name>.py` |

**Regression Suite Runner (Mandatory):**
```powershell
# Run all smoke tests in one command — use before EVERY commit
.\Scripts\python.exe tests/run_all_smoke.py
```
This script auto-discovers every `tests/smoke_*.py` file, runs them, and prints a consolidated
pass/fail count. It exits with code 1 on any failure, making it CI/CD-compatible.
The count reported here is the authoritative number for the commit message.

**IMPORTANT — How to run this (Principle 9):**
Always use `run_in_terminal` directly. Never delegate this command to `execution_subagent`.
Never redirect output to an assumed absolute path (e.g., `C:\Temp`) — the directory may not exist.

**The Protocol:**
1. ✅ Verify baseline - run full test suite BEFORE any changes (zero failures, zero warnings)
2. 🔄 Make changes (one logical step at a time)
3. ✅ **Run tests IMMEDIATELY** after changes (zero failures, zero warnings)
4. ❌ If tests fail OR warnings appear - fix immediately or revert
5. ✅ **Backend tests pass = Server logic correct** (necessary but not sufficient for UI changes)
6. ✅ **For UI changes: Add manual testing** (see Principle 5)
7. ✅ Only commit when tests pass + manual verification complete (if UI changed)

**Test Coverage Requirements:**
- **Backend routes:** Test all HTTP endpoints (GET, POST, error cases)
- **Business logic:** Test all functions with edge cases (empty, None, boundary values)
- **Integration:** Test complete workflows end-to-end
- **Error handling:** Test invalid inputs return proper errors
- **Minimum coverage:** 70%+ for new features, 90%+ for critical paths

**Route Coverage Rule (Non-Negotiable):**
Every new or modified API endpoint **must** have corresponding tests committed in the **same** change.

| Required test | What it covers |
|---|---|
| Happy path → 200 + correct response shape | Confirms endpoint is reachable and returns expected data |
| Missing required fields → 400 | Confirms input validation is enforced |
| Unknown/invalid values → 400/404 | Confirms error handling is correct |
| "Adopt / Create / Instantiate" flow → uses **real** domain class | Catches constructor-level crashes; `Mock()` cannot substitute here |

**Adopt-flow test rule:**
Any endpoint that internally calls `__init__` on a domain object (e.g., `POST /api/strategies/create`) must have at least one integration test that instantiates the **real** class — not a `Mock()`. Only real instantiation will catch attribute errors, missing imports, or wrong event-bus API calls at test time.

**Warning Policy:**
- Warnings are NOT acceptable - they must be investigated and resolved
- Every warning indicates a potential issue (deprecations, type mismatches, anti-patterns)
- "Just warnings" become breaking errors in future versions
- Warnings create technical debt and mask real issues
- Zero tolerance for warnings = clean, maintainable codebase

**❌ Never:**
- Skip baseline verification
- Ignore or dismiss warnings as "not important"
- Make multiple unrelated changes at once
- Commit with failing tests OR warnings
- Defer fixing test failures or warnings
- Delete code without verifying impact

**✅ Always:**
- Run tests before starting work (establish baseline: X passed, 0 warnings)
- Run tests after each logical change
- Maintain 100% pass rate AND zero warnings throughout
- Investigate every warning immediately when it appears
- Fix warnings before proceeding with new work
- Document test count AND warning count in commits (e.g., "393 passed, 0 warnings")
- Preserve git history when removing code

### 2. **Verify First, Code Second**  
Never assume how existing code works. Always verify before implementing.

**❌ Don't:**
```python
# Assuming without checking
timeframe=TimeFrame.DAILY  # Does DAILY exist?
def on_bar(self, symbol, bar):  # Is this the right signature?
```

**✅ Do:**
```python
# Step 1: Check existing code
# grep_search(query="class TimeFrame", includePattern="data_models.py")
# read_file to see: DAY_1, HOUR_1, MINUTE_1

# Step 2: Use correct values
timeframe=TimeFrame.DAY_1
def on_bar(self, market_data):  # Matches base class signature
```

### 3. **Defensive Programming Always**  
Assume nothing. Handle None, validate inputs, check bounds.

**❌ Don't:**
```python
position = self.get_position(symbol)
if position <= 0:  # Crashes if None!
    ...
```

**✅ Do:**
```python
position = self.get_position(symbol) or 0  # Default to 0
if position <= 0:
    ...

# Or more explicit:
position = self.get_position(symbol)
if position is None:
    position = 0
```

### 4. **Test Incrementally, Not All At Once**  
Build and verify in small steps. Don't write 300 lines before testing.

**✅ Development Flow:**
```python
# Step 1: Test component in isolation
data_manager = HistoricalDataManager(data_dir)
data_manager.load_csv(...)
print(f"✓ Loaded {len(bars)} bars")  # Verify!

# Step 2: Test next component
strategy = MyStrategy(config)
strategy.on_start()  # Does it initialize?

# Step 3: Test integration
result = engine.run()  # Now combine them
```

### 5. **Frontend/UI Testing - The Backend Test Blind Spot**
**CRITICAL:** Backend tests (pytest, unittest) **CANNOT** catch frontend bugs. Know the gap.

**The Reality Check:**
- ✅ Backend tests verify: routes work, logic correct, data flows properly
- ❌ Backend tests **MISS**: JavaScript bugs, form behavior, UI interactions, browser rendering
- 🎯 **100% backend test pass ≠ working application from user perspective**

**What Backend Tests Don't Catch:**
1. **JavaScript Errors**
   - Form fields being cleared by JS
   - Event handlers not firing
   - Tab switching breaking functionality
   - Client-side validation issues
   - **CRITICAL: Syntax errors that break ALL JavaScript** (missing braces, semicolons)

2. **HTML Form Behavior**
   - Disabled fields don't submit their values (HTML spec behavior)
   - Form validation preventing submission
   - Field names not matching server expectations
   - Empty file inputs always present in request.files

3. **Browser-Specific Issues**
   - CSS breaking layout
   - Forms not submitting
   - AJAX requests failing
   - Event listeners not attaching

4. **User Flow Problems**
   - Confusing UX (buttons that don't work as expected)
   - Missing feedback (no loading indicators)
   - Error messages not displayed
   - Navigation breaks

**⚠️ SPECIAL DANGER: JavaScript Syntax Errors**
JavaScript syntax errors are **silent killers** that make debugging extremely difficult:

```javascript
// Bug example: Missing closing brace
if (inputForm) {
    inputForm.addEventListener('submit', function(e) {
        // ... lots of code ...
        return true;
    });
// ❌ MISSING } for if statement!
</script>

// Result:
// - Browser shows: "Uncaught SyntaxError: Unexpected end of input"
// - ALL JavaScript after the error: DOESN'T RUN
// - Event handlers: NEVER REGISTERED
// - Console logs: NEVER APPEAR
// - Form: Falls back to plain HTML submission (no validation, no logging)
// - From user perspective: Form "doesn't work" with no clear error
```

**Why Syntax Errors Are Devastating:**
1. **Silent failure** - JavaScript stops executing, no obvious error to user
2. **All subsequent code disabled** - entire script block becomes useless
3. **Event handlers don't register** - buttons appear functional but don't work
4. **No logging output** - can't debug with console.log if code never runs
5. **Backend tests still pass** - they don't load JavaScript at all

**How to Catch JavaScript Syntax Errors:**
1. **Open browser console (F12)** before any manual test
2. **Look for red error messages** - "SyntaxError" is your clue  
3. **Check line numbers** - browser tells you exactly where the error is
4. **Fix syntax, hard refresh** - Ctrl+Shift+R to clear cached JavaScript
5. **Re-test** - verify error gone and functionality works

**⚠️ SPECIAL DANGER: Compounding Bugs (Multiple Bugs Masking Each Other)**
When multiple bugs exist simultaneously, they can hide each other:

**Example Cascade:**
```
Bug #1: Disabled form fields (don't submit values)
         ↓
Prevents testing → Bug #2: JavaScript syntax error (code doesn't run)
         ↓  
Can't reach server → Bug #3: if/elif logic bug (wrong branch executes)
         ↓
Each bug hides the next → Appears as single issue to user
```

**Debugging Compounding Bugs - Systematic Approach:**
1. **Start at the beginning** - browser loads page (console errors?)
2. **Check each layer in order:**
   - Browser console → any errors?
   - JavaScript logs → are they appearing?
   - Network tab → is request being sent?
   - Server logs → is request received?
   - Server processing → what's the data?
3. **Fix ONE bug at a time**
4. **Re-test after EACH fix** - don't assume you found "the" bug
5. **Repeat until workflow succeeds end-to-end**

**Cost of Compounding Bugs:**
- Single bug alone: 5-10 min to find
- Two bugs together: 15-30 min (each hides symptoms of the other)
- Three bugs together: 45+ min (exponential debugging difficulty)
- **Prevention: Manual testing catches ALL of them in 2 minutes**

**The Protocol - Web Applications:**

**After ANY UI Change (HTML/CSS/JavaScript):**
1. ✅ **Run backend tests** - ensure server-side still works (100% pass required)
2. ✅ **Manual smoke test** - actually use the application (MANDATORY)
3. ✅ **Check browser console** - no JavaScript errors (F12 DevTools)
4. ✅ **Test critical user flows** - can users complete key tasks?
5. ✅ **Verify on refresh** - state persists, no unexpected resets

**Manual Testing Checklist** (Required for UI changes):
```markdown
Critical User Flows (Test EVERY TIME):
- [ ] Submit form with valid data → reaches next page
- [ ] Submit form with invalid data → shows errors
- [ ] Navigate between pages → no data loss  
- [ ] Refresh page mid-workflow → state preserved (or reasonable fallback)
- [ ] Click all primary buttons → expected actions occur
- [ ] Check browser console (F12) → zero errors
- [ ] Mobile/responsive view → usable on small screens (if applicable)
```

**When to Add Browser-Based E2E Tests:**
Consider Selenium/Playwright if:
- Application has complex JS interactions (SPAs, real-time updates)
- UI bugs cause frequent customer escalations
- Team size > 3 developers making concurrent UI changes
- Application is customer-facing (not internal tool)

**Trade-offs:**
- **Backend tests:** Fast (seconds), reliable, catch logic bugs -  **miss UI bugs**
- **Manual testing:** Fast (minutes), catches UI bugs - **not automated, can be forgotten**
- **E2E browser tests:** Catch UI bugs, automated - **slow (minutes), brittle, maintenance overhead**

**For Small Projects/Internal Tools:**
- Prioritize: Backend tests (automated) + Manual checklist (discipline)
- Skip: E2E browser automation (too much overhead)
- Reason: Manual testing 5 critical flows takes 2-5 minutes vs hours maintaining E2E tests

**Red Flags That Indicate Missing Manual Testing:**
- ❌ "All 138 tests pass" but users report basic features broken
- ❌ Form submissions fail but tests don't catch it
- ❌ JavaScript console full of errors
- ❌ UI changes deployed without anyone actually clicking buttons

**❌ Never:**
- Deploy UI changes without manual smoke test
- Assume backend tests caught all issues
- Skip browser console error check
- Trust "it works on my machine" without verification

**✅ Always:**
- Manually test every UI change before commit
- Check browser console (F12) for errors
- Test critical user flows end-to-end
- Document UI testing in commit message ("Tested: form submission, navigation, refresh")
- Have second person spot-check if possible

### 6. **User-Facing Output Quality - No Truncated Business Content**
**CRITICAL:** Do not ship user-facing documents with truncated sentences (e.g., "...") unless explicitly labeled as a preview.

**Why this matters:**
- Business minutes are circulated as authoritative records
- Truncated content undermines clarity, professionalism, and legal/audit value
- "Looks fine" in UI can still be wrong in exported output

**✅ Always:**
- Ensure exported/printable user-facing text includes full sentences
- If compact tables are used, wrap lines instead of truncating
- Only use ellipses in explicit previews, never in final export content

**Manual Output Check (Required when rendering changes):**
- Verify final exported text and PDF contain complete action items
- Confirm no ellipses appear in the final output (unless explicitly intended)

**Cost of Skipping Manual UI Testing:**
- 2 minutes saved = hours debugging production issues
- "100% test pass" gives false confidence
- Users discover bugs = credibility damage
- Regression bugs = wasted time

**Example Commit Message (Good):**
```
Fix word counter validation logic

- Changed minimum from 50 to 10 words
- Updated UI messaging to show "recommended" vs "required"
- Updated core/parser.py validation
- Updated tests/test_parser.py expectations

Backend Tests: 138/138 passed, 0 warnings ✓
Manual Testing: ✓
  - Submitted 10-word transcript → accepted
  - Submitted 5-word transcript → rejected with error
  - Word counter updates in real-time
  - Browser console: 0 errors
```

### 7. **Enterprise Input Validation & Security Standards**
**CRITICAL:** Never trust frontend validation alone. Always validate and sanitize on the backend.

**The Golden Rules:**
1. **Frontend validation = UX convenience** (instant feedback, prevent network calls)
2. **Backend validation = Security boundary** (enforceable, cannot be bypassed)
3. **Both are required** - frontend for UX, backend for security

---

#### **Date/Time Input Standards**

**❌ NEVER: Plain text fields for time without backend normalization**
```html
<!-- BAD: Relies on user typing correct format -->
<input type="text" name="start_time" placeholder="Enter time">
```

**❌ NEVER: HTML5 time input without backend conversion**
```html
<!-- BAD: Browser sends HH:MM but no timezone info -->
<input type="time" name="start_time">
<!-- Backend receives: "09:30" - but in what timezone? -->
```

**✅ ALWAYS: Use proper datetime controls with timezone handling**

**Option 1: Modern JavaScript DateTime Picker (Recommended for Enterprise)**
```html
<!-- Use libraries that handle timezones properly -->
<!-- Flatpickr, React DatePicker, MUI DateTimePicker, etc. -->
<input id="meeting-time" type="text">
<script>
flatpickr("#meeting-time", {
    enableTime: true,
    dateFormat: "Y-m-d H:i",
    time_24hr: true
});
</script>
```

**Option 2: HTML5 datetime-local (Acceptable for Internal Tools)**
```html
<!-- datetime-local includes date + time, no timezone -->
<input type="datetime-local" name="meeting_time">
<!-- Browser sends: "2026-02-23T09:30" -->
```

**Backend Processing (MANDATORY for all datetime inputs):**
```python
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+

# ✅ GOOD: Convert to UTC, store as ISO 8601
def process_meeting_time(user_input: str, user_timezone: str = "UTC") -> str:
    """
    Convert user's local datetime to UTC ISO 8601 format.
    
    Args:
        user_input: "2026-02-23T09:30" or "2026-02-23 09:30"
        user_timezone: "Asia/Singapore", "America/New_York", etc.
    
    Returns:
        ISO 8601 UTC string: "2026-02-23T01:30:00Z"
    """
    # Parse input (handle multiple formats)
    dt_naive = datetime.fromisoformat(user_input.replace(' ', 'T'))
    
    # Attach user's timezone
    dt_aware = dt_naive.replace(tzinfo=ZoneInfo(user_timezone))
    
    # Convert to UTC
    dt_utc = dt_aware.astimezone(ZoneInfo("UTC"))
    
    # Store as ISO 8601
    return dt_utc.isoformat()

# Example:
# User in Singapore enters: "2026-02-23T09:30"
# Backend stores: "2026-02-23T01:30:00Z" (UTC)
# Display to user: "2026-02-23T09:30:00+08:00" (Singapore time)
```

**Database Storage Standards:**
```sql
-- ✅ ALWAYS: Store datetimes in UTC
CREATE TABLE meetings (
    id SERIAL PRIMARY KEY,
    meeting_time TIMESTAMP WITH TIME ZONE NOT NULL,  -- PostgreSQL
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ❌ NEVER: Store as local time without timezone
CREATE TABLE meetings (
    meeting_time TIMESTAMP,  -- Ambiguous! What timezone?
    created_at DATETIME      -- SQLite/MySQL - no timezone info
);
```

**Display to Users (Convert back to local time):**
```python
def display_meeting_time(utc_iso_string: str, user_timezone: str) -> str:
    """
    Convert stored UTC time back to user's local timezone.
    
    Args:
        utc_iso_string: "2026-02-23T01:30:00Z"
        user_timezone: "Asia/Singapore"
    
    Returns:
        "2026-02-23 09:30 SGT"
    """
    dt_utc = datetime.fromisoformat(utc_iso_string.replace('Z', '+00:00'))
    dt_local = dt_utc.astimezone(ZoneInfo(user_timezone))
    return dt_local.strftime("%Y-%m-%d %H:%M %Z")
```

**Time Input Validation Rules:**
1. **Frontend:** Provide picker UI (date + time together)
2. **Backend:** Parse, validate, convert to UTC ISO 8601
3. **Storage:** Always UTC with timezone marker (`TIMESTAMP WITH TIME ZONE`)
4. **Display:** Convert from UTC to user's timezone

**Acceptable Shortcuts for Internal/Small Tools:**
- Use `datetime-local` input (not `time` alone)
- Assume single timezone (e.g., company HQ timezone)
- Store as ISO 8601 string: `YYYY-MM-DDTHH:MM:SS`
- Document timezone assumption clearly

**❌ NEVER Acceptable (Even for Internal Tools):**
- Plain text `<input type="text">` for time without backend normalization
- `<input type="time">` without date - time is meaningless without date
- Storing time as "09:30" string - ambiguous format, no date context
- Mixing 12-hour/24-hour formats without clear indicators

---

#### **General Input Validation Standards**

**The Three-Layer Defense:**
```
Layer 1: Frontend (HTML5 + JavaScript)
         ↓ (Can be bypassed - user can modify DOM/disable JS)
Layer 2: Backend Validation (Python/Node/etc)
         ↓ (Enforceable - server controls this)
Layer 3: Database Constraints
         ↓ (Last line of defense)
```

**HTML5 Client-Side Validation (UX Layer):**
```html
<!-- ✅ GOOD: Provides instant feedback -->
<input 
    type="email" 
    name="email" 
    required 
    pattern="[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$"
    title="Enter a valid email address"
>

<input 
    type="number" 
    name="age" 
    min="0" 
    max="120" 
    required
>

<!-- Date input with min/max constraints -->
<input 
    type="date" 
    name="meeting_date" 
    min="2026-01-01" 
    max="2026-12-31"
    required
>
```

**Backend Validation (Security Layer - REQUIRED):**
```python
from pydantic import BaseModel, Field, field_validator, EmailStr
from datetime import datetime, date
from typing import Optional

class MeetingInput(BaseModel):
    """Backend validation model - never trust frontend alone"""
    
    email: EmailStr  # Validates email format
    age: int = Field(ge=0, le=120)  # Greater/equal 0, less/equal 120
    meeting_date: date = Field(...)
    meeting_time: datetime = Field(...)
    description: str = Field(min_length=1, max_length=500)
    
    @field_validator('meeting_date')
    @classmethod
    def validate_date_not_past(cls, v: date) -> date:
        """Meetings must be in the future"""
        if v < date.today():
            raise ValueError("Meeting date cannot be in the past")
        return v
    
    @field_validator('description')
    @classmethod
    def sanitize_description(cls, v: str) -> str:
        """Sanitize to prevent XSS"""
        # Strip dangerous characters/tags
        import html
        return html.escape(v.strip())

# Usage in Flask/FastAPI route:
@app.post("/create-meeting")
def create_meeting(data: MeetingInput):
    # If we reach here, data is validated
    # Pydantic raises 422 Unprocessable Entity if validation fails
    return {"status": "success", "meeting": data.model_dump()}
```

**Database Constraints (Last Defense):**
```sql
-- PostgreSQL example
CREATE TABLE meetings (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    age INT CHECK (age >= 0 AND age <= 120),
    meeting_date DATE NOT NULL CHECK (meeting_date >= CURRENT_DATE),
    description TEXT NOT NULL CHECK (LENGTH(description) > 0 AND LENGTH(description) <= 500)
);
```

---

#### **Input Sanitization Standards**

**XSS Prevention (Cross-Site Scripting):**
```python
import html
from markupsafe import escape  # If using Flask/Jinja2

# ✅ ALWAYS: Escape user input before displaying in HTML
user_input = "<script>alert('XSS')</script>"
safe_output = html.escape(user_input)
# Result: "&lt;script&gt;alert('XSS')&lt;/script&gt;"

# In templates (Jinja2/Flask auto-escapes by default)
{{ user_input }}  # ✅ Auto-escaped
{{ user_input | safe }}  # ❌ DANGEROUS - bypasses escaping
```

**SQL Injection Prevention:**
```python
# ❌ NEVER: String concatenation
cursor.execute(f"SELECT * FROM users WHERE email = '{user_email}'")

# ✅ ALWAYS: Parameterized queries
cursor.execute("SELECT * FROM users WHERE email = %s", (user_email,))

# ✅ ALWAYS: Use ORM (SQLAlchemy, Django ORM)
User.query.filter_by(email=user_email).first()  # Auto-escaped
```

**File Upload Validation:**
```python
from werkzeug.utils import secure_filename
import os

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def validate_file_upload(file):
    """Validate uploaded file"""
    # Check if file exists
    if not file or file.filename == '':
        raise ValueError("No file provided")
    
    # Secure the filename (remove path traversal attempts)
    filename = secure_filename(file.filename)
    
    # Check extension
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type .{ext} not allowed")
    
    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)  # Reset file pointer
    if size > MAX_FILE_SIZE:
        raise ValueError("File too large (max 10MB)")
    
    return filename
```

---

#### **Enterprise DateTime Best Practices Summary**

**For Production/Enterprise Systems:**
1. ✅ Use modern datetime picker libraries (Flatpickr, MUI, etc.)
2. ✅ Capture user's timezone (from browser or profile)
3. ✅ Convert all times to UTC before storage
4. ✅ Store as ISO 8601 with timezone: `2026-02-23T01:30:00Z`
5. ✅ Use `TIMESTAMP WITH TIME ZONE` in database
6. ✅ Convert back to user's timezone when displaying
7. ✅ Handle daylight saving time transitions

**For Internal Tools (Acceptable Shortcuts):**
1. ✅ Use `<input type="datetime-local">` (includes date + time)
2. ✅ Document assumed timezone clearly (e.g., "All times in UTC")
3. ✅ Store as ISO 8601: `YYYY-MM-DDTHH:MM:SS`
4. ⚠️ Validate format on backend even if frontend provides picker

**❌ NEVER Acceptable:**
1. ❌ `<input type="time">` alone without date
2. ❌ Plain `<input type="text">` for time without backend normalization
3. ❌ Storing times without date context (e.g., "09:30" string)
4. ❌ Trusting frontend validation alone
5. ❌ Storing times without timezone information

---

#### **Validation Checklist (Required for ALL form inputs)**

**Frontend (UX Layer):**
- [ ] Use appropriate HTML5 input types (`email`, `number`, `date`, `datetime-local`)
- [ ] Add `required`, `min`, `max`, `pattern` attributes where applicable
- [ ] Provide clear error messages with `title` attribute
- [ ] Use datetime pickers for date/time inputs (not plain text)
- [ ] JavaScript validation for complex rules (matching passwords, etc.)

**Backend (Security Layer - MANDATORY):**
- [ ] Use Pydantic/Marshmallow/dataclasses for validation models
- [ ] Validate data types (int, str, email, date, etc.)
- [ ] Validate ranges (min/max length, min/max value)
- [ ] Validate formats (email regex, date format, etc.)
- [ ] Sanitize all text inputs (escape HTML, strip dangerous chars)
- [ ] Convert datetimes to UTC ISO 8601 before storage
- [ ] Return clear error messages (400/422 with details)

**Database (Last Defense):**
- [ ] Add NOT NULL constraints where required
- [ ] Add CHECK constraints for value ranges
- [ ] Add UNIQUE constraints where applicable
- [ ] Use proper column types (`TIMESTAMP WITH TIME ZONE`, `INTEGER`, etc.)
- [ ] Add foreign key constraints for relationships

**Testing:**
- [ ] Test with valid inputs → success
- [ ] Test with missing required fields → 400/422 error
- [ ] Test with invalid formats → 400/422 error
- [ ] Test with boundary values (min, max) → correct behavior
- [ ] Test with malicious inputs (XSS, SQL injection attempts) → sanitized/blocked

---

### 8. **Investigate Anomalies - Don't Work Around Them**
**CRITICAL:** If something seems wrong, strange, or requires a workaround - it IS wrong. Stop and investigate.

**The Rule:**
```
IF behavior seems unexpected OR requires a workaround:
  THEN:
    1. STOP forward progress immediately
    2. Document the strange behavior
    3. Investigate root cause thoroughly
    4. Fix properly OR confirm it's intentional
    5. ONLY THEN continue with your task
```

**Why This Matters:**
- Workarounds mask problems, they don't solve them
- "Strange" is a red flag, not a quirk to accept
- 2 minutes investigating now prevents hours debugging later
- Small issues compound into major blockers

**Real Example - The .gitignore Incident:**
```bash
# ❌ WRONG Response
$ git add core/export.py
# Error: The following paths are ignored by .gitignore: core
# Thought: "That's weird... let me try a workaround"
$ git add -u  # Works! Moving on...
# Result: Broken .gitignore with wildcard '*' went unfixed

# ✅ CORRECT Response  
$ git add core/export.py
# Error: The following paths are ignored by .gitignore: core
# Thought: "That's wrong. Why is 'core' ignored?"
$ cat .gitignore
# Found: wildcard '*' ignoring EVERYTHING
# Action: Fix .gitignore properly, verify, then continue
```

**Common "Strange" Signals:**
- Error messages that disappear with a different command
- Tests that "randomly" pass/fail
- "It works on my machine" but fails elsewhere
- Needing sudo/admin rights where you shouldn't
- Circular imports that "just work"
- Settings that only work in a specific order
- Code that requires comments like "don't change this or it breaks"
- Dependencies installed multiple times

**The Cost of Ignoring Anomalies:**

| Issue | Workaround Time | Investigation Time | Cost of Ignoring |
|-------|-----------------|-------------------|------------------|
| `.gitignore` broken | 30 seconds | 2 minutes | Can't add new files (project-blocking) |
| Import error | 1 minute | 5 minutes | Wrong package version breaks production |
| Test flakiness | Skip the test | 10 minutes | Regression goes undetected |
| Permission error | Run as admin | 3 minutes | Security vulnerability in deployment |

**Investigation Protocol:**

1. **Capture the anomaly**
   ```bash
   # Save error messages
   command 2>&1 | tee error.log
   
   # Document unexpected behavior
   echo "Expected X, got Y because Z" >> investigation.md
   ```

2. **Form hypothesis**
   - What should happen?
   - What actually happens?
   - What's different?

3. **Test hypothesis**
   - Read config files
   - Check environment variables  
   - Review recent changes
   - Search codebase for similar patterns

4. **Fix root cause**
   - Don't patch symptoms
   - Fix the underlying issue
   - Verify fix with tests
   - Document why it happened

5. **Prevent recurrence**
   - Add checks/validation
   - Update documentation
   - Add to Prime Directive if broadly applicable

**❌ Never:**
- Dismiss errors as "probably nothing"
- Use workarounds without understanding why they're needed
- Proceed when something feels wrong
- Skip investigation "to save time"
- Leave TODO comments for weird behavior
- Assume "it's always been like that"

**✅ Always:**
- Treat "strange" as a bug until proven otherwise
- Investigate before implementing workarounds
- Document both the problem AND the solution
- Share findings with team (update Prime Directive)
- Fix properly, not quickly
- Trust your instincts - if it feels wrong, investigate

**Remember: "It works" ≠ "It's correct"**

Code that works despite being wrong is technical debt waiting to cause production incidents.

---

### 9. **AI Agent Execution Discipline — No Blind Commands**
**CRITICAL:** AI agents must never execute terminal commands blindly. Every command must be grounded, observable, and use the simplest possible tool for the job.

#### The Regression Suite Rule (Non-Negotiable)

The regression suite command is **always** run with `run_in_terminal` directly. It must never be delegated to `execution_subagent`.

```powershell
# ✅ CORRECT — direct, observable, no assumptions
run_in_terminal:
  .\Scripts\python.exe tests/run_all_smoke.py 2>&1

# ❌ WRONG — subagent invents unseen paths, redirects to assumed directories
execution_subagent:
  "Run the regression suite and capture output to C:\Temp\results.txt"
```

**Why delegation fails here:**
- `execution_subagent` runs in an isolated subcontext with no verified knowledge of machine directory structure
- It invents file paths (`C:\Temp`) that may not exist
- Failures accumulate silently, wasting session time
- The prime directive already documents the canonical command — just run it

#### Tool Selection Rules for Terminal Commands

| Situation | Correct Tool | Never Use |
|-----------|-------------|-----------|
| Run regression suite | `run_in_terminal` | `execution_subagent` |
| Run a single known command | `run_in_terminal` | `execution_subagent` |
| Multi-step exploratory build/install | `execution_subagent` | `run_in_terminal` (fragile for long chains) |
| Check file or grep result | `grep_search` / `read_file` | Terminal `cat` / `grep` commands |

#### Never Assume Paths

Before writing **any** path into a command (especially for output redirection), verify it exists.

```powershell
# ❌ WRONG — assumes C:\Temp exists (it often doesn't on Windows)
.\Scripts\python.exe tests/run_all_smoke.py *> "C:\Temp\results.txt"

# ✅ CORRECT — use project-relative path (always exists in project context)
.\Scripts\python.exe tests/run_all_smoke.py 2>&1

# ✅ CORRECT — if a file path is needed, use $env:TEMP (guaranteed) or project dir
.\Scripts\python.exe tests/run_all_smoke.py *> "$env:TEMP\cdw_results.txt"
```

**Path verification before use:**
- Project-relative paths (e.g., `tests/_last_run.txt`) — safe, always within the project
- `$env:TEMP` — safe on Windows, guaranteed to exist
- Absolute paths like `C:\Temp` — **NEVER** without first verifying with `Test-Path`

#### Incident: April 7, 2026

**What happened:**
- `execution_subagent` was invoked to run the regression suite
- Subagent invented `C:\Temp\test_results.txt` as output path
- `C:\Temp` did not exist on this machine → command failed
- Multiple retry attempts all failed; user had to intervene

**What should have happened:**
```powershell
# One tool call, one command, done
run_in_terminal: .\Scripts\python.exe tests/run_all_smoke.py 2>&1
```

**Time wasted:** Multiple tool invocations + user frustration vs. one direct command

**Root causes:**
1. Used the wrong abstraction (`execution_subagent`) for a known, single command
2. Assumed a system path without verification
3. Did not apply "simplest correct approach first" principle

**❌ Never:**
- Delegate a single documented command to `execution_subagent`
- Write a path into any command without verifying it exists
- Use `execution_subagent` when `run_in_terminal` is sufficient
- Retry the same failing approach more than once — step back and use a different tool

**✅ Always:**
- Use `run_in_terminal` for single, known commands (regression suite, test runs, git operations)
- Use project-relative paths or `$env:TEMP` if output redirection is needed
- Apply Principle 8: if a command fails once with a path error, investigate before retrying
- Reserve `execution_subagent` for genuinely multi-step exploratory tasks (install sequences, build chains)

---

### 10. **PowerShell + Python: Never Inline Complex Python via `-c`**
**CRITICAL:** PowerShell parses `{`, `}`, `'`, and `"` inside `-c "..."` strings before Python ever sees them. Any Python code containing f-string format specs (`{'field':<8}`), nested braces, or certain quote patterns will trigger a PowerShell `ParserError` — not a Python error — making the failure misleading and the fix non-obvious.

#### The Rule

**Never pass Python code that contains `{`, `}`, or nested quotes directly to `.\Scripts\python.exe -c "..."`.**

Write it to a `.py` file instead, run the file, then delete it.

#### The Problem

```powershell
# ❌ WRONG — PowerShell treats {'ID':<5} as a script block → ParserError
.\Scripts\python.exe -c "print(f'{'ID':<5} {'Active':<8}')"

# ❌ WRONG — here-string (@"..."@) helps with outer quotes but still chokes
# on nested braces like f-string format specs
.\Scripts\python.exe -c @"
print(f'{'ID':<5} {'Username':<20}')
"@
# Result: Unexpected token '}' in expression or statement
```

PowerShell errors like these are **not Python errors** — they never reach the Python interpreter at all. This makes them especially confusing to diagnose.

#### The Solution Pattern

```powershell
# ✅ CORRECT — write to file, run file, delete file
Set-Content _tmp.py -Encoding utf8 -Value @'
from app import create_app
from app.models import User

app = create_app()
with app.app_context():
    users = User.query.order_by(User.id).all()
    print(f"{'ID':<5} {'Username':<20} {'Active':<8} {'Admin':<7} {'Created'}")
    print('-' * 70)
    for u in users:
        print(f"{u.id:<5} {u.username:<20} {str(u.is_active):<8} {str(u.is_admin):<7} {u.created_at.strftime('%Y-%m-%d %H:%M')}")
'@
.\Scripts\python.exe _tmp.py
Remove-Item _tmp.py
```

Note the use of **single-quoted here-string** (`@'...'@`) — PowerShell does **zero** interpolation inside `@'...'@`, so all braces and quotes are passed verbatim to the file.

#### When Each Form Is Safe

| Python code complexity | Safe method |
|---|---|
| Simple string, no braces — `print("hello")` | `-c "..."` is fine |
| Contains `{}` for `.format()` or f-strings | Write to `.py` file |
| Contains nested quotes | Write to `.py` file |
| Multi-line or imports Flask app context | Write to `.py` file |
| Database inspection, schema migrations | Write to `.py` file |

**Default to the file pattern for anything beyond trivial one-liners.** The cost is two extra commands; the benefit is zero mysterious parser errors.

#### Naming Convention for Temp Files

Use a leading underscore so the project's `.gitignore` (which excludes `_*.py` scratch files) keeps them out of version control:

```powershell
# ✅ Temp script names
_tmp.py
_migrate.py
_patch_guide.py
_inspect.py
```

Always `Remove-Item` the temp file immediately after use.

#### Incident: April 8, 2026

**What happened:** A database patch and an ADMIN_GUIDE.md update were both written as PowerShell `-c` one-liners. Both contained Python f-string format specs (`{'Active':<8}`) and nested quotes. Multiple `ParserError: Unexpected token '}'` failures were generated before switching to the file-based approach.

**What should have happened:** Recognised immediately that any Python containing `{...}` format specs cannot be passed via `-c`. Written the script to `_tmp.py`, run it, deleted it — zero parser errors.

**❌ Never:**
- Pass Python f-string format specs (`{'field':<N}`) via `-c`
- Pass multi-line Python with braces or nested quotes via `-c`
- Retry a `-c` variant of the same broken command — switch to `.py` file on first `ParserError`
- Leave temp `.py` files in the repo after use

**✅ Always:**
- Use `@'...'@` (single-quoted here-string) when writing Python to a temp file — prevents PowerShell interpolation
- Delete temp files immediately with `Remove-Item`
- Treat a PowerShell `ParserError` on a `-c` command as a signal to switch to the file pattern, not to escape/rewrite the one-liner

---

### 11. **Mock Fidelity — Mocks Must Enforce the Real Interface**
**CRITICAL:** A mock that doesn't replicate the real class's contract gives false confidence. Tests pass; production crashes.

**The Rule:**
Every mock of a collaborator must:
1. Call the same methods in the same way the real class does
2. Assert argument *types*, not just values
3. Raise on violations — never silently accept wrong types

**The Anti-Pattern (what caused the Adopt-button bug, April 2026):**
```python
# ❌ BAD — swallows everything silently; strings are valid dict keys so no error fires
class MockEventBus:
    def subscribe(self, event_type, callback):
        self.subscriptions[event_type] = ...  # "MARKET_DATA" string works here!
```
`BaseStrategy._subscribe_to_events` was passing raw strings (`"MARKET_DATA"`) instead of
`EventType` enum members. Because the mock accepted strings without complaint, every unit test
passed — but every real instantiation crashed with `AttributeError: 'str' object has no attribute 'name'`.

**The Correct Pattern:**
```python
# ✅ GOOD — enforces the same contract as the real EventBus
from core.event_bus import Event, EventType

class MockEventBus:
    def __init__(self):
        self.subscriptions = {}
        self.published_events = []

    def subscribe(self, event_type: EventType, callback):
        assert isinstance(event_type, EventType), (
            f"subscribe() requires EventType, got {type(event_type).__name__!r}"
        )
        self.subscriptions.setdefault(event_type, []).append(callback)

    def publish(self, event: Event):
        assert isinstance(event, Event), (
            f"publish() requires Event, got {type(event).__name__!r}"
        )
        self.published_events.append(event)
        for cb in self.subscriptions.get(event.event_type, []):
            cb(event.data)
```

**Prefer real classes over mocks when possible:**
If the real class has no side effects (no network, no disk, no heavy setup), use it directly.
Reserve mocks for classes with I/O or expensive setup. `EventBus` is a pure in-memory object —
use the real one in registry and strategy tests.

**`unittest.mock.Mock()` is a last resort:**
`Mock()` accepts any call and returns `Mock` for any attribute. It validates nothing. Use it only
when the collaborator's interface is deliberately irrelevant to the specific test being written.

**Regression test requirement:**
Every mock that enforces types must have a corresponding **negative test** — a test that passes
the wrong type and asserts it raises. This locks the enforcement in place against future refactors.

```python
def test_mock_event_bus_enforces_types():
    """Verify MockEventBus raises on wrong argument types."""
    bus = MockEventBus()

    # Wrong type for subscribe — must raise, not silently key by string
    with pytest.raises(AssertionError):
        bus.subscribe("MARKET_DATA", lambda e: None)

    # Wrong type for publish — must raise, not silently append string
    with pytest.raises((AssertionError, AttributeError)):
        bus.publish("SIGNAL_GENERATED")
```

**❌ Never:**
- Use `Mock()` for a collaborator whose interface is the thing being tested
- Write a mock that accepts raw strings/ints where the real class demands typed objects
- Assert only that a key *exists* in `mock.subscriptions` without checking its type

**✅ Always:**
- Add `isinstance` assertions inside mock methods for all arguments with a documented type
- Write at least one **negative test**: pass the wrong type and assert it raises
- Prefer the real class when it has no side effects
- If a `Mock()`-based test passes but production crashes, the mock is lying — fix the mock

#### Incident: April 2026

**What happened:**
`BaseStrategy._subscribe_to_events` passed raw strings to `EventBus.subscribe()`, which calls
`event_type.name`. `MockEventBus` silently keyed by those strings. All 50+ strategy unit tests
passed; every `POST /api/strategies/create` call (the "Adopt" button) raised `AttributeError`.

**Root causes:**
1. `MockEventBus` accepted any hashable key — strings appeared equivalent to `EventType` members
2. `POST /api/strategies/create` had no test at all (Route Coverage Rule violation)
3. Registry tests used bare `Mock()` which swallowed every wrong-type call silently

**Time to diagnose:** ~30 minutes. Time to prevent with this principle: ~2 minutes (add `isinstance` assert and one `POST /create` test).

---

### 12. **Secrets & Credentials Management — Never Commit Secrets**
**CRITICAL:** Credentials, API keys, tokens, and passwords committed to version control are permanently exposed — even after deletion, the history remains. This is one of the most common and damaging security mistakes.

**The Rule:**
Never commit secrets to version control. Ever. Not even temporarily.

**What counts as a secret:**
- API keys and tokens (broker keys, OpenAI keys, third-party service keys)
- Passwords and database connection strings
- Private keys and certificates
- OAuth client secrets
- Webhook signing secrets
- Any value your code uses to authenticate to an external service

**The Correct Pattern:**
```python
# ✅ CORRECT — load secrets from environment variables
import os
from dotenv import load_dotenv

load_dotenv()  # Loads from .env file (which is in .gitignore!)

API_KEY = os.environ["BROKER_API_KEY"]       # Raises KeyError if missing — catches misconfiguration
DB_URL = os.environ.get("DATABASE_URL", "")  # Returns empty string if missing

# ❌ WRONG — hardcoded credential
API_KEY = "sk-abc123realkey..."  # Never!
DB_URL = "postgresql://admin:password@prod-server/db"  # Never!
```

**Project Setup (Mandatory for every project):**
```bash
# Step 1: Create .env file for local secrets (never commit this)
# .env
BROKER_API_KEY=your_key_here
DATABASE_URL=postgresql://localhost/mydb

# Step 2: Create .env.example with placeholder values (SAFE to commit)
# .env.example
BROKER_API_KEY=your_broker_api_key_here
DATABASE_URL=postgresql://localhost/mydb

# Step 3: Ensure .gitignore includes .env
echo ".env" >> .gitignore
```

**If a Secret Is Accidentally Committed:**
1. **Rotate the credential immediately** — assume it is compromised
2. Remove the secret from the codebase
3. Force-push is NOT sufficient — git history retains it
4. Use `git filter-branch` or BFG Repo Cleaner to scrub history
5. Notify the service provider if the secret controls external access

**❌ Never:**
- Commit `.env` files containing real credentials
- Hardcode secrets in source code, even in "dev" branches
- Log or print secret values (they end up in log files)
- Share secrets via chat messages, email, or tickets
- Assume a private repository is safe for committing credentials

**✅ Always:**
- Use `.env` for local development secrets (with `.env` in `.gitignore`)
- Commit `.env.example` with placeholder values to document required keys
- Use environment variables in CI/CD pipelines and production deployments
- Rotate any credential that may have been exposed
- Check for secret leaks before every PR merge (use tools like `git-secrets` or GitHub secret scanning)

---

### 13. **Git Branching & Code Review — Protect the Main Branch**
**CRITICAL:** Committing untested or unreviewed code directly to `main` bypasses quality gates and introduces regressions that affect everyone. Every change must be isolated and reviewed before merging.

**The Branching Model:**
```
main          ← production-ready only; never commit directly here
  └─ feature/my-feature     ← all new work starts here
  └─ fix/bug-description    ← bug fixes
  └─ chore/dependency-update ← maintenance tasks
```

**Branch Naming Convention:**
```bash
# ✅ Descriptive, type-prefixed names
feature/add-risk-manager-stop-loss
fix/order-rejected-on-market-open
chore/upgrade-ibapi-to-10.19
refactor/extract-position-calculator

# ❌ Vague or unprefixed names
my-branch
update
fix2
```

**The Workflow (Non-Negotiable):**
1. **Create a feature branch** from up-to-date `main`
   ```bash
   git fetch origin
   git checkout -b feature/my-feature origin/main
   ```
2. **Work on the branch** — commit frequently with descriptive messages
3. **Pass all tests locally** before opening a PR (Principle 1)
4. **Open a Pull Request** — describe what changed and why
5. **Code review** — at least one reviewer must approve before merge
6. **Merge** only after all checks pass and review is approved

**Code Review Checklist (Reviewer):**
- [ ] Does the code do what the PR description claims?
- [ ] Are edge cases handled? (None, empty, boundary values — Principle 3)
- [ ] Are tests present and meaningful? (Principle 1)
- [ ] Are there any security concerns? (secrets, injection, input validation — Principles 7, 13)
- [ ] Is the code readable without excessive explanation?
- [ ] Does it introduce any new warnings or deprecations?

**Code Review Checklist (Author):**
- [ ] All tests pass with zero warnings (Principle 1)
- [ ] No secrets or credentials in diff (Principle 12)
- [ ] PR scope is focused — one logical change per PR
- [ ] Commit messages are descriptive (type: summary format)
- [ ] Breaking changes are documented

**Keep PRs Small:**
- Large PRs are harder to review and more likely to introduce subtle bugs
- A PR should ideally change fewer than 400 lines
- If a feature is large, split it into sequential PRs

**❌ Never:**
- Push directly to `main` (except for critical hotfixes with immediate retrospective)
- Merge a PR without at least one review (for solo projects: self-review with a checklist)
- Leave stale branches open for weeks — merge or delete
- Use `git push --force` on shared branches (destroys collaborators' history)

**✅ Always:**
- Branch from the latest `main`
- Keep `main` in a deployable state at all times
- Write a clear PR description explaining the "why" not just the "what"
- Respond to review comments before re-requesting review
- Delete merged branches to keep the repo tidy

---

### 14. **CDN / External Resource Integrity — Never Write SRI Hashes by Hand**
**CRITICAL:** Subresource Integrity (SRI) `integrity="sha384-..."` attributes must always be computed directly from the live CDN file. Writing or copying a hash from memory, documentation, or a previous session is unreliable and will cause the resource to be silently blocked by the browser.

**The Rule:**
Before committing any `<link>` or `<script>` tag that includes an `integrity` attribute, verify the hash by downloading and hashing the actual file.

**Why Hand-Written Hashes Fail:**
- CDN providers occasionally update file content (minification changes, patch releases) even under the same version URL
- A single character case difference (`s` vs `S`) produces a completely different Base64 hash — the error is invisible in a code review
- The browser blocks the resource silently; the only symptom is a console error and broken JavaScript, which looks identical to many other UI bugs
- Backend tests pass regardless — they never load the CDN resource

**The Correct Protocol — Always Compute From the Live File:**

```powershell
# ✅ CORRECT — download the file and compute its actual SHA-384 hash
Scripts\python.exe -c "import urllib.request, hashlib, base64; d = urllib.request.urlopen('REPLACE_WITH_CDN_URL').read(); print('sha384-' + base64.b64encode(hashlib.sha384(d).digest()).decode())"
```

Then paste the printed value directly into the `integrity` attribute.

**Example (Bootstrap 5.3.3 JS):**
```powershell
Scripts\python.exe -c "import urllib.request, hashlib, base64; d = urllib.request.urlopen('https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js').read(); print('sha384-' + base64.b64encode(hashlib.sha384(d).digest()).decode())"
# Output: sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz
```

**Verification Step After Editing:**
After updating the hash in the template, confirm Flask is serving the corrected value before committing:
```powershell
$r = Invoke-WebRequest -Uri 'http://localhost:5000/' -UseBasicParsing
($r.Content | Select-String -Pattern 'integrity="sha384[^"]*"' -AllMatches).Matches | ForEach-Object { $_.Value }
# Must match the hash you just computed above
```

**When This Rule Applies:**
- Any new `<script>` or `<link>` tag added with a CDN URL and `integrity` attribute
- Any time a CDN library version is upgraded
- Any time a template is copied from a code sample, documentation, or another project
- Any time an SRI-related console error appears (treat as hash mismatch, compute fresh)

**❌ Never:**
- Copy an SRI hash from a README, documentation page, or code sample without verifying it against the live file
- Write a hash from memory or a prior session
- Assume the hash embedded in a CDN provider's own documentation is current
- "Fix" an SRI error by removing the `integrity` attribute — that removes the security guarantee entirely
- Retry the same broken hash after a browser SRI error — always recompute

**✅ Always:**
- Run the `urllib.request` / `hashlib.sha384` one-liner against the exact CDN URL before committing
- Check browser console (F12) after any change touching CDN `integrity` attributes — 0 errors required
- Verify Flask is serving the new hash via `Invoke-WebRequest` before marking the fix done

---

## 🧪 Testing Strategy Decision Matrix

**Quick Guide: What Testing Do I Need?**

| Change Type | Backend Tests | Manual UI Test | E2E Browser Tests | Time Investment |
|-------------|--------------|----------------|-------------------|-----------------|
| **Backend logic only** (API, core, data models) | ✅ Required | ❌ Not needed | ❌ Not needed | 5-15 min |
| **UI only** (CSS, static HTML) | ⚠️ Run existing | ✅ Required | ❌ Not needed | 2-5 min |
| **JavaScript/Forms** (interactions, validation) | ✅ Required | ✅ Required | ⚠️ Consider for complex | 10-20 min |
| **Full-stack feature** (backend + frontend) | ✅ Required | ✅ Required | ⚠️ Consider for critical | 20-40 min |
| **Bug fix** (any layer) | ✅ Add regression test | ✅ Required if UI | ❌ Usually not needed | 10-30 min |

**Testing Type Definitions:**

1. **Backend Tests (pytest, unittest)**
   - **What:** Python tests that call functions/routes directly
   - **Catches:** Logic errors, data flow issues, API contract violations
   - **Misses:** JavaScript bugs, form behavior, browser rendering, user interactions
   - **Speed:** Fast (seconds to minutes)
   - **When:** Always for backend changes; run but don't add for pure UI changes

2. **Manual UI Testing**
   - **What:** Human clicking through the application in a browser
   - **Catches:** Broken forms, JS errors, layout issues, confusing UX
   - **Misses:** Race conditions, edge cases (manual testing is not exhaustive)
   - **Speed:** Fast (2-5 minutes for smoke test)
   - **When:** Required for ANY change that touches HTML/CSS/JavaScript

3. **E2E Browser Tests (Selenium, Playwright)**
   - **What:** Automated browser tests simulating user interactions
   - **Catches:** UI bugs, JS errors, integration issues (automated coverage)
   - **Misses:** Nothing significant (most comprehensive)
   - **Speed:** Slow (minutes to hours for full suite)
   - **When:** Complex UIs, multiple developers, customer-facing apps
   - **Trade-off:** High maintenance cost vs. manual testing discipline

**Decision Flowchart:**

```
Did I change backend code (Python)?
├─ YES → Write/update backend tests ✅
└─ NO → Run existing backend tests (smoke check) ⚠️

Did I change frontend code (HTML/CSS/JS)?
├─ YES → Manual UI test REQUIRED ✅
│        └─ Is it complex/critical user flow?
│           ├─ YES → Consider E2E tests 💭
│           └─ NO → Manual test sufficient ✅
└─ NO → Skip manual testing ❌

Is this a customer-facing production app?
├─ YES → Consider E2E test suite 💭
└─ NO (Internal tool) → Manual testing sufficient ✅
```

**For Small Internal Tool Profile (Example):**
- ✅ Backend tests required (fast, automated)
- ✅ Manual UI testing required (2-5 min, catches most issues)
- ❌ E2E browser tests skipped (overhead > benefit for small team)

**When to Add E2E Tests:**
- Team size > 5 developers making concurrent UI changes
- Frequent customer escalations due to UI bugs
- Critical financial/healthcare application (high risk)
- Complex SPA with heavy JavaScript (React/Vue/Angular)

**When to Skip E2E Tests:**
- Small team (1-3 developers)
- Internal tools with few users
- Simple CRUD applications
- Manual testing discipline working well
- Limited time/budget for test maintenance

---

## 🔍 Pre-Implementation Checklist

Before writing ANY new code that uses existing classes/methods:

### ☑️ Research Phase (Mandatory)

#### For New Feature Implementation (TDD):
1. **Check Method Signatures**
   ```python
   # Use grep_search to find the method definition
   grep_search(query="def method_name", includePattern="filename.py")
   ```

2. **Verify Enum Values**
   ```python
   # Read the enum definition
   read_file("path/to/file.py", offset=line_number, limit=30)
   ```

3. **Inspect Data Structures**
   ```python
   # Check class attributes and properties
   grep_search(query="class ClassName", includePattern="*.py")
   list_code_usages(symbolName="ClassName")
   ```

4. **Find Usage Examples**
   ```python
   # See how others use this API
   grep_search(query="method_call.*pattern", isRegexp=True)
   ```

#### For Integration Tests of Existing Code (NEW):
**⚠️ CRITICAL: Research APIs BEFORE writing integration tests**

1. **List All Components to Integrate**
   ```python
   # Write down every class/module you'll test together
   # Example: StrategyLifecycle, PaperMetricsTracker, StrategyOrchestrator, RiskManager
   ```

2. **Find Existing Tests for Each Component**
   ```python
   # These tests show the CORRECT API usage
   grep_search(query="test.*ComponentName", includePattern="test_*.py")
   # Result: tests/test_component.py
   ```

3. **Read Existing Tests (API Documentation)**
   ```python
   # Read the test file completely
   read_file("tests/test_component.py")
   # Note ALL constructor signatures, method calls, return values
   # Pay special attention to:
   # - Parameter order (db_path first? strategy_name second?)
   # - Parameter count (5 params not 3?)
   # - Method names (get_report not validate?)
   # - Attribute names (overall_passed not passed?)
   # - Return types (dict not object? list not single item?)
   ```

4. **Verify Ambiguous Cases from Implementation**
   ```python
   # If existing tests don't clarify something, check source
   grep_search(query="class ComponentName", includePattern="*.py")
   read_file("path/to/component.py", offset=line, limit=50)
   ```

5. **Document API Reference in Comments**
   ```python
   # Create comprehensive API reference block at top of test file
   """
   API Reference (verified from existing tests):
   
   ComponentA (from test_component_a.py):
   - Constructor: ComponentA(param1: type, param2: type)
   - method1(arg1, arg2) -> return_type
   - attribute_name (not attribute_name_variant!)
   
   ComponentB (from test_component_b.py):
   - Constructor: ComponentB(db_path, name, initial_val) - db_path FIRST
   - method2(p1, p2, p3, p4, p5) - 5 params required!
   - Returns dict with keys: 'key1', 'key2' (not object)
   """
   ```

6. **Verify Integration Points**
   ```python
   # Check how components interact in existing code
   grep_search(query="ComponentA.*ComponentB", isRegexp=True)
   # Look for: data passing patterns, callback signatures, event handling
   ```

**Integration Test Research Checklist:**
- [ ] All components listed
- [ ] Existing tests found for each (test_*.py files)
- [ ] Existing tests read and APIs documented
- [ ] Constructor signatures verified (param order, types, required vs optional)
- [ ] Method signatures verified (names, param counts, return types)
- [ ] Attribute names verified (singular/plural, exact spelling)
- [ ] Enum values verified (actual values, not assumed)
- [ ] Integration patterns verified (how components interact)
- [ ] API reference comment block created
- [ ] Ambiguous cases checked in implementation
- [ ] Expected 80%+ first-run pass rate

**Time Investment:**
- API Research: 20-40 minutes (depends on component count)
- Test Writing: 40-60 minutes (faster with verified APIs)
- Debugging: 5-15 minutes (minimal with correct APIs)
- **Total: 65-115 minutes** (vs 180+ minutes without research)

**When to Skip Research:**
- Unit tests for code you just implemented (you know the API)
- Tests written alongside new implementation (TDD)
- You implemented the component recently (within same sprint)

### ☑️ Before Calling Any Method

- [ ] Checked the method signature (parameters, types, order)
- [ ] Verified return type (can it be None? Optional?)
- [ ] Checked for required imports
- [ ] Looked for existing usage examples
- [ ] Understood parameter types (enum vs string, int vs Optional[int])

### ☑️ Before Using Enums/Constants

- [ ] Verified actual enum value names (not assumed)
- [ ] Checked if it's a string enum or value enum
- [ ] Imported the enum properly

---

## 🚨 Common Pitfalls & Solutions

### Pitfall 1: Wrong Enum Values
**Problem:** Assuming enum names without checking
```python
TimeFrame.DAILY  # ❌ Doesn't exist
```
**Solution:** Always verify enum definitions
```python
TimeFrame.DAY_1  # ✅ Actual value
```
**Prevention:** Read enum source code first, add reference comment:
```python
# TimeFrame: DAY_1, HOUR_1, MINUTE_1, MINUTE_5, etc.
```

### Pitfall 2: Method Signature Mismatch
**Problem:** Implementing interface without checking base class
```python
def on_bar(self, symbol, bar):  # ❌ Wrong signature
```
**Solution:** Check abstract method in base class
```python
def on_bar(self, market_data):  # ✅ Matches Strategy base class
```
**Prevention:** Use `grep_search` to find base class method signature

### Pitfall 3: Attribute Name Assumptions
**Problem:** Guessing attribute names
```python
market_data.symbol  # ❌ It's plural!
```
**Solution:** Check class definition
```python
market_data.symbols  # ✅ Returns list
market_data.get_bar(symbol)  # ✅ Gets bar for symbol
```
**Prevention:** Read class docstrings and inspect attributes

### Pitfall 4: None Type Errors
**Problem:** Not handling None return values
```python
position = get_position(symbol)
if position > 0:  # ❌ Crashes if None
```
**Solution:** Always handle None explicitly
```python
position = get_position(symbol) or 0
if position > 0:  # ✅ Safe
```
**Prevention:** Check return type hints: `Optional[T]` means None is possible

### Pitfall 5: Parameter Type Confusion
**Problem:** Passing string where enum expected
```python
self.buy(symbol, quantity, "market order")  # ❌ String not OrderType
```
**Solution:** Use proper enum type
```python
self.buy(symbol, quantity, OrderType.MARKET)  # ✅ Enum
```
**Prevention:** Check method signature for parameter types

---

## 🛠️ Mandatory Tools Usage

### Before Implementation

| Task | Tool | Example |
|------|------|---------|
| Find method definition | `grep_search` | `grep_search(query="def on_bar", includePattern="strategy.py")` |
| Read enum values | `read_file` | `read_file("data_models.py", offset=17, limit=30)` |
| Check class usage | `list_code_usages` | `list_code_usages(symbolName="Strategy")` |
| Find patterns | `grep_search` (regex) | `grep_search(query="TimeFrame\\.", isRegexp=True)` |
| Verify structure | `read_file` | `read_file("file.py", offset=50, limit=100)` |

### During Development

| Task | Tool | Example |
|------|------|---------|
| Run tests | `run_in_terminal` | `python test_module.py` |
| Check errors | `get_errors` | `get_errors(filePaths=["path/to/file.py"])` |
| Verify changes | `read_file` | Read modified sections |

---

## 📋 Development Workflow (The Right Way™)

### Phase 1: Research (15-30% of time)
```
For New Feature Implementation:
1. Understand the requirement
2. Find relevant existing code
3. Check base classes and interfaces
4. Verify data structures and enums
5. Look for usage examples
6. Document findings in comments

For Integration Tests (ADDITIONAL - MANDATORY):
1. List ALL components to integrate
2. Find existing tests for EACH component (test_*.py)
3. Read existing tests COMPLETELY (note every API detail)
4. Verify constructor signatures (param order, types, counts)
5. Verify method signatures (names, params, return types)
6. Verify attribute names (exact spelling, singular/plural)
7. Verify integration patterns (how components interact)
8. Document comprehensive API reference in comments
9. Expected outcome: 80%+ first-run pass rate
```

**Integration Test Research is NON-NEGOTIABLE:**
- Skipping this step leads to API mismatches (see historical sprint example below)
- 30 minutes research saves 2 hours debugging
- Existing tests are your API documentation
- Write the API reference comment block BEFORE writing tests

### Phase 2: Design (10-15% of time)
```
1. Sketch out the implementation
2. Identify dependencies
3. Plan for error handling
4. Consider edge cases
5. Keep it simple initially
```

### Phase 3: Implementation (40-50% of time)
```
1. Start with minimal working code
2. Match signatures exactly
3. Add defensive checks (None, bounds, types)
4. Use proper types (enums, not strings)
5. Add logging/print statements for debugging
6. Keep functions small and focused
```

### Phase 4: Testing (20-30% of time)
```
1. Test each component in isolation
2. Add unit tests as you go
3. Run tests frequently (after each component)
4. Fix errors immediately - don't accumulate
5. Verify integration works
6. Run full test suite before committing
```

---

## ✅ Code Quality Standards

### Type Safety
```python
# ✅ GOOD: Use type hints
def calculate_position_size(
    self, 
    symbol: str, 
    price: float,
    fraction: Optional[float] = None
) -> int:
    ...

# ✅ GOOD: Handle Optional types
position: Optional[int] = self.get_position(symbol)
if position is None:
    position = 0
```

### Error Handling
```python
# ✅ GOOD: Validate inputs
if not symbol or symbol not in self.config.symbols:
    return

# ✅ GOOD: Check preconditions
if len(prices) < self.lookback_period:
    return  # Not enough data

# ✅ GOOD: Handle exceptions gracefully
try:
    result = risky_operation()
except SpecificError as e:
    log.warning(f"Operation failed: {e}")
    return default_value
```

### Documentation
```python
# ✅ GOOD: Document assumptions and constraints
def on_bar(self, market_data):
    """
    Process market data bar
    
    Note: MarketData.symbols is a list (plural)
    Note: get_position() returns Optional[int] - check for None!
    """
    for symbol in market_data.symbols:  # Note: plural!
        position = self.get_position(symbol) or 0  # Handle None
        ...
```

---

## 🎓 Learning from Errors

_Note: This section contains case studies and examples. Reuse the principles even when your stack, framework, and project domain differ._

### Case Study (Web App): Frontend Testing Gap (February 16, 2026)

#### Lesson: Backend Tests Can't Catch JavaScript Bugs
**Context:** Web application incident - backend tests were passing, but users couldn't submit forms

**The Incident:**
- All 138 backend tests passing with 0 warnings ✓
- Application deployed confidently based on test results
- User reports: "Transcript text disappears when I click Generate MOM"
- Form submissions never reaching server - no POST requests logged
- Issue: JavaScript tab-switching code was **clearing form field values**

**Root Cause:**
```javascript
// Bug in templates/index.html
if (tabId === 'text-tab') {
    transcriptField.disabled = false;
    audioField.disabled = true;
    audioField.value = '';  // OK
} else {
    transcriptField.disabled = true;
    audioField.disabled = false;
    transcriptField.value = '';  // ❌ BUG: Clears user input!
}
```

**Why Tests Didn't Catch It:**
- Backend tests use `client.post('/process', data={...})` directly
- They **bypass** all HTML, JavaScript, and browser behavior
- Tests never execute tab-switching JS code
- Tests never interact with actual form elements
- 100% backend test pass ≠ working user interface

**The False Confidence:**
```bash
============================= 138 passed in 21.81s =============================
```
- Looked perfect ✓
- All routes working ✓
- All business logic correct ✓
- **But users couldn't use the app** ❌

**What We Should Have Done:**
1. ✅ Run backend tests (we did this)
2. ❌ **Manual smoke test** (we skipped this) → would have caught bug in 30 seconds
3. ❌ **Check browser console** (we skipped this) → might have shown errors
4. ❌ **Test critical flow** (we skipped this) → submit form, verify POST request

**The 2-Minute Test That Would Have Saved Hours:**
```markdown
Manual Smoke Test (skipped):
1. Open http://localhost:5000 in browser
2. Paste transcript in text field
3. Click "Generate MOM" button
4. Expected: redirect to /edit page
5. Actual: page refreshes, data gone
→ Bug discovered in 30 seconds
```

**Cost of Skipping Manual Test:**
- Time saved: 2 minutes
- Time spent debugging: 45+ minutes  
- User frustration: High
- Damage to test credibility: "Tests passed but app is broken"

**Lessons Learned:**
1. **"100% backend tests pass" ≠ "application works"**
   - Tests verify logic, not user experience
   - JavaScript bugs invisible to Python tests
   - Browser behavior not tested

2. **Manual testing is NOT optional for UI changes**
   - Takes 2-5 minutes
   - Catches 90% of UI bugs immediately
   - No excuses for skipping

3. **Always check browser console (F12)**
   - JavaScript errors show here
   - Network tab shows failed requests
   - Console logs show debugging info

4. **Add manual testing to commit messages**
   ```
   Fix: Enable form submission workflow
   
   Backend Tests: 138/138 passed ✓
   Manual Testing: ✓
     - Form submission works
     - POST request reaches server  
     - Redirects to /edit successfully
     - Browser console: 0 errors
   ```

5. **Consider where automated tests fall short**
   - Backend tests → fast, reliable, miss UI bugs
   - Manual testing → catches UI bugs, requires discipline
   - E2E browser tests → comprehensive, but expensive

**Action Items Implemented:**
1. ✅ Added Principle 5 to Prime Directive: "Frontend/UI Testing - The Backend Test Blind Spot"
2. ✅ Created manual testing checklist for UI changes
3. ✅ Added enhanced logging (server + client) for debugging
4. ✅ Fixed root cause: removed field value clearing in tab-switch code
5. ✅ Documented in commit with manual testing verification

**Key Quote:**
> "It's not exactly reassuring that the initial set of tests still let this issue happen"  
> — User feedback that exposed the testing blind spot

**Prevention Strategy:**
- Never deploy UI changes without manual smoke test
- Add "Manual Testing: ✓" section to commit messages for UI work
- Check browser console must be part of workflow
- Accept that some testing requires human interaction

**Long-term Consideration:**
- For larger teams/complex UIs: Consider Selenium/Playwright E2E tests
- For small projects/internal tools: Manual checklist + discipline is sufficient
- Trade-off: E2E test maintenance time vs manual testing time (usually manual wins for small projects)

---

### Case Study (Web App): Premature Commit and Compounding Bugs (February 16, 2026)

#### Lesson: "Fixed" Doesn't Mean Fixed - Three Bugs Masking Each Other
**Context:** Web application incident - a committed "fix" didn't actually work and required extensive debugging to find THREE separate bugs

**The Incident Timeline:**
1. **First commit (0e64b72):** "Fix form submission bug" - claimed to remove field clearing
2. **User test:** "Same problem persists" - form still not working
3. **Debugging discovery:** THREE separate bugs were present:
   - Bug #1: Disabled form fields (don't submit values)
   - Bug #2: JavaScript syntax error (missing closing brace)
   - Bug #3: if/elif logic bug in Python (audio field check always true)

**The Premature Commit:**
```bash
# What I thought I fixed:
- Removed transcriptField.value = '' and audioField.value = ''
- Added extensive logging
- Committed with confidence

# What I actually missed:
- Didn't test manually before committing
- Assumed code changes were correct without verification
- Trusted code review over actual execution
```

**The Three Compounding Bugs:**

**Bug #1: Disabled Form Fields**
```javascript
// templates/index.html
if (tabId === 'text-tab') {
    transcriptField.disabled = false;
    audioField.disabled = true;  // ❌ Disabled fields DON'T submit!
}
```
**Issue:** HTML specification - disabled form fields are excluded from form submission
**Hidden by:** Even if JavaScript worked, fields wouldn't submit
**Fix:** Removed all disabled logic, let server decide which input to use

**Bug #2: JavaScript Syntax Error**
```javascript
// templates/index.html - broken structure
if (inputForm) {
    inputForm.addEventListener('submit', function(e) {
        // ... submission handler code ...
        return true;
    });
// ❌ MISSING CLOSING BRACE for if (inputForm) block!
</script>
```
**Error:** `Uncaught SyntaxError: Unexpected end of input (at (index):222)`
**Impact:** 
- Event handler never registered
- JavaScript failed silently
- Form did plain HTML submission (no validation, no logging)
- All console.log statements never executed
**Hidden by:** Bug #1 meant even if JS worked, form wouldn't submit values
**Fix:** Added missing `}` closing brace

**Bug #3: if/elif Logic Bug**
```python
# app.py - broken logic
if 'audio_file' in request.files:  # ❌ ALWAYS TRUE (field exists even when empty)
    audio_file = request.files['audio_file']
    if audio_file and audio_file.filename:  # Only processes if file uploaded
        transcript = transcribe_audio(...)
# elif never runs because outer if is always true!
elif 'transcript_text' in request.form:  # ❌ NEVER EXECUTES
    transcript = request.form['transcript_text']
```
**Issue:** Form fields always exist in request, even when empty
**Impact:**
- Transcript branch never executed
- `transcript` variable stayed `None`
- Cleaned to empty string
- Validation failed: "Transcript is empty"
**Hidden by:** Bugs #1 and #2 prevented form from submitting properly to even see this
**Fix:** Changed to check for actual file content: `if audio_file and audio_file.filename:`

**Why All Three Bugs Were Present:**
1. **First bug** (disabled fields) introduced when trying to "fix" clearing issue
2. **Second bug** (syntax error) introduced while adding extensive logging
3. **Third bug** (if/elif logic) was pre-existing but hidden by first two bugs
4. **Each bug masked the others** - fixing one revealed the next

**The Systematic Debugging Process That Found Them:**
```markdown
Step 1: Check browser console → Found syntax error (Bug #2)
Step 2: Fix syntax error, test → Still doesn't work, no logs appearing
Step 3: Check form submission → Fields have values, but not submitting  
Step 4: Research disabled fields → Discovered they don't submit (Bug #1)
Step 5: Remove disabled logic, test → Form submits but server gets empty transcript
Step 6: Check server logs → Transcript arrives (230 chars) but becomes empty after cleaning
Step 7: Trace Python logic → Found if/elif never reaching transcript branch (Bug #3)
Step 8: Fix if/elif logic → SUCCESS!
```

**What Should Have Been Done (First Time):**
```markdown
Pre-Commit Checklist (FAILED):
□ Backend tests passing (138/138) ✓ - Not sufficient!
□ Manual smoke test - ❌ SKIPPED (would have caught all bugs)
□ Browser console check - ❌ SKIPPED (would have found syntax error)
□ Server logs during manual test - ❌ SKIPPED (would have found if/elif bug)
□ Verified form submission end-to-end - ❌ SKIPPED
```

**Cost Analysis:**
- Time to manual test before first commit: **2 minutes**
- Time spent debugging after premature commit: **45+ minutes**
- Additional commits needed: **2 (first one was wrong)**
- Users affected: **1 (found issues immediately)**
- **ROI of 2-minute manual test: 22.5x time savings**

**Critical Insights:**

1. **"Backend tests pass" ≠ "Code works"**
   - 138/138 tests passed for ALL THREE buggy commits
   - Tests validated logic, not execution
   - No amount of unit tests catches these build-time issues

2. **Multiple bugs compound exponentially**
   - Bug #1 alone: 5 min to find
   - Bug #2 alone: 2 min to find  
   - Bug #3 alone: 10 min to find
   - All three together: 45+ min (each hides the others)

3. **Systematic debugging is essential when multiple bugs present**
   - Start at the beginning (browser loads)
   - Check each layer (JavaScript → HTML → Server → Logic)
   - Fix one bug, re-test immediately
   - Don't assume you found "the" bug (there might be more)

4. **Never commit "fixes" without verification**
   - Code that "should work" often doesn't
   - Reading code ≠ executing code
   - 2 minutes of testing > 45 minutes of debugging later

5. **Syntax errors are silent killers**
   - JavaScript syntax errors prevent ALL subsequent code from running
   - Event handlers never register
   - No error shown to user (just fails silently)
   - Browser console is MANDATORY for any JS changes

**Updated Pre-Commit Protocol (Post-Incident):**
```markdown
For ANY code change that affects user-facing features:

1. Backend tests passing ✓
2. **MANDATORY Manual Test:**
   - Start application
   - Exercise the changed feature end-to-end
   - Check browser console (F12) for errors
   - Check server logs for expected behavior
   - Verify success/failure cases
3. **Document manual testing in commit message:**
   ```
   Manual Testing: ✓
     - Pasted transcript in form (228 chars)
     - Clicked Generate MOM
     - Form submitted successfully
     - Server received transcript
     - MOM generated and displayed
     - Browser console: 0 errors
   ```
4. Only then commit and push

Time investment: 2-5 minutes
Time savings: 15-60+ minutes (per avoided bug)
Confidence level: Actually fixed (not "should be fixed")
```

**The Hard Truth:**
```
Commit 0e64b72: "Fix form submission bug" 
Actual status: Claimed fix, didn't test, pushed broken code
User feedback: "Same problem persists"
Reality: THREE bugs still present

Commit ca0e67d: "Fix form submission bugs (ACTUAL fix)" 
Actual status: Tested manually, verified working
User feedback: "the previous errors were resolved"
Reality: Actually fixed, user confirmed
```

**Key Quote:**
> "appreciate the hard work. Can you please push to git?"  
> — User request showing assumption that code was ready (but it wasn't until manual testing forced proper debugging)

**Permanent Rule Additions:**
1. **Never commit without manual verification of changed functionality**
2. **"Should work" ≠ "Does work" - only execution proves correctness**
3. **Browser console must be checked for ALL JavaScript changes**
4. **Systematic debugging checklist for compounding bugs**
5. **Document what you tested, not just what you changed**

**Prevention Strategy:**
- Make manual testing feel as important as backend tests (because it is)
- Budget 2-5 minutes for manual verification into every code change
- Use browser DevTools as religiously as pytest
- Treat premature commits as failures requiring incident reports
- Accept that some verification requires actual execution, not code review

---

### Case Study (Web App): SRI Hash Written by Hand — One Character, Hours Lost (May 18, 2026)

#### Lesson: Never Write or Copy SRI Hashes — Always Compute Them From the Live File

**Context:** CDW application — Bootstrap JS was silently blocked on the Export page, making the download button unresponsive. Three separate sessions were spent diagnosing the issue before the root cause was identified.

**The Incident:**
1. User reported the Export page download button was "unresponsive"
2. Browser console showed: `Failed to find a valid digest in the 'integrity' attribute for resource`
3. A fix was committed (`4ddb802`) with a "corrected" SRI hash — written from inspection of the error, not computed from the file
4. User hard-refreshed, restarted Flask, tested again — same error
5. Another session was spent re-diagnosing (Flask not running, cache, etc.)
6. Root cause finally found: the "corrected" hash had a lowercase `s` where the actual file's hash has an uppercase `S` in position 32 of the Base64 string

**The One-Character Difference:**
```
# What was committed (WRONG):
sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLEsaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz
                                          ^
                                     lowercase s

# What the file actually hashes to (CORRECT):
sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz
                                          ^
                                     uppercase S
```

Base64 is case-sensitive. The browser computes the hash from the file it downloads, then compares it character-by-character against the `integrity` attribute. One character mismatch = blocked.

**Why It Was Hard to Find:**
- The hash strings are 64 characters long — a single case difference is invisible in a code review
- The page loaded correctly (Flask was serving HTML); only the CDN JS was blocked
- The error message shows the *computed* hash, not the *attribute* hash — easy to misread
- Flask's debug mode re-reads templates on every request, so there was no caching issue to investigate
- Multiple red herrings: Flask not running, browser cache, Edge tracking prevention — all explored before the hash itself was checked

**What Should Have Happened:**
```powershell
# ✅ CORRECT — one command, done, no guessing
Scripts\python.exe -c "import urllib.request, hashlib, base64; d = urllib.request.urlopen('https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js').read(); print('sha384-' + base64.b64encode(hashlib.sha384(d).digest()).decode())"
# Output: sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz
```

Then verify Flask is serving the result:
```powershell
$r = Invoke-WebRequest -Uri 'http://localhost:5000/' -UseBasicParsing
($r.Content | Select-String -Pattern 'integrity="sha384[^"]*"' -AllMatches).Matches | ForEach-Object { $_.Value }
```

**Cost Analysis:**
- Time to compute hash from live URL: **30 seconds**
- Time spent across multiple sessions diagnosing: **60+ minutes**
- Additional incorrect commits: **1**
- User frustration: **High** (tested the same broken behaviour repeatedly)

**Root Causes:**
1. SRI hash written by reading the error message instead of computing from the file
2. No verification step — Flask was queried for CSS/JS loading but not for the integrity attribute value itself
3. Principle 14 did not exist — no documented rule requiring hash computation

**Lessons Learned:**
1. **SRI hashes are opaque 64-character Base64 strings — never write them from memory or by eye**
2. **The correct hash is computed from the file, not inferred from error messages**
3. **After any SRI fix, verify the served attribute value matches the computed hash before closing the task**
4. **A one-character difference in a hash is undetectable in code review — only the computation matters**

**Permanent Rule Additions:**
- Principle 14 added: CDN / External Resource Integrity — Never Write SRI Hashes by Hand
- Pre-commit checklist item added for UI changes: CDN integrity hash verified against live URL

---

### Historical Lessons (Legacy Project) - Day 4 (November 22, 2025)

_Note: This section is retained as historical reference from a prior project. Apply the principles, not the project-specific module names._

#### Lesson 1: Delete Systematically with Test Verification
**Context:** Cleaning up duplicate modules and legacy scripts (legacy project example)
- **What we did right:**
  1. Verified baseline: 138/138 tests passing
  2. Made one logical change (rename backtesting → backtesting_old)
  3. Verified tests still pass: 138/138
  4. Committed with clear message
  5. Made second change (delete backtesting_old/)
  6. Verified tests still pass: 138/138
  7. Committed with clear message
  8. Made third change (delete legacy scripts)
  9. Verified tests still pass: 138/138
  10. Ready to commit

- **Why this matters:** 
  - Each checkpoint provides safety net
  - Can pinpoint exact change if something breaks
  - Git history preserves deleted code
  - 100% confidence in each step

- **Key insight:** "Delete with confidence, verify with discipline"

#### Lesson 2: Legacy Code Cleanup Strategy
**Context:** Found 5 legacy scripts importing deleted module
- **The right way:**
  1. Search for all imports: `grep_search(query="from backtesting|import backtesting", isRegexp=True)`
  2. Analyze each file (is it part of core system?)
  3. Verify none are in current test suite
  4. Delete all at once (they're related)
  5. Verify test suite still passes
  
- **Files deleted:**
  - `optimize_strategy.py` - used deleted optimizer
  - `run_backtest.py` - used deleted visualizer
  - `tests/test_risk_manager.py` - tested deleted component
  - `tests/test_performance_analytics.py` - tested deleted component
  - `tests/test_backtesting.py` - tested deleted module
  
- **Why delete instead of rewrite:** 
  - The retained canonical module was superior and complete
  - These were superseded, not complementary
  - Maintaining two implementations creates confusion
  - Can recreate if needed (git history preserved)

#### Lesson 3: Module Consolidation
**Context:** Had two overlapping directories causing import confusion
- **Problem indicators:**
  - Developers confused about which to import
  - Duplicate functionality
  - Import errors in new code
  
- **Solution:**
  - Keep the superior, complete implementation (backtest/)
  - Delete the legacy, incomplete implementation (backtesting/)
  - Update all imports (but in this case, old imports were in dead code)
  
- **Lesson:** "One authoritative implementation per concept"

#### Lesson 4: Git History as Safety Net
**Context:** Deleting 13 files totaling 3,000+ lines
- **Why we could delete confidently:**
  - All code preserved in git history (commits da9a714, 8206109)
  - Can retrieve if needed: `git show da9a714:backtesting_old/optimizer.py`
  - Clear commit messages document what was deleted and why
  
- **Best practices:**
  - Commit before major deletions
  - Write detailed commit messages
  - Reference commit hashes in documentation
  - Never force-push deleted code (preserve history)

### Sprint 4 Lessons Learned (November 25, 2025)

#### Lesson 1: Research APIs Before Writing Integration Tests
**Context:** Sprint 4 Task 1 - Writing 30 integration tests for existing components
- **What went wrong:**
  - Wrote 916 lines of integration tests based on assumed APIs
  - 37+ API mismatches discovered during test execution
  - Required 5 correction rounds to reach 100% pass rate
  - Issues: wrong imports, incorrect signatures, missing parameters, wrong attributes
  
- **Why it happened:**
  - Treated integration tests like unit tests (write, then implement)
  - Assumed APIs instead of researching actual implementations
  - No pre-test verification phase for existing code
  
- **The right way - API Research Protocol:**
  ```python
  # BEFORE writing integration tests for existing components:
  
  # 1. List all components you'll integrate
  components = [
      "strategy.lifecycle.StrategyLifecycle",
      "strategy.metrics_tracker.PaperMetricsTracker",
      "strategies.strategy_orchestrator.StrategyOrchestrator",
      # ... etc
  ]
  
  # 2. For EACH component, research its API:
  
  # Step 2a: Find existing tests (they show correct usage)
  grep_search(query="test.*StrategyLifecycle", includePattern="test_*.py")
  # Result: tests/test_strategy_lifecycle.py
  
  # Step 2b: Read the test file to see actual API usage
  read_file("tests/test_strategy_lifecycle.py")
  # Note: StrategyLifecycle(db_path, strategy_name)
  # Note: transition_to(state) returns bool
  # Note: get_current_state() returns LifecycleState
  
  # Step 2c: Find the implementation for ambiguous cases
  grep_search(query="class PaperMetricsTracker", includePattern="*.py")
  read_file("strategy/metrics_tracker.py", offset=line, limit=50)
  # Note: __init__(self, db_path: str, strategy_name: str, initial_capital: float)
  # Note: record_daily_snapshot(date, portfolio_value, cash, positions_value, daily_pnl)
  
  # Step 2d: Document findings in code comments
  # PaperMetricsTracker API:
  # - Constructor: (db_path, strategy_name, initial_capital)
  # - record_daily_snapshot(date, portfolio_value, cash, positions_value, daily_pnl) - 5 params
  # - record_trade(symbol, side, quantity, entry_price, exit_price, entry_time, exit_time)
  # - get_metrics_snapshot() -> MetricsSnapshot
  
  # 3. Create API reference comment block at top of test file
  # 4. NOW write integration tests using verified APIs
  # 5. Tests should pass on first full run (or have minimal fixes)
  ```

- **Time comparison:**
  - Our approach: 0 min research + 60 min writing + 120 min debugging = 180 min
  - Right approach: 30 min research + 60 min writing + 10 min fixes = 100 min
  - **Time saved: 44%** (plus less frustration)

- **How to avoid in future:**
  1. **Add "API Research Phase" before integration tests**
     - Mandatory for tests integrating 3+ existing components
     - Research each component's API from existing tests
     - Document findings in comment block
     - Verify ambiguous cases by reading implementation
  
  2. **Use existing tests as API documentation**
     - Passing tests show correct usage
     - More reliable than reading implementation directly
     - Shows actual parameter values and return types
  
  3. **Create API reference at top of integration test file**
     ```python
     """
     Integration Test Suite: End-to-End Workflows
     
     API Reference (verified from existing tests):
     
     StrategyLifecycle (from test_strategy_lifecycle.py):
     - Constructor: StrategyLifecycle(db_path: str, strategy_name: str)
     - transition_to(state: LifecycleState) -> bool
     - get_current_state() -> LifecycleState
     - get_history() -> List[StateTransition]
     
     PaperMetricsTracker (from test_metrics_tracker.py):
     - Constructor: PaperMetricsTracker(db_path, strategy_name, initial_capital)
     - record_daily_snapshot(date, pv, cash, pos_val, daily_pnl) - 5 params!
     - record_trade(sym, side, qty, entry_px, exit_px, entry_t, exit_t) - needs times!
     - get_metrics_snapshot() -> MetricsSnapshot (not get_summary!)
     
     ... (continue for all integrated components)
     """
     ```
  
  4. **Integration test writing checklist:**
     - [ ] Listed all components to integrate
     - [ ] Found existing tests for each component
     - [ ] Read existing tests to verify APIs
     - [ ] Documented API reference in comments
     - [ ] Verified ambiguous cases from implementation
     - [ ] Created fixtures matching verified signatures
     - [ ] Wrote tests using verified APIs only
     - [ ] Expected high first-run pass rate (80%+)

- **When this applies:**
  - Writing integration tests for existing components
  - Writing E2E tests across multiple modules
  - Adding tests to legacy code
  - Creating system-level test suites
  
- **When research is optional:**
  - Unit testing new code you just wrote (TDD)
  - Integration tests written alongside implementation
  - Tests for code you personally implemented recently

- **Key insight:** "For integration tests of existing code, research APIs first. 30 minutes of research saves 2 hours of debugging."

**Sprint 4 Task 1 Outcome:**
Despite the inefficient approach, we achieved:
- 30/30 integration tests passing (100%)
- 562/562 full test suite passing (100%)
- Comprehensive coverage of all Sprint 1-3 integration points
- Clean commit (11da7f4)

**Lesson learned:** API research phase is mandatory before writing integration tests. Add it to the Prime Directive.

---

### NRIC Verification Demo Lessons Learned (January 8, 2026)

#### Lesson 1: Tests Are Mandatory - Not Optional
**Context:** Made editable name field enhancement, broke JavaScript, committed without testing
- **What went wrong:**
  1. Modified HTML template to make name field editable
  2. Text replacement corrupted JavaScript code: `document.getElementById('timestavalue = data.name;`
  3. Committed broken code without testing
  4. Start Camera button completely broken on production
  5. User discovered the bug, not automated tests (embarrassing!)

- **Root cause:** 
  - **No test coverage existed** - project had zero tests
  - Made changes without running the application
  - Assumed text replacement was correct without verification
  - Violated Prime Directive Principle 1 (100% test pass rate) by having no tests at all

- **What should have been done:**
  1. ✅ Created test suite FIRST (test_app.py)
  2. ✅ Run tests before making changes (baseline)
  3. ✅ Make enhancement to HTML
  4. ✅ **Test manually** by running Flask app and clicking buttons
  5. ✅ **Run automated tests** after changes
  6. ✅ Verify 100% pass rate with zero warnings
  7. ✅ Only then commit

- **Consequences of no tests:**
  - Broke production functionality
  - Required immediate hotfix commit
  - Lost user confidence
  - Wasted time debugging obvious errors
  - **Could have been prevented with 1 minute of manual testing**

- **The fix process (doing it right):**
  1. Created comprehensive test suite (test_app.py)
  2. Added pytest to requirements.txt
  3. Wrote 23 tests covering:
     - All Flask routes (index, verify, error cases)
     - OCR extraction functions (name, NRIC patterns)
     - Integration workflows (complete verification)
     - Edge cases (invalid images, empty data)
     - Performance (response time under 5s)
  4. **All 23 tests passing** - proves code works
  5. Updated Prime Directive to mandate test creation

- **Test categories created:**
  - **Route tests** (4 tests): HTTP endpoints, error codes, response formats
  - **OCR function tests** (12 tests): Name extraction, NRIC parsing, edge cases
  - **Integration tests** (2 tests): Complete workflows, stateless verification
  - **Edge case tests** (4 tests): Invalid inputs, special characters, error handling
  - **Performance tests** (1 test): Response time verification

- **Key insight:** "Tests are not optional. Tests are not 'nice to have'. Tests are MANDATORY. They prevent embarrassing production bugs."

**Updated Prime Directive Requirements:**
- ❌ **Never make code changes without test coverage**
- ✅ **Write tests FIRST for new features (TDD)**
- ✅ **Add tests IMMEDIATELY when fixing bugs**
- ✅ **Run tests before AND after every code change**
- ✅ **Manual testing required for UI changes** (click the buttons!)
- ❌ **Never commit untested code** - tests prevent regressions

**Time comparison:**
- **Without tests (my mistake):** 10 min implement + 0 min test + 30 min debug + 15 min fix = 55 minutes + embarrassment
- **With tests (right way):** 10 min implement + 5 min manual test + 2 min fix + 30 min write tests = 47 minutes + confidence

**Lesson learned:** Create test suite FIRST. Test EVERY change. Manual + automated testing catches bugs before users do.

---



### Sprint 3 Lessons Learned (November 24-25, 2025)

#### Lesson 1: Dataclasses + Enums = Clean Architecture
**Context:** Implementing attribution system and health monitoring
- **What worked exceptionally well:**
  - Using dataclasses for data structures (AttributionBreakdown, HealthMetrics, HealthAlert)
  - Using Enums for type safety (AttributionMetric, AttributionPeriod, HealthStatus, AlertLevel)
  - Zero boilerplate, maximum clarity
  - Type hints everywhere = fewer bugs
  
- **Pattern that emerged:**
  ```python
  @dataclass
  class HealthMetrics:
      win_rate: float
      sharpe_ratio: float
      max_drawdown: float
      profit_factor: float
      
      def calculate_health_score(self) -> float:
          # Business logic in the dataclass
          return (self.win_rate * 0.25 + ...)
  ```
  
- **Benefits realized:**
  - Tests are easier to write (clear data creation)
  - Serialization built-in (to_dict/from_dict)
  - Type checking catches errors at development time
  - Self-documenting code structure
  
- **Key insight:** "Dataclasses + Enums create self-documenting, type-safe architectures"

#### Lesson 2: Statistical Analysis Requires Domain Knowledge
**Context:** Implementing degradation detection with linear regression
- **Challenge:** Detecting performance degradation in real-time
- **Solution approach:**
  1. Use Python's `statistics` module (built-in, tested, reliable)
  2. Simple linear regression for trend analysis
  3. Sliding window approach (deque with maxlen)
  4. Configurable thresholds (lookback_window=20, threshold=20%)
  
- **Why simple approach won:**
  - Linear regression is interpretable (operators understand slope)
  - Built-in statistics module is battle-tested
  - Configurable parameters allow tuning per strategy
  - No external ML dependencies needed
  
- **What to avoid:**
  - Overly complex ML models for simple trend detection
  - Black-box algorithms operators can't understand
  - External dependencies when built-ins suffice
  
- **Key insight:** "Use simplest statistical method that solves the problem - interpretability matters"

#### Lesson 3: TDD Accelerates Complex Feature Development
**Context:** Each Sprint 3 task started with comprehensive test file first
- **Pattern that worked:**
  1. Write comprehensive test file (~500-600 lines, 30-35 tests)
  2. Run tests (they all fail, as expected)
  3. Implement features to make tests pass
  4. All tests pass on first full run!
  
- **Sprint 3 Results:**
  - Task 1 (Config Hot-Reload): 35/35 tests passing immediately
  - Task 2 (Multi-Strategy Orchestration): 35/35 tests passing immediately
  - Task 3 (Strategy Comparison): 34/34 tests passing immediately
  - Task 4 (Performance Attribution): 35/35 tests passing immediately
  - Task 5 (Health Monitoring): 35/35 tests passing immediately
  
- **Why TDD worked so well:**
  - Tests define exact requirements
  - No ambiguity about "done"
  - Implementation is guided by tests
  - Refactoring is safe (tests catch breaks)
  - Zero debugging time wasted on "what's wrong?"
  
- **Time savings:**
  - Without TDD: Implement → Debug → Fix → Test → Debug → Fix (iterative, slow)
  - With TDD: Test → Implement → Done (linear, fast)
  - Sprint 3: 174 tests in 3 tasks, minimal debugging
  
- **Key insight:** "TDD isn't slower - it eliminates debugging time and makes 'done' unambiguous"

#### Lesson 4: Comprehensive Fixtures Enable Fast Testing
**Context:** Creating realistic test data for attribution and comparison
- **Pattern discovered:**
  ```python
  @pytest.fixture
  def sample_trades():
      """Create realistic trade data once, use everywhere"""
      return [
          TradeAttribution(symbol="AAPL", pnl=150, entry=100, exit=115, ...),
          TradeAttribution(symbol="MSFT", pnl=-50, entry=200, exit=195, ...),
          # 10+ realistic trades covering various scenarios
      ]
  ```
  
- **Benefits:**
  - Tests are concise (just use fixture)
  - Realistic data = realistic test scenarios
  - Consistent data across tests = reproducible
  - Easy to add edge cases (add to fixture)
  
- **What we avoided:**
  - Duplicating test data in every test
  - Unrealistic data (all trades winning, perfect patterns)
  - Inconsistent data across tests
  
- **Key insight:** "Comprehensive fixtures with realistic data make tests faster to write and more reliable"

#### Lesson 5: Format Reports for Human Consumption
**Context:** Building comparison dashboard and attribution reports
- **What made reports valuable:**
  1. **Visual elements:** Sparklines (▁▂▃▄▅▆▇█) show trends instantly
  2. **Color coding:** Green/yellow/red = instant status assessment
  3. **Rankings:** 🥇🥈🥉 make comparisons clear
  4. **Bar charts:** ASCII bars (████░░░░) show proportions visually
  5. **Formatted tables:** Aligned columns with proper borders
  
- **Example that worked:**
  ```
  ╔══════════════════════════════════════════╗
  ║ Performance Attribution Report           ║
  ║ Momentum_Agg   $3,200  42.7%  ████████  ║
  ║ MA_Cross_Cons  $2,500  33.3%  ██████    ║
  ╚══════════════════════════════════════════╝
  ```
  
- **Why formatting matters:**
  - Operators scan reports quickly
  - Visual patterns recognized faster than numbers
  - Well-formatted reports get read, ugly ones get ignored
  - Terminal-based works everywhere (no UI needed)
  
- **Key insight:** "Reports are for humans - format them for human consumption with visual elements"

#### Lesson 6: Edge Case Testing Prevents Production Bugs
**Context:** Testing with empty data, single items, boundary conditions
- **Edge cases we tested every time:**
  1. Empty collections (no trades, no metrics)
  2. Single item collections (1 trade, 1 strategy)
  3. Boundary values (exactly 0, exactly at threshold)
  4. None/missing data (optional fields)
  5. Invalid inputs (negative values, bad types)
  
- **Bugs caught by edge case testing:**
  - Division by zero when no trades
  - Index errors with single strategy
  - Health score calculation with missing metrics
  - Comparison sorting with equal values
  
- **Time to find these in production:** Hours or days  
  **Time to find in tests:** Seconds
  
- **Pattern that worked:**
  ```python
  # For every feature test, add edge cases:
  def test_feature_with_empty_data():
      result = feature([])
      assert result == expected_for_empty
      
  def test_feature_with_single_item():
      result = feature([single_item])
      assert result == expected_for_one
  ```
  
- **Key insight:** "Edge case tests catch production bugs before they happen - write them every time"

#### Lesson 7: Integration Tests Validate Complete Workflows
**Context:** Testing full workflow from data → orchestrator → attribution → monitoring
- **Integration test pattern:**
  ```python
  def test_complete_workflow():
      # 1. Set up multi-strategy orchestrator
      orchestrator = StrategyOrchestrator(...)
      orchestrator.register_strategy(strategy1, allocation=0.5)
      orchestrator.register_strategy(strategy2, allocation=0.5)
      
      # 2. Feed market data
      orchestrator.on_market_data(market_data)
      
      # 3. Generate signals
      signals = orchestrator.collect_signals()
      
      # 4. Execute trades
      orchestrator.execute_signals(signals)
      
      # 5. Calculate attribution
      attribution = orchestrator.get_attribution()
      
      # 6. Check health
      health = orchestrator.get_health_status()
      
      # 7. Verify complete chain worked
      assert all components worked correctly
  ```
  
- **What integration tests caught:**
  - Signal conflicts between strategies
  - Attribution tracking gaps
  - Health metrics not updating
  - Dashboard rendering errors
  
- **Coverage strategy:**
  - Unit tests: Individual components (80% of tests)
  - Integration tests: Complete workflows (20% of tests)
  - System tests: End-to-end scenarios (manual initially)
  
- **Key insight:** "Integration tests catch interaction bugs that unit tests miss - include them in every sprint"

#### Lesson 8: Commit Frequently with Descriptive Messages
**Context:** Sprint 3 had 5 commits (one per task)
- **Commit pattern that worked:**
  ```
  Task N: Feature Name (X tests passing)
  
  Implementation: Key classes and features
  Tests: Coverage breakdown
  Results: Test counts and status
  ```
  
- **Benefits:**
  - Clear project history
  - Easy to find when features were added
  - Test counts show progress
  - Can bisect bugs if needed
  - Documentation in git log
  
- **What we avoided:**
  - Huge commits with multiple features
  - Vague messages ("updates", "fixes")
  - Committing broken code
  
- **Sprint 3 commit history:**
  - Task 1: c9b5cbb (35 tests)
  - Task 2: c9b5cbb (35 tests, same commit)
  - Task 3: 2e009ab (34 tests)
  - Task 4: b24c48f (35 tests)
  - Task 5: 0f45bc7 (35 tests)
  
- **Key insight:** "Commit after each complete task with descriptive message and test count"

#### Lesson 9: Maintain 100% Pass Rate Through Every Change
**Context:** 532 tests maintained throughout Sprint 3
- **Verification discipline:**
  - Before Task 1: 393/393 tests passing
  - After Task 1: 428/428 tests passing ✓
  - After Task 2: 463/463 tests passing ✓
  - After Task 3: 497/497 tests passing ✓
  - After Task 4: 532/532 tests passing ✓
  - After Task 5: 532/532 tests passing ✓
  
- **What this prevented:**
  - Regressions in existing features
  - Integration breakage
  - Accumulated technical debt
  - "Fix it later" mentality
  
- **Time cost:** 30-60 seconds per verification  
  **Time saved:** Hours of debugging regressions
  
- **Key insight:** "Full test suite verification after every change is the cheapest insurance against regressions"

#### Lesson 10: Deque for Efficient Sliding Windows
**Context:** Health monitoring needs sliding window of recent metrics
- **Problem:** Need last N metrics, update frequently
- **Bad solution:** List with append + slice
  ```python
  self.metrics.append(new_metric)
  self.metrics = self.metrics[-window_size:]  # Creates new list every time!
  ```
  
- **Good solution:** Deque with maxlen
  ```python
  from collections import deque
  self.metrics = deque(maxlen=window_size)  # Auto-evicts oldest
  self.metrics.append(new_metric)  # O(1), no slicing needed
  ```
  
- **Performance difference:**
  - List approach: O(n) for every append (creates new list)
  - Deque approach: O(1) for every append (just updates pointers)
  - With 1000 appends of 100-item window: 100x faster with deque
  
- **Other deque benefits:**
  - Thread-safe operations
  - Memory efficient (no temporary lists)
  - Cleaner code (maxlen handles eviction)
  
- **Key insight:** "Use deque with maxlen for sliding windows - it's built for this use case"

### Sprint 2 Lessons Learned (November 22-24, 2025)

#### Lesson 1: Multi-Dimensional Validation is Essential
**Context:** Implementing paper trading validation criteria
- **What we learned:**
  - Single metrics (Sharpe ratio alone) are insufficient
  - Need validation across 7+ dimensions: time, volume, risk-adjusted returns, drawdown, win rate, profit factor, consecutive losses
  - A strategy with high Sharpe but only 5 trades is not validated
  - Time-based validation (30+ days) is non-negotiable
  
- **Why this matters:**
  - Multiple criteria provide confidence in strategy robustness
  - Prevents overfitting and false positives
  - Ensures statistical significance
  
- **Key insight:** "Validate strategies across all dimensions, not just one metric"

#### Lesson 2: Two-Layer Risk Management
**Context:** Real-time risk monitoring integration
- **The right way:**
  1. **Pre-trade checks (blocking):** Validate before order submission
     - Check position size limits
     - Check portfolio heat
     - Check concentration risk
     - REJECT order if any limit would be exceeded
  
  2. **Post-trade monitoring (continuous):** Recalculate after fills
     - Update portfolio metrics after every fill
     - Detect accumulated risk from multiple fills
     - Alert or pause if thresholds crossed
     
- **Why both layers matter:**
  - Pre-trade stops problems before they start
  - Post-trade catches issues from multiple fills accumulating
  - Two-layer defense prevents risk limit violations
  
- **Key insight:** "Both layers are necessary for robust risk management"

#### Lesson 3: Database Persistence for Validation
**Context:** Tracking metrics for 30+ day validation period
- **Why database over in-memory:**
  - In-memory tracking loses data on restart
  - Validation requires persistent time-series data
  - Historical performance matters for approval decisions
  - Audit trail must survive system restarts
  
- **Schema design that worked:**
  ```sql
  -- Separate tables for different data types
  strategy_metrics        -- Current aggregated metrics
  strategy_snapshots      -- Daily time-series data
  strategy_trades         -- Individual trade records
  approval_history        -- Complete audit trail
  ```
  
- **Why this design:**
  - Fast queries for current status
  - Historical analysis from snapshots
  - Trade-by-trade review when needed
  - Complete audit trail for accountability
  
- **Key insight:** "Critical validation data must persist in database"

#### Lesson 4: Visual Feedback Increases Operator Confidence
**Context:** Building validation dashboard with sparklines and progress bars
- **What worked well:**
  - Progress bars for percentage completion (clear visual of status)
  - Sparklines for time-series trends (instant pattern recognition)
  - Color coding green/yellow/red (quick status assessment)
  - Composite health scores 0-100 (complex metrics simplified)
  - Action-required notifications (next steps obvious)
  
- **User feedback:**
  - "I can see exactly where the strategy stands"
  - "Progress bars make it clear what's needed"
  - "Sparklines give instant visual feedback"
  
- **Why it matters:**
  - Operators need confidence before approving live trading
  - Visual feedback reduces cognitive load
  - Clear next-action guidance prevents mistakes
  
- **Key insight:** "Visual dashboard features increase operator confidence and reduce errors"

#### Lesson 5: Multi-Gate Approval Prevents "Skip to Live"
**Context:** Implementing strategy promotion workflow
- **Human nature problem:** "This strategy looks good, let's go live now!"
- **Solution: Multi-gate approval**
  ```
  PAPER → (auto validation) → VALIDATED → (manual approval) → LIVE_APPROVED → (final confirm) → LIVE_ACTIVE
  Gate 1: Automated          Gate 2: Manual            Gate 3: Final
  ```
  
- **Why multiple gates:**
  - Prevents emotional decision-making
  - Forces thorough review of all criteria
  - Creates audit trail for accountability
  - Provides multiple "think about it" moments
  - No direct path from PAPER to LIVE possible
  
- **Checklist enforcement:**
  - Strategy code reviewed
  - Risk parameters verified
  - Position sizing confirmed
  - Emergency procedures tested
  - Monitoring alerts configured
  - All items must be checked before approval
  
- **Key insight:** "Never allow direct path from paper to live - require human approval with checklist"

#### Lesson 6: Incremental Testing Catches Issues Early
**Context:** Building complex metrics calculations (Sharpe ratio, drawdown tracking)
- **Sprint 2 approach that worked:**
  ```
  Task 2: Metrics Tracker
  1. Wrote database schema → tested persistence ✓
  2. Wrote trade recording → tested calculation ✓
  3. Wrote Sharpe ratio → tested with known data ✓
  4. Wrote drawdown tracking → tested edge cases ✓
  5. Integrated all → tests already passing! ✓
  ```
  
- **Why this approach worked:**
  - Early bug detection = easy fixes
  - Confident integration when components tested
  - Faster overall development (less debugging time)
  - Each test provides safety net for next component
  
- **What to avoid:**
  - Writing 500 lines before testing = debugging nightmare
  - "I'll test it all at the end" = technical debt accumulation
  
- **Key insight:** "Test components in isolation first, integration should 'just work'"

#### Lesson 7: Test Quality > Test Quantity
**Context:** 393 tests with 37% overall coverage
- **What we learned:**
  - High test count doesn't guarantee quality
  - Coverage should match criticality of code
  - Risk-critical code needs near-100% coverage
  - Integration code can rely on manual testing initially
  
- **Sprint 2 coverage where it matters:**
  - strategy/lifecycle.py: 97% ✅
  - strategy/metrics_tracker.py: 99% ✅
  - strategy/validation.py: 96% ✅
  - execution/risk_monitor.py: 95% ✅
  
- **Intentionally lower coverage:**
  - tws_client.py: 0% (TWS integration, manual testing initially)
  - Legacy scripts: 0% (will be replaced)
  
- **Key insight:** "Focus on edge cases and error conditions in critical code, not just happy path coverage"

#### Lesson 8: Velocity Compounds with Strong Foundation
**Context:** Sprint 2 velocity 64% faster than Sprint 1
- **Why velocity increased:**
  - Foundation from Sprint 1 enabled faster Sprint 2 work
  - Established patterns reduced decision time
  - Clear requirements from Sprint plan
  - Test-first approach prevented rework
  - Team learning curve effect
  
- **Metrics:**
  - Sprint 1: 33 tests/day
  - Sprint 2: 54 tests/day
  - Increase: 64%
  
- **Key insight:** "Invest in strong foundation early, velocity compounds over time"

#### Lesson 9: Zero Tolerance for Warnings (November 24, 2025)
**Context:** SQLAlchemy deprecation warning discovered in test output
- **The Warning:**
  ```
  MovedIn20Warning: The declarative_base() function is now available as
  sqlalchemy.orm.declarative_base(). (deprecated since: 2.0)
  ```

- **Why it matters:**
  - Deprecation warnings become breaking errors in future versions
  - "Just warnings" create technical debt that compounds
  - Warnings mask real issues in test output noise
  - Future-proofing requires addressing deprecations immediately
  
- **The Fix:**
  - Changed: `from sqlalchemy.ext.declarative import declarative_base`
  - To: `from sqlalchemy.orm import declarative_base, relationship`
  - Result: Zero warnings, SQLAlchemy 2.0+ compliant
  
- **Policy Established:**
  - All warnings must be investigated immediately when they appear
  - Zero warnings required before committing (not just zero failures)
  - Warnings are treated with same urgency as test failures
  - Document warning count in commit messages (e.g., "393 passed, 0 warnings")
  
- **Why zero tolerance:**
  - Clean test output makes real issues immediately visible
  - Prevents "warning fatigue" where important warnings get ignored
  - Keeps codebase modern and maintainable
  - Eliminates future breaking changes proactively
  
- **Key insight:** "Warnings are errors waiting to happen - fix them immediately, don't defer to later"

### Historical Lessons (Legacy Project) - Day 3

_Note: This section is retained as historical reference from a prior project. The verification discipline applies broadly across projects._

#### Error 1: TimeFrame.DAILY
- **What happened:** Used `TimeFrame.DAILY` without checking enum
- **Why:** Assumed naming convention
- **Fix:** Check enum source, use `TimeFrame.DAY_1`
- **Lesson:** Never assume enum values - always verify

#### Error 2: on_bar(symbol, bar)
- **What happened:** Wrong method signature for Strategy.on_bar()
- **Why:** Didn't check base class abstract method
- **Fix:** Use correct signature `on_bar(market_data)`
- **Lesson:** Always check base class/interface signatures

#### Error 3: market_data.symbol
- **What happened:** Accessed `.symbol` (singular) instead of `.symbols` (plural)
- **Why:** Assumed single symbol, didn't inspect class
- **Fix:** Use `.symbols` list and iterate
- **Lesson:** Inspect data structure before accessing attributes

#### Error 4: buy(symbol, qty, "reason")
- **What happened:** Passed string as third parameter instead of OrderType enum
- **Why:** Misread method signature
- **Fix:** Use `OrderType.MARKET` enum
- **Lesson:** Check parameter types, not just parameter names

#### Error 5: position <= 0
- **What happened:** Compared None to int, causing TypeError
- **Why:** Didn't handle None return value
- **Fix:** Use `position or 0` to default None to 0
- **Lesson:** Check if methods return Optional types

---

## 📝 Quick Reference Template

Add this comment block at the top of new files:

```python
"""
Quick Reference for this module:

Key Classes:
- ClassName: .attribute1 (type), .method1(params) -> return_type

Important Enums:
- EnumName: VALUE_1, VALUE_2, VALUE_3

Common Patterns:
- Pattern 1: description
- Pattern 2: description

Gotchas:
- Thing that returns None - handle it!
- Attribute is plural (.symbols not .symbol)
- Use EnumType not string
"""
```

---

## 🚀 Integration Best Practices

### When Integrating New Code

1. **Start Simple**
   - Minimal working example first
   - One feature at a time
   - Verify each step

2. **Incremental Integration**
   ```python
   # ✅ Add one component at a time
   # Step 1: Add data loading only
   # Step 2: Add strategy initialization
   # Step 3: Add execution logic
   # Step 4: Add analytics
   ```

3. **Verify At Each Step**
   - Run tests after each addition
   - Check for warnings (they matter!)
   - Fix issues before proceeding

4. **Don't Skip Testing**
   - "I'll test it later" = technical debt
   - Test as you go
   - Automated tests > manual testing

---

## 🎯 Success Metrics

### Before Considering Code "Done"

- [ ] All unit tests passing (100%) - baseline verified with 0 warnings
- [ ] All unit tests passing (100%) - after changes verified with 0 warnings
- [ ] Zero compiler/linter warnings (all investigated and fixed)
- [ ] Zero test warnings (deprecations, type issues, etc. all resolved)
- [ ] No None-type errors
- [ ] All edge cases handled
- [ ] Code reviewed (by peer or self)
- [ ] Documentation complete
- [ ] Integration tested
- [ ] Performance acceptable
- [ ] Git commit with clear message including warning count

### Definition of "Done"

Code is only done when:
1. ✅ Baseline tests verified (before changes): X passed, 0 warnings
2. ✅ Changes implemented
3. ✅ Tests pass after changes (verify again): X passed, 0 warnings
4. ✅ Zero warnings (all warnings investigated and resolved)
5. ✅ Error handling complete
6. ✅ Integrated and verified
7. ✅ Documented
8. ✅ Committed with test count AND warning count (e.g., "393 passed, 0 warnings")

### Deletion Protocol (Additional Requirements)

When deleting code:
1. ✅ Verify baseline tests pass
2. ✅ Search for all usages: `grep_search(query="module_name", isRegexp=True)`
3. ✅ Analyze impact (is it in test suite? imported elsewhere?)
4. ✅ Delete in logical groups (related files together)
5. ✅ Verify tests still pass after deletion
6. ✅ Commit with detailed message explaining what and why
7. ✅ Reference commit hash in documentation if significant
8. ✅ Never force-push (preserve git history)

---

### 14. **Periodic Test Coverage Audit - Prevent Silent Gaps**

**CRITICAL:** New modules can accumulate without smoke tests if the Module → Smoke Test Hard Rule
(Principle 1) is not enforced in every commit. This principle adds a **scheduled safety net**.

**Audit Trigger:**
Run a coverage audit at the **start of every 5th session** or after **any session that introduces
three or more new modules** in a batch.

**Audit Procedure (5 minutes max):**
```powershell
# Step 1: List all modules that require smoke tests
Get-ChildItem app/routes/*.py, app/services/*.py | Where-Object { $_.Name -ne '__init__.py' } | Select-Object Name

# Step 2: List existing smoke test files
Get-ChildItem tests/smoke_*.py | Select-Object Name

# Step 3: Identify gaps (module without matching smoke_<module>.py)
# Any module in Step 1 with no matching file in Step 2 is a gap.
# Gaps MUST be closed before new feature work begins.
```

**Audit Output Example:**
```
Modules requiring coverage:   auth, export, generate, tsc, ai_handler, excel_gen,
                              mapper, tsc_service, validators
Smoke tests present:          smoke_auth, smoke_export, smoke_generate, smoke_tsc,
                              smoke_excel_gen, smoke_mapper, smoke_tsc_service,
                              smoke_validators
Gaps:                         ai_handler  <-- must create tests/smoke_ai_handler.py
```

**Rule: No new feature work until all audit gaps are closed.**

**Gap Closure Protocol:**
1. For each gap, create `tests/smoke_<module>.py` covering:
   - All exported functions/classes
   - Happy path for each function
   - At least one error/edge case per function
2. Run `tests/run_all_smoke.py` — must pass before proceeding
3. Commit the new smoke tests with message: `test: add smoke tests to close coverage audit gaps`

**Why a Scheduled Audit Is Needed (Root Cause):**
During the March 2026 session, four modules (`auth`, `export`, `validators`, `mapper`) had
been live without smoke tests across multiple sessions. The gap was only discovered when
an explicit audit was triggered by a human question — not by any automated enforcement.
The Module → Smoke Test Hard Rule prevents new gaps; this Principle prevents historic gaps
from persisting indefinitely.

**Session Log Integration:**
Record the audit result in `session_log.md` as a checkpoint entry with type `audit`:
```markdown
## Audit Checkpoint
- Type: audit
- Modules checked: 9
- Gaps found: 0 (or list gaps)
- Gaps closed: n/a (or list files created)
- KPI delta: Coverage gate now green
```

**❌ Never:**
- Begin new feature implementation if an audit gap is known
- Skip the audit because "we've been careful"
- Close the audit by deleting the module instead of writing the test

**✅ Always:**
- Run the audit at the scheduled cadence (every 5th session)
- Close all gaps before proceeding with new work
- Record audit outcome in `session_log.md`
- Run `tests/run_all_smoke.py` to confirm 0 failures after closing gaps

---

## 🤝 Team Expectations

### For All Team Members (Human & AI)

1. **Read this document before starting work**
2. **Follow the checklist - every time**
3. **Ask questions if unsure - don't guess**
4. **Test incrementally - don't batch**
5. **Fix errors immediately - don't defer**
6. **Document learnings - update this file**

### For AI Agents Specifically

1. **Always use verification tools before implementing**
   - `grep_search`, `read_file`, `list_code_usages`
2. **Never assume - always verify**
3. **Test each component before moving on**
4. **Read error messages completely and act on them**
5. **Keep implementations simple initially**
6. **Ask for clarification if requirements are ambiguous**

### For Code Reviewers

1. **Check that verification was done**
   - Were existing patterns checked?
   - Were types validated?
2. **Look for None handling**
3. **Verify test coverage**
4. **Ensure error handling present**
5. **Confirm documentation exists**

---

## 📚 Resources

### Internal Documentation
- `README.md` - Project overview
- `session_log.md` - Session-level compliance log and KPI checkpoints
- `tests/` - Living examples of expected behavior and usage patterns
- Test files - Living examples of correct usage

### When in Doubt
1. Check existing tests - they show correct usage
2. Use `grep_search` to find patterns
3. Read the source code - it's the truth
4. Ask the team - collaboration over guessing

---

## 🔄 Document Maintenance

### When to Update This Document

- After encountering a new type of error
- When establishing a new pattern
- After team retrospectives
- When tooling changes
- Quarterly review minimum

### How to Update

1. Add specific examples
2. Keep it practical, not theoretical
3. Include code snippets
4. Update "Lessons Learned" section
5. Date the changes

---

## 💡 Remember

> **"100% test pass rate with zero warnings is not a goal - it's a requirement."**

> **"Warnings are errors waiting to happen - fix them immediately."**

> **"The best code is code that works correctly the first time because you took the time to verify before implementing."**

> **"Tests are not overhead - they're proof your code works."**

> **"Defensive programming isn't paranoia - it's professionalism."**

> **"Delete with confidence when you verify with discipline."**

> **"One authoritative implementation per concept - no duplicates."**

> **"Zero tolerance for warnings = zero technical debt from ignored issues."**

---

### Legacy Metrics Archive (Reference Only)

The detailed sprint and module metrics below this directive were originally captured from a prior project phase and are retained as historical context only.

For current project status and auditable checkpoints, use:
- `session_log.md` for live KPI and test execution cadence
- Local test output (`pytest`) for authoritative test and warning counts in this repository

---

## 📌 Summary: Key Takeaways

### The Core Truth
**"100% backend tests passing ≠ working application"**
- Backend tests verify logic correctness
- Manual testing verifies user experience
- Both required for UI changes

### The Five Principles (In Order)
0. **Virtual Environment First** - Always verify before running commands
1. **100% Test Pass + Zero Warnings** - Non-negotiable baseline
2. **Verify First, Code Second** - Research existing code before changing
3. **Defensive Programming** - Handle None, validate inputs, check bounds
4. **Test Incrementally** - Build and verify in small steps
5. **Manual UI Testing** - Required for any HTML/CSS/JS changes

### The Critical Workflow

**For Backend Changes:**
```bash
1. ✅ Verify venv active
2. ✅ Run baseline tests
3. 🔧 Make changes
4. ✅ Run tests again
5. ✅ All pass → Commit
```

**For UI Changes:**
```bash
1. ✅ Verify venv active
2. ✅ Run baseline tests
3. 🔧 Make changes (HTML/CSS/JS)
4. ✅ Run backend tests
5. 👁️ Manual smoke test (2-5 min)
6. 👁️ Check browser console (F12)
7. 👁️ Test critical flows
8. ✅ All pass → Document manual testing → Commit
```

### The Most Common Mistakes
1. ❌ Skipping manual testing for "small" UI changes
2. ❌ Assuming backend tests catch UI bugs
3. ❌ Not checking browser console for errors
4. ❌ Deploying without actually clicking buttons
5. ❌ Ignoring warnings ("they're just warnings")

### The Cost of Shortcuts
- Skip 2-minute manual test → Spend 45+ minutes debugging
- Ignore warnings → Breaking changes in future versions
- Assume without verifying → Hours fixing wrong implementation
- Make multiple changes → Can't identify what broke

### The Discipline That Pays Off
- Manual testing every UI change → Catch 90% of bugs before deployment
- Zero warnings policy → Clean, maintainable codebase  
- Incremental testing → Fast debugging, clear git history
- Research APIs first → 44% reduction in debugging time

### Remember
> "It's not exactly reassuring that the initial set of tests still let this issue happen"

Tests are tools, not guarantees. The best test is actually using your application.

---

## 🌐 Hosted Deployment Addendum (New)

### Why This Exists
Cloud hosting introduces new failure modes that local tests cannot catch:
- Dependency install failures (large ML packages, GPU/CUDA wheels)
- Incompatible library versions in managed runtimes
- Missing system binaries (ffmpeg, etc.)
- Cold-start latency and model download behavior

### Mandatory Hosted Checks

1. **Verify dependency install logs** after any dependency change
  - Look for failed installs, version conflicts, or large GPU wheel downloads
  - If install fails, prefer lighter dependencies or explicit pins

2. **Pin compatibility-sensitive libraries**
  - If a library depends on a specific `transformers` API, pin it
  - Document the reason in commit message or session log

3. **Prefer lightweight fallbacks for hosted reliability**
  - If ML dependencies break hosting, use a simpler fallback that keeps the app running
  - You can move heavier ML to a separate hosted API later

4. **System dependencies must be declared**
  - For Streamlit Cloud, use `packages.txt` (e.g., `ffmpeg`)
  - For other hosts, add platform-specific install docs

### Hosted Smoke Test (Required)

- Deploy and run a full end-to-end flow in the hosted environment
- Verify:
  - App starts without install errors
  - Upload works
  - Transcription returns
  - Downloads succeed
  - Any optional features (punctuation, timestamps) work or fall back cleanly

---

## ♻️ Stack Profile (Streamlit) - Optional

Streamlit reruns the script on most UI interactions. This can retrigger expensive work unless you explicitly cache.

**Mandatory rule for heavy work (transcription, conversion, model downloads):**
- Use `st.session_state` to cache results keyed by input content
- Use `st.cache_resource` for heavyweight model initialization
- Never re-run transcription on download button clicks

**Checklist for Streamlit apps:**
- [ ] Expensive work is cached by input hash
- [ ] Model initialization uses `st.cache_resource`
- [ ] Download buttons do not re-trigger heavy computation

---

### Code Quality Standards (Target State)
✅ No duplicate implementations for the same behavior
✅ 100% test pass rate maintained before and after changes
✅ Zero warnings maintained (all warnings investigated and resolved)
✅ Clear git history with detailed commit messages
✅ Zero breaking changes to existing user-critical workflows
✅ TDD or immediate regression-test coverage for bug fixes and new logic

---

## 🔧 Git Best Practices - Tool Selection & Encoding

### ⚠️ PowerShell Unicode Encoding Issues

**The Problem:**
PowerShell has known issues with Unicode character handling when used with shell redirection (`2>&1`).
Commit messages with special characters (✓, ✗, →, •, etc.) cause:
```
git : To https://github.com/user/repo.git
At line:XX char:YY
    + CategoryInfo          : NotSpecified (To https://github.com/...):String) [], RemoteException
    + FullyQualifiedNameId : NativeCommandError
```

**The Reality:**
- The error is **cosmetic only** - the git command still succeeds
- Commits are pushed successfully despite the error message
- But the error message creates confusion and looks unprofessional

---

### ✅ Solution 1: Use ASCII-Only Commit Messages (Recommended for all projects)

**Why this is the best approach:**
- Works everywhere (PowerShell, Git Bash, macOS, Linux)
- Professional appearance
- No encoding issues ever
- Commits are readable in all tools

**Update to commit format (v7):**

```markdown
Pre-Commit Checklist - Updated Format:

Commit Message Format:
  <type>: <description>
  
  <body with details>
  
  Backend Tests: X/X passed, 0 warnings [PASS]
  Manual Testing: [PASS] (for UI changes only)
    - [What you tested]
    - [Results]

Approved ASCII replacements:
  [PASS]  == previously ✓
  [FAIL]  == previously ✗
  [OK]    == previously ✓
  [DONE]  == previously ✓
  [TODO]  == previously ?
  [WAIT]  == previously ⏳
  ->      == previously →
  -       == previously •
```

**Example commits (updated format):**
```bash
# ✅ Good - ASCII only
git commit -m "feat: implement PDF export module

- Created core/pdf_export.py with export_mom_pdf() function
- Uses reportlab for monospaced text rendering
- Returns raw PDF bytes for Flask send_file() compatibility

Backend Tests: 151/151 passed, 0 warnings [PASS]"


# ❌ Avoid - Unicode characters
git commit -m "feat: implement PDF export module ✓"
```

---

### ✅ Solution 2: Use Git Bash (Recommended for development)

**Why Git Bash is better for git operations:**
- Native Unicode support (no encoding issues)
- Standard shell syntax works everywhere
- Part of Git for Windows installation
- No configuration needed
- More reliable than PowerShell for git

**How to use Git Bash:**

1. **Install Git for Windows** (if not already installed)
   - Download: https://git-scm.com/download/win
   - Installation includes Git Bash

2. **Open Git Bash** instead of PowerShell for git operations
   - Right-click in Explorer: "Git Bash Here"
   - Or launch from Start Menu: "Git Bash"

3. **Use standard bash commands:**
   ```bash
   cd "/c/Users/evanl/Documents/development workspace/clearmeet"
   git add -A
   git commit -m "feat: add PDF export [PASS]"
   git push origin main
   ```

4. **No Unicode issues** - Git Bash handles all characters correctly

**Comparison:**

| Task | PowerShell | Git Bash |
|------|-----------|----------|
| ASCII commits | ✅ Works | ✅ Works |
| Unicode commits | ❌ Errors shown | ✅ Works perfectly |
| Standard shell syntax | ⚠️ Different | ✅ Standard |
| Line continuation | Semicolon (;) | Backslash (\) |
| Feel | Windows-specific | Universal |

---

### ✅ Solution 3: Configure PowerShell for UTF-8 (Advanced)

If you must use PowerShell, add UTF-8 support to your profile:

```powershell
# Edit your PowerShell profile
# Usually at: C:\Users\USERNAME\Documents\PowerShell\profile.ps1

# Add these lines
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$env:PYTHONIOENCODING = 'utf-8'
```

**Limitation:** Even with this, PowerShell's shell redirection (`2>&1`) can still cause issues. Better to avoid relying on this.

---

### 🎯 Project Profile Example (Windows): Git Bash as Team Standard

**Effective immediately (February 19, 2026):**

For teams that adopt this profile, Git Bash is the required git tool for development on Windows.

**Why Git Bash is a strong team standard for Windows projects:**
- ✅ **Zero cosmetic errors** - No confusing error messages during commits
- ✅ **Professional appearance** - Clean git history without artifacts
- ✅ **Universal compatibility** - Works across all operating systems and environments
- ✅ **Culture of quality** - Demonstrates commitment to "no eyesores" philosophy
- ✅ **Team consistency** - Everyone uses the same tool, same experience
- ✅ **Future-proof** - Avoids PowerShell issues entirely, no workarounds needed
- ✅ **Built into Git** - No additional setup beyond standard Git for Windows

**This standard means:**
- When performing git operations (add, commit, push, pull, etc.), use Git Bash
- PowerShell remains useful for runtime and automation tasks
- Git operations are standardized in Git Bash for consistency
- This is a team commitment to quality, not an arbitrary restriction

---

### 📋 Setup Guide: Switching to Git Bash

**For contributors using this profile:**

1. **Verify Git for Windows is installed**
   ```powershell
   # In PowerShell, check git version
   git --version
   # Should show: git version 2.x.x.windows.1
   ```

2. **Locate Git Bash**
   - **Option A:** Right-click in Windows Explorer → "Git Bash Here"
   - **Option B:** Start Menu → Search "Git Bash" → Launch
   - **Option C:** From any terminal: `"C:\Program Files\Git\bin\bash.exe"`

3. **Set up Git Bash as your default for repo operations**
   - Create desktop shortcut to Git Bash pointing to the project folder
   - Or: Open Git Bash → `cd` to project folder → keep it open during development

4. **Daily workflow (Updated):**

   ```powershell
   # PowerShell - Python/Flask operations
   .\Scripts\Activate.ps1
   python app.py
   python -m pytest
   ```

   ```bash
   # Git Bash - Git operations (NOT PowerShell)
   cd /c/Users/evanl/Documents/development\ workspace/clearmeet
   git add README.md
   git commit -m "docs: update audio upload security [PASS]"
   git push origin main
   ```

5. **Avoid PowerShell for git operations**
   - ❌ PowerShell: `git commit -m "message" 2>&1` (may show cosmetic errors)
   - ✅ Git Bash: Same command works perfectly

---

### 🎨 Why This Reflects Our Quality Culture

**Values demonstrated by this standard:**
- **Highest Quality:** No compromises on appearance or professionalism
- **User Experience:** Clean output, no confusing error messages ("eyesores")
- **Team Consistency:** Everyone operates the same way
- **Preventive:** Avoid problems instead of working around them
- **Documentation:** This is written down, not assumed knowledge

**A single cosmetic error affects credibility:**
- User sees error messages even though everything works
- Creates doubt: "Is the commit really pushed?"
- Undermines professional appearance
- Prevents us from inculcating highest quality culture

**This standard says:** "We care enough to eliminate cosmetic issues. Quality matters in every detail."

---

### ✅ Alternative: ASCII-Only Commit Messages (For teams that insist on PowerShell)

If your team strongly prefers PowerShell and refuses Git Bash, **minimum requirement** is ASCII-only commit messages:

```markdown
Update to commit format (v7):

Commit Message Format:
  <type>: <description>
  
  <body with details>
  
  Backend Tests: X/X passed, 0 warnings [PASS]
  Manual Testing: [PASS] (for UI changes only)

Approved ASCII replacements ONLY:
  [PASS]  == previously ✓
  [FAIL]  == previously ✗
  [OK]    == previously ✓
  [DONE]  == previously ✓
```

**But note:** This approach still has the PowerShell redirection issue appear cosmetically.  
**Git Bash approach is superior** - Choose that instead.

---

### Updating Prime Directive

**Git profile requirements (if this profile is adopted):**
- ✅ **PRIMARY:** Use Git Bash for all git operations on Windows
- ✅ Use only ASCII characters in commit messages (no Unicode/emoji)
- ✅ Use approved ASCII replacements: `[PASS]`, `[FAIL]`, `[OK]`, `[DONE]`
- ✅ Document what was tested in commit message
- ✅ Include test count: "Backend Tests: X/X passed, 0 warnings [PASS]"
- ✅ For UI changes, include: "Manual Testing: [PASS]" with checklist items
- ✅ Never commit code with failing tests or warnings

**Document last updated:** 2026-05-18

---

**Revision History:**
- **2026-05-18 (v12): CDN SRI Hash Integrity Rule** - Added Principle 14 "CDN / External Resource Integrity — Never Write SRI Hashes by Hand"; added pre-commit checklist item requiring hash computation from live URL for any CDN integrity attribute; added Case Study "SRI Hash Written by Hand — One Character, Hours Lost" documenting the Bootstrap JS incident where a single character case difference (s vs S) caused Bootstrap to be blocked, with 60+ minutes of diagnosis across multiple sessions; root cause was writing the hash by inspection rather than computing it from the downloaded file; prevention: always run the urllib.request/hashlib.sha384 one-liner against the exact CDN URL before committing
- **2026-02-20 (v11): Cross-Project Portability Refactor** - Added explicit global scope statement; generalized hardcoded project path examples (`<project-folder>`); reframed ClearMeet-titled incidents as stack-agnostic case studies; generalized output-quality wording beyond MOM-specific content; converted Git Bash section into an optional Windows project profile; clarified that historical/case-study sections are examples to apply across projects
- **2026-02-20 (v10): Context Cleanup Pass** - Updated virtual environment examples to use ClearMeet naming (`clearmeet` instead of `pp2-practice-bot`); refreshed internal documentation pointers (`session_log.md`, `tests/`); archived outdated non-ClearMeet sprint metrics into a legacy reference note; normalized "Code Quality Standards Achieved" into project-agnostic target-state criteria
- **2026-02-20 (v9): Hosted Deployment Addendum + Streamlit Rerun Discipline** - Added hosted dependency checks, version pinning guidance, and system dependency declaration for cloud deployments; added Streamlit rerun caching discipline to prevent unintended reprocessing; required hosted smoke tests for end-to-end verification
- **2026-02-19 (v8): Git Bash as Required Standard** - Upgraded Git Bash from "optional recommendation" to "REQUIRED team standard" (v7 was incomplete approach); Added "Why Git Bash is the standard for ClearMeet" section emphasizing quality culture alignment; Created detailed "Setup Guide: Switching to Git Bash" for team onboarding; Added "Why This Reflects Our Quality Culture" section explaining how this standard demonstrates commitment to highest quality; Established daily workflow division: PowerShell for Python/Flask operations, Git Bash exclusively for git operations; Made clear that cosmetic errors undermine professionalism and damage credibility; Updated all requirements to mandate Git Bash; Secondary fallback (ASCII-only messages) now clearly marked as "minimum if team refuses Git Bash" (not recommended); Rationale: Single cosmetic error affects entire credibility - preventing the issue is better than working around it; Philosophy: "We care enough to eliminate eyesores entirely"
- **2026-02-19 (v7): Git Best Practices & ASCII Commit Messages** - Added comprehensive Git best practices section addressing PowerShell Unicode encoding issues; Established ASCII-only commit message standard to prevent encoding errors; Documented three solutions (ASCII messages, Git Bash, UTF-8 config); Updated commit message format to use [PASS]/[FAIL] instead of Unicode; Added tool comparison table and recommendations; Commits with special characters will no longer cause error messages
- **2026-02-16 (v6): Audio Chunking for Large Files** - Implemented time-based audio chunking to handle files >20MB (up to 200MB); Used lazy import pattern for pydub to avoid Python 3.13 audioop compatibility issues when not chunking; Added Phase 1 progress UI (loading overlay with spinner) to inform users during long transcription operations; Updated validation to accept larger files (16MB → 200MB); Maintained backward compatibility for small files (<20MB) using single-file transcription; Design decision: Simple time-based chunking (Option B) over silence detection (Option A) for faster implementation and reliability; Testing approach: Verified existing tests still pass (17/19 audio tests), chunking tested with large file; Future enhancement: Real-time progress updates via SSE/WebSocket (Phase 2); Key lesson: Lazy imports can resolve dependency conflicts while maintaining functionality
- **2026-02-16 (v5): ClearMeet Frontend Testing Gap** - Added Principle 5 "Frontend/UI Testing - The Backend Test Blind Spot" after 138/138 tests passed but form submission failed due to JavaScript bug; Added comprehensive lesson learned documenting incident where tab-switching code cleared form values; Added Quick Reference "Before Every Commit" checklist at document top; Added Testing Strategy Decision Matrix with clear guidance on when to use backend tests vs manual testing vs E2E tests; Enhanced Principle 1 Protocol to explicitly require manual testing for UI changes (steps 5-7); Added Summary section with key takeaways, common mistakes, cost analysis, and critical workflows; Updated last modified date to 2026-02-16; Total additions: ~150 lines of critical frontend testing guidance
- 2025-11-25 (v4): **Sprint 4 Task 1 Lesson (Legacy Snapshot)** - Added critical "Research APIs Before Integration Tests" lesson from Sprint 4 Task 1 experience (37+ API mismatches), enhanced pre-implementation checklist with integration test research protocol, and documented time savings from API research
- 2025-11-24 (v3): **Sprint 3 Complete (Legacy Snapshot)** - Added sprint lessons (dataclasses+enums, statistical analysis, TDD acceleration, fixtures, reporting, edge cases, integration workflows, commit discipline, pass-rate rigor)
- 2025-11-24 (v2): **Zero Warnings Policy** - Updated Principle 0 to require zero warnings (not just zero failures), Added warning investigation requirement to all checklists and protocols, Fixed SQLAlchemy deprecation warning (declarative_base import), Documented warning resolution in Sprint 2 history
- 2025-11-24 (v1): Added Sprint 2 lessons (legacy snapshot) including validation, risk management, persistence, and incremental testing guidance
- 2025-11-22: Added Prime Directive Principle 0 (100% test pass requirement), historical Day 4 lessons, and deletion protocol
- 2025-11-21: Initial creation with historical Day 3 lessons learned

**Next Review:** After next major incident or quarterly (next: May 2026)

---

*This is a living document. Update it as we learn. Share it with the team. Follow it every time.*
