from setuptools import setup, find_packages

test_exclusions = ["*.tests", "*.tests.*", "tests.*", "tests"]

packages = ["testers"] + [f"testers.{pkg}" for pkg in find_packages(where="testers", exclude=test_exclusions)]

setup(
    name="autotester-testers",
    version="2.0",
    description="Testers for the automatic tester for programming assignments",
    url="https://github.com/MarkUsProject/markus-autotesting",
    author="Misha Schwartz, Alessio Di Sandro",
    author_email="mschwa@cs.toronto.edu",
    license="MIT",
    include_package_data=True,
    packages=packages,
    zip_safe=False,
)
