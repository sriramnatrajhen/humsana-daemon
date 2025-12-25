"""
Humsana Daemon - Setup
Install with: pip install humsana-daemon
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="humsana-daemon",
    version="1.0.0",
    author="Humsana",
    author_email="hello@humsana.com",
    description="AI that reads the room - stress and focus detection for Claude",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/humsana/humsana-daemon",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.9",
    install_requires=[
        "pynput>=1.7.6",
        "PyYAML>=6.0",
        "requests>=2.28.0",  # For webhooks
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "humsana=humsana.cli:main",
        ],
    },
    include_package_data=True,
    keywords="claude, ai, focus, stress, productivity, mcp",
    project_urls={
        "Bug Reports": "https://github.com/humsana/humsana-daemon/issues",
        "Source": "https://github.com/humsana/humsana-daemon",
        "Documentation": "https://docs.humsana.com",
    },
)