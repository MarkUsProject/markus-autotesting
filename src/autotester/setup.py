from setuptools import setup, find_packages

test_exclusions = ["*.tests", "*.tests.*", "tests.*", "tests"]

setup(name='markus-autotester-testers',
      version='2.0',
      description='Testers for the automatic tester for programming assignments',
      url='https://github.com/MarkUsProject/markus-autotesting',
      author='Misha Schwartz, Alessio Di Sandro',
      author_email='mschwa@cs.toronto.edu',
      license='MIT',
      packages=find_packages(where='testers', exclude=test_exclusions),
      zip_safe=False)