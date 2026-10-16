# CS 4300 / 5300 Project Starter

This is a working technical baseline, not a product design. Evolve it into the product your team inherited.

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
Run tests with `pytest`.

## What is here
Django configuration, one `core` app, routing, a model + migration, a view, a template, SQLite, and passing-test examples. The `StarterItem` feature exists only to demonstrate **URL -> view -> model -> template -> rendered behavior**.

Signed-in Firebase users can save XP stats in their Firestore `users/{uid}` document. The fields are `total_xp`, `arms_xp`, `legs_xp`, `core_xp`, `chest_xp`, and `weekly_xp`; missing stats load as zero.

## Sprint 1
Do not rebuild infrastructure that already works. Use this baseline to reach one **small, integrated, testable vertical slice** of your actual product. Add architecture because your product needs it, not because you think a real project is supposed to have it.
