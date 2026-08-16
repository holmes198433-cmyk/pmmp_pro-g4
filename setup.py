"""Setup configuration for PMMP Pro-G4"""

from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="pmmp-pro-g4",
    version="1.0.0",
    description="PMMP Pro-G4 - Vehicle Diagnostics System with RAG",
    author="Loose Nutz Garage",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "pmmp-pro-g4=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["config/*.json", "data/*"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Automotive :: Diagnostics",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
