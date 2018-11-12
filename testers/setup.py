from setuptools import setup, find_packages

setup(
    name='testers',
    version='1.7.0',
    description='testers for markus autotesting',
    url='https://github.com/MarkUsProject/markus-autotesting',
    author='Alessio & Misha',
    author_email='mschwa@cs.toronto.edu',
    packages=find_packages(),
    install_requires=[ 'psycopg2-binary', 'pytest', 'python-ta' ]
)