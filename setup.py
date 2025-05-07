import os
import setuptools

# Get the absolute path to the directory containing setup.py
here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.md"), "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Get documentation requirements
try:
    with open(os.path.join(here, "requirements-docs.txt"), "r", encoding="utf-8") as f:
        docs_requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
except FileNotFoundError:
    # Fallback in case the file is not found
    docs_requirements = [
        "sphinx>=7.0.0",
        "sphinx-rtd-theme>=2.0.0",
        "sphinx-autodoc-typehints>=1.12.0",
        "myst-parser>=0.15.0"
    ]

setuptools.setup(
    name="retrosys-core",
    version="0.1.0", 
    author="RetroSys",
    author_email="afaghi@gmail.com",
    description="Yet another Python dependency injection framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/arashafaghi/retrosys_core",
    project_urls={
        "Bug Tracker": "https://github.com/arashafaghi/retrosys_core/issues",
        "Documentation": "https://retrosys-core.readthedocs.io/en/latest/",  
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "."},
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    install_requires=[
        
    ],
    extras_require={
        "docs": docs_requirements,
    },
)