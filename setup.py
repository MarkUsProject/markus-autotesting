from setuptools import setup, find_packages

test_exclusions = ["*.tests", "*.tests.*", "tests.*", "tests"]

setup(name='markus-autotester',
      version='2.0',
      description='Automatic tester for programming assignments',
      url='https://github.com/MarkUsProject/markus-autotesting',
      author='Misha Schwartz, Alessio Di Sandro',
      author_email='mschwa@cs.toronto.edu',
      license='MIT',
      package_dir={'': 'src'},
      packages=find_packages(where='src', exclude=test_exclusions),
      zip_safe=False,
      install_requires=[
        'redis==3.3.8',
        'requests==2.22.0',
        'rq==1.1.0',
        'supervisor==4.1.0',
        'PyYAML==5.1.2',
        'psycopg2-binary==2.8.4',
        'markusapi==0.0.1',
        'jsonschema==3.0.2'
      ],
      tests_require=[
        'fakeredis==1.1.0'
      ],
      include_package_data=True,
      # data_files=[('config_defaults', ['config/config_default.yml', 'config/config_env_vars.yml'])],
      entry_points={
        'console_scripts': 'markus_autotester = autotester.cli:cli'
      })
