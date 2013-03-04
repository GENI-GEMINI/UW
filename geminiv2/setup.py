from setuptools import setup

version = "0.2"

setup(
    name="gemini_uw",
    version=version,
    description="GEMINI User Workspace Scripts",

    install_requires=[
        "paramiko",
        "lxml",
        "unisencoder>=0.1.dev",
        ],
    dependency_links=[
        "https://github.com/periscope-ps/unisencoder/tarball/master#egg=unisencoder-0.1.dev"
        ]        
)

