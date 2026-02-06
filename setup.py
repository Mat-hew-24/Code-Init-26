from setuptools import setup

setup(
    name="gridx",
    version="0.1",
    py_modules=["cli", "agent", "api"],
    install_requires=["requests"],
    entry_points={
        "console_scripts": [
            "gridx=cli:main"
        ]
    }
)
