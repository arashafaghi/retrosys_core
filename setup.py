import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="retrosys-core",
    version="0.1.1",
    author="RetroSys",
    author_email="afaghi@gmail.com",  # Replace with your email
    description="Yet another Python dependency injection framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/arashafaghi/retrosys_core",  # Replace with your GitHub repo URL
    project_urls={
        "Bug Tracker": "https://github.com/arashafaghi/retrosys_core/issues",
        "Documentation": "https://retrosys-core.readthedocs.io/",  
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
)