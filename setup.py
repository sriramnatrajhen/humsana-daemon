from setuptools import setup, find_packages
import os

# Read README if it exists
long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="humsana-daemon",
    version="1.0.0",
    author="Humsana",
    author_email="ram.natrajhen@gmail.com",
    description="Local behavioral signal collection for Humsana Cognitive Security",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sriramnatrajhen/humsana-daemon",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pynput>=1.7.6",
        "PyYAML>=6.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "humsana=humsana.cli:main",
        ],
    },
)
