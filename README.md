# Lambder

Creates and manages scheduled AWS Lambdas


## Installation

If you don't use `pipsi`, you're missing out.
Here are [installation instructions](https://github.com/mitsuhiko/pipsi#readme).

Simply run:

    $ pipsi install python-lambder

## Usage

Get help

    lambder --help

### Managing Events

Schedule an existing AWS Lambda

    lambder events add \
      --name EbsBackups \
      --function-name Lambder-ebs-backup \
      --cron 'cron(0 6 ? * * *)'

Remove an event (a scheduled Lambda)

    lambder events rm --name EbsBackups

Disable an event

    lambder events disable --name EbsBackups

Re-enable a disabled event

    lambder events enable --name EbsBackups

Load events from a json file

    lambder events load --file example_events.json

List all events created by lambder

    lambder events list

### Managing Functions

Create a new AWS Lambda project

    lambder functions new \
      --name ebs-backups \
      --bucket my-s3-bucket

Deploy the Lambda function (from within the project directory)

    lambder function deploy

Invoke the Lambda in AWS (from within the project directory)

    lambder function invoke

Invoke the function with input (from within the project directory)

    lambder function invoke --input input/ping.json

List all functions

    lambder functions list

Delete a function (from within the project directory)

    lambder functions rm

## Sample Lambda Functions

* https://github.com/LeafSoftware/lambder-create-images
* https://github.com/LeafSoftware/lambder-start-instances
* https://github.com/LeafSoftware/lambder-stop-instances

## TODO:

* add code to add site packages from virtualenvwrapper to zip
* add lambda name autodetection to 'lambder events add'
* add pagination where needed (lambda:list-functions)
* parameterize lambda timeout
