"""
Creates and manages scheduled AWS Lambdas
"""
from setuptools import find_packages, setup

dependencies = [
  'click>=6.2',
  'boto3>=1.2.6',
  'botocore>=1.4.0',
  'cookiecutter>=1.3.0'
]

setup(
    name='lambder',
    version='1.2.2',
    url='https://github.com/LeafSoftware/python-lambder',
    license='MIT',
    author='Chris Chalfant',
    author_email='cchalfant@leafsoftwaresolutions.com',
    description='Creates and manages scheduled AWS Lambdas',
    long_description=__doc__,
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=dependencies,
    entry_points={
        'console_scripts': [
            'lambder = lambder.cli:cli',
        ],
    },
    classifiers=[
        # As from http://pypi.python.org/pypi?%3Aaction=list_classifiers
        # 'Development Status :: 1 - Planning',
        # 'Development Status :: 2 - Pre-Alpha',
        # 'Development Status :: 3 - Alpha',
        'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        # 'Development Status :: 7 - Inactive',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
