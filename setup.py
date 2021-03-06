from setuptools import setup, find_packages

test_exclusions = ["*.tests", "*.tests.*", "tests.*", "tests"]

setup(
    name="autotester",
    version="2.0",
    description="Automatic tester for programming assignments",
    url="https://github.com/MarkUsProject/markus-autotesting",
    author="Misha Schwartz, Alessio Di Sandro",
    author_email="mschwa@cs.toronto.edu",
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages(where="src", exclude=test_exclusions),
    zip_safe=False,
    install_requires=[
        "redis==3.3.8",
        "rq==1.1.0",
        "supervisor==4.1.0",
        "PyYAML==5.1.2",
        "psycopg2-binary==2.8.6",
        "markusapi==0.2.0",
        "jsonschema==3.0.2",
    ],
    tests_require=["pytest==5.3.1", "hypothesis==4.47.3", "fakeredis==1.1.0"],
    setup_requires=["pytest-runner"],
    include_package_data=True,
    entry_points={"console_scripts": "autotester = autotester.cli:cli"},
)
