from setuptools import setup

version = "0.2"

setup(
    name="msplot",
    version=version,
    description="GEMINI MS Plotting Scripts",

    install_requires=[
        "matplotlib",
        "requests",
        "docopt"
        ]
)

