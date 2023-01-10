from setuptools import setup, find_packages

setup(
    name='karmabot',
    version='1.0.2',
    description='A Slack bot to track Karma points',
    author='Jay Kline',
    author_email='jay.kline@target.com',
    url='https://github.com/target/karmabot',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'flask',
        'urlfetch',
        'pymongo',
        'influxdb',
        'flask-executor',
        'hvac'
    ],
    extras_require={
        'dev': [
            'flake8'
        ]
    }
)
