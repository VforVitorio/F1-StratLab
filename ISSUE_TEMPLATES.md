# 📋 Issue Templates for F1_Strat_Manager

Copy and paste these templates when creating issues on GitHub or wherever you track bugs.

---

## 🐛 TEMPLATE: Bug Report

```markdown
## 🐛 Bug Report

**Affected Component:** [Streamlit App / Notebook #X / Model / Data Processing]

### Problem Description

[Describe what's wrong - e.g.: "The 'Run Strategy Analysis for all Drivers' button generates a different CSV than notebook #6"]

### Steps to Reproduce

1.
2.
3.
4.

### Expected Behavior

[What should happen]

### Actual Behavior

[What actually happens]

### Related Files

- [ ] `/notebooks/XX_notebook.ipynb`
- [ ] `/app/file.py`
- [ ] `/data/file.csv`

### Logs/Screenshots
```

[Paste error logs here]

```

### Environment
- OS:
- Python:
- Streamlit:

**Priority:** [🔥 Critical / 🔴 High / 🟡 Medium / 🟢 Low]
```

---

## ✨ TEMPLATE: Feature Request

```markdown
## ✨ Feature Request

**Component:** [Telemetry Analyzer / Voice Control / Dashboard / etc.]

### Feature Description

[What new functionality do you want]

### Use Case

[What would this feature be used for]

### Usage Example
```

User says: "Compare Hamilton lap 23 with Verstappen"
System: [automatically makes the comparison]

```

### Implementation Ideas
- [ ] Option 1:
- [ ] Option 2:

**Estimated Complexity:** [🟢 Simple / 🟡 Medium / 🔴 Complex]
```

---

## 📊 TEMPLATE: Data Issue

```markdown
## 📊 Data Issue

**Type:** [CSV Output Mismatch / Model Error / Data Loading / Processing]

### Data Problem

[Describe the specific issue]

### Reference File (correct)

[Notebook #X, model_output.csv, etc.]

### Data Comparison

**Expected:**

- Rows: X
- Columns: [A, B, C]
- Content: [description]

**Actual:**

- Rows: Y
- Columns: [A, B, D]
- Content: [description]

### Files Involved

- **Input:** `/data/raw/file.csv`
- **Script:** `/app/processor.py`
- **Expected output:** `/notebooks/output.csv`
- **Actual output:** `/app/generated.csv`

### To Investigate

- [ ] Verify input data
- [ ] Review processing logic
- [ ] Compare with notebook
- [ ] Validate model parameters
```

---

## 🚀 TEMPLATE: Task/TODO

```markdown
## 🚀 Task: [Task Title]

### Description

[What needs to be done]

### Checklist

- [ ] Subtask 1
- [ ] Subtask 2
- [ ] Subtask 3
- [ ] Testing
- [ ] Documentation

### Acceptance Criteria

- [ ] Criteria 1
- [ ] Criteria 2

### Files to Modify

- [ ] `/app/file.py`
- [ ] `/notebooks/XX.ipynb`

**Estimation:** [1 hour / 1 day / 1 week]
**Blocks:** [Issue #X, Issue #Y]
```

---

## 💡 TEMPLATE: Quick Note/Idea

```markdown
## 💡 [Short Title]

**Idea:** [Quick description]

**Why it's important:** [Reason]

**Next step:** [What to do now]

**References:** [Links, notebooks, etc.]
```

---

## 🔧 Tips for using these templates:

1. **Copy and paste** the appropriate template when creating an issue
2. **Delete sections** you don't need
3. **Add labels** like: `bug`, `feature`, `data`, `high-priority`
4. **Save this file** in your repo as `ISSUE_TEMPLATES.md`
5. **Reference issues** using `#123` to create automatic links

### Real usage example:

```
Title: [BUG] Run Strategy Analysis button generates different CSV than notebook #6
Template: 🐛 Bug Report
Labels: bug, data, high-priority, streamlit
```
