## Setting up your environment
If you don't already have python installed, install it, eg from [here](https://www.python.org/downloads/)


## Contribution
Once you have installed python please install pip
Then you will need to install [poetry](https://python-poetry.org/docs/#installing-with-pipx) this is our dependency management system. The easiest way is probably via [pipx](https://pipx.pypa.io/stable/installation/).

Once you have installed these run the following from the root folder
```
cd <folder for project you want to work on>
poetry install # for non mkdocs projects
poetry install --no-root # for mkdocs project
```
This installs all dependencies listed in pyproject.toml and locked in poetry.lock.

It also creates a virtual environment for the project if one doesn’t exist.

## Adding dependencies
```
poetry add <package>          # add a runtime dependency
poetry add --dev <package>    # add a dev dependency (for tests, linting, etc.)
```
Then run
```
poetry install # for non mkdocs projects
poetry install --no-root # for mkdocs project
```

## Running a particular project
Once inside the folder for the project if you have installed the dependencies run
```
poetry run python3 <python file to run> # for python
poetry run mkdocs serve # for mkdocs
```

## Using Pre-commit

We use pre-commit to automatically run linters and formatters before committing code. This helps maintain code quality and consistency.

From the root folder
Install pre-commit (if not already installed):
```
poetry add --dev pre-commit
```
Install the Git hooks for the project:
```
poetry run pre-commit install
```

This sets up hooks that automatically run on git commit.

Run pre-commit manually (optional, to check all files):
```
poetry run pre-commit run --all-files
```

If any hook fails, fix the issues, then commit again.

## Code quality
Code is linted using the following tools:

black - Code formatter (auto-formats code using defined rules in global pyproject.toml file)

flake8 - Provides PEP8 linting, basic style & errors

isort - Manages import order

