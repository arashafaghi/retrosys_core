import nox

PROJECT_NAME = "retrosys"
PROJECT_PATH = "retrosys"
TEST_PATH_1 = "tests"

@nox.session(python=False)
def lint(session):
    session.run("ruff", "check", PROJECT_PATH, silent=False)

@nox.session(python=False)
def fix(session):
    session.run("ruff", "check", PROJECT_PATH, "--fix", silent=False)

@nox.session(python=False)
def format(session):
    session.run("ruff", "format", PROJECT_PATH, silent=False)

@nox.session(python=False)
def test(session):
    session.env["PYTHONPATH"] = "retrosys"
    session.run("pip", "install", "pytest-cov")
    session.run(
        "python",
        "-m",
        "pytest",
        TEST_PATH_1,
        f"--cov={PROJECT_PATH}",
        "--cov-report=term",
        "--cov-report=html",
        silent=False
    )
@nox.session(python=False)
def pre_format(session):
    session.run("ruff", "check", PROJECT_PATH, "--show-fixes", silent=False, )

@nox.session(python=False)
def all(session):
    session.run("ruff", "check", PROJECT_PATH, silent=False)
    session.run("ruff", "check", PROJECT_PATH, "--fix", silent=False)
    session.run("ruff", "format", PROJECT_PATH, silent=False)

@nox.session(python=False)
@nox.session
def clean(session):
    """Remove temp folders."""
    session.run("find", ".", "-name", "__pycache__", "-type", "d", "-exec", "rm", "-rf", "{}", "+", external=True)
    session.run("rm", "-rf", "htmlcov", ".pytest_cache", ".coverage", ".ruff_cache", external=True)