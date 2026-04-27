# Technical challenge — Transaction importer

## Context

This codebase was written by a previous developer under time pressure. It works
— the data ends up in the database — but it has serious problems that would
become apparent in production with real data volumes.

Your job is to review it, identify what is wrong, and fix the most critical issues.

The stack: **Django · Celery · Redis · PostgreSQL · pandas**

---

## Setup

**Requirements**: Python 3.11+, PostgreSQL, Redis.

```bash
docker compose up -d --build
```

Generate a sample CSV to work with:

```bash
python generate_csv.py
```

Import the CSV:

```bash
curl -F "file=@sample_transactions.csv" http://localhost:8010/api/import/
```

Check job status:

```bash
curl http://localhost:8010/api/import/<job_id>/
```

Get summary:

```bash
curl "http://localhost:8010/api/summary/?from=2024-01-01&to=2024-06-30"
```

---

## What we ask

### 1. REVIEW.md (required)

Write a document listing every problem you identified in the codebase.
For each problem, explain:

- **What** is wrong
- **Why** it matters (what breaks, what slows down, what risks appear at scale)
- **How** you would fix it

There is no minimum or maximum length. Be precise, not exhaustive.

### 2. Fix the issues you consider most critical

Apply your fixes directly in the code. You do not need to fix everything —
prioritise what you think matters most and be ready to justify that choice
during the interview.

### 3. What you did not fix

In your REVIEW.md, add a short section at the end listing what you would
address next if you had more time, and why you deprioritised it.

---

## Constraints

- Do not add new dependencies beyond what is already listed above.
- Do not restructure the project layout.
- The API contract (URLs, request/response format) must remain the same.

---

## Submission

Push your work to a Git repository and share the link before the interview.
Commit history matters — we want to see how you progressed, not just the final state.
