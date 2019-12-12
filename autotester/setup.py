from setuptools import setup

setup(name='MarkUs Autotester',
      version='2.0',
      description='Automatic tester for programming assignments',
      url='https://github.com/MarkUsProject/markus-autotesting',
      author='Misha Schwartz, Alessio Di Sandro',
      author_email='mschwa@cs.toronto.edu',
      license='MIT',
      packages=['autotester'],
      zip_safe=False,
      install_requires=[
        'redis==3.3.8',
        'requests==2.22.0',
        'rq==1.1.0',
        'supervisor==4.0.4',
        'PyYAML==5.1.2',
        'psycopg2-binary==2.8.3',
        'markusapi==0.0.1',
        'jsonschema==3.0.2',
        'fakeredis==1.1.0',
      ],
      entry_points={
        'console_scripts': 'markus_autotester = autotester.cli:cli'
      })