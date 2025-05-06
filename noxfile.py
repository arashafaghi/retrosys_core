import nox
import os

PROJECT_NAME = "retrosys"
PROJECT_PATH = "retrosys"
TEST_PATH_1 = "tests"

# Get the repository root path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

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
def docs(session):
    """Build the documentation."""
    # Install required dependencies using the full path to the requirements file
    requirements_path = os.path.join(REPO_ROOT, "requirements _dev.txt")
    session.run("pip", "install", "-r", requirements_path)
    
    # Create _static directory if it doesn't exist
    static_dir = os.path.join(REPO_ROOT, "docs/source/_static")
    session.run("mkdir", "-p", static_dir, external=True)
    
    # Build the documentation
    docs_dir = os.path.join(REPO_ROOT, "docs")
    session.chdir(docs_dir)
    
    # Run sphinx-apidoc with the correct path to the project
    api_dir = os.path.join(docs_dir, "source/api")
    project_dir = os.path.join(REPO_ROOT, PROJECT_PATH)
    session.run("sphinx-apidoc", "-o", api_dir, project_dir, "--force")
    
    # Build HTML documentation
    session.run("sphinx-build", "-b", "html", "source", "build/html")
    
    session.log(f"Documentation built in {os.path.join(docs_dir, 'build/html')}")
    # Open the documentation (optional, uncomment if needed)
    # session.run("xdg-open", "build/html/index.html", external=True)

@nox.session(python=False)
@nox.session
def clean(session):
    """Remove temp folders."""
    session.run("find", ".", "-name", "__pycache__", "-type", "d", "-exec", "rm", "-rf", "{}", "+", external=True)
    session.run("rm", "-rf", "htmlcov", ".pytest_cache", ".coverage", ".ruff_cache", "docs/build", external=True)