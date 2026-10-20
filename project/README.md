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

## Sprint 1
Do not rebuild infrastructure that already works. Use this baseline to reach one **small, integrated, testable vertical slice** of your actual product. Add architecture because your product needs it, not because you think a real project is supposed to have it.


# Getting started (FOR DEVS*)
- Switch to the branch you're working out of with: git switch <BRANCH-NAME>
- Once in the new branch, confirm your location with: git branch
- Enter this command to implement the latest changes: git pull
- Change directories down into the 'project' folder.
- Enter VSCode from here with: code .
- Open a new terminal with Ctrl+L-Shift+~
- Ensure you are working under the 'project>' directory
*NOTE* If the following commands are giving you issues, try this command before trying the next commands: python manage.py makemigrations
- Follow these commands:
1. python manage.py makemigrations --merge
2. python manage.py migrate
- Now, to verify tests all pass run: python -m pytest
# TO CREATE AN ACCOUNT:
- There are 2 ways. One from within the VSCode terminal and one from the create account page on the web app. Both should work.
*FROM THE WEB-APP*
- Run the web-app with: python manage.py runserver
- This will default to the localhost on port 8000. Go to any webpage you'd like and type this address in: 127.0.0.1:8000
- Below the 'Log in' button there should be a 'Create account' button, click on it and you'll be brough to a create user page where you can enter in a fake username, email, and password. Right now, you can have more than one account per email. We may change this later but for all of my test accounts I've been using "no@no.com" for the email with simple user/passwords.
- At the bottom you'll find a 'Create account!' button, click on it and you'll be brough to the home page of your account's lounge.
*FROM THE TERMINAL*
- From within the 'project>' directory, run the command: python manage.py createsuperuser
- This will take you through a short setup process. You'll need to enter a username, email, and password twice.
- Once you receive the 'Superuser created successfully.' message, you'll know an account is setup.
- Run the server with: python manage.py runserver
- Open a browser and go to: 127.0.0.1:8000
- Use the username and password you just created to login, and you should be taken to a home page unique to that account.

This is ==highlighted== text. ==Test?==