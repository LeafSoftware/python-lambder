# Lambder

Creates and manages scheduled AWS Lambdas


# Installation

If you don't use `pipsi`, you're missing out.
Here are [installation instructions](https://github.com/mitsuhiko/pipsi#readme).

Simply run:

    $ pipsi install .


# Usage

To use it:

    $ lambder --help

# TODO:

* move run script into lambder cli/pure python
* modify run command to take input event
* create invoke command to run lambda in AWS
* add code to add site packages from virtualenvwrapper to zip
* refactor lambder class into sep file
* add pagination where needed (lambda:list-functions)
