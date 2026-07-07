"""Setup script for the Financial Intelligence package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip()
        for line in fh
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="financial-intelligence",
    version="1.0.0",
    author="Your Team",
    author_email="team@example.com",
    description="Production-ready Financial Intelligence API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/financial-intelligence",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "notebooks"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "black>=24.1.0",
            "isort>=5.13.0",
            "mypy>=1.8.0",
            "pylint>=3.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "financial-api=src.api.main:main",
        ],
    },
)
