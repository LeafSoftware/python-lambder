# Lambder

Serverless cron jobs written in python and scheduled as AWS Lambdas.

We used to implement maintenance jobs like RDS snapshots and starting/stopping
instances outside of business hours as CI server builds. This always seemed hacky.
When scheduled Lambdas were released, we got to work re-implementing these
scripts. Unfortunately, scheduled Lambdas have a steep learning curve.
You have to understand IAM roles, CloudWatch Events, and how to deploy and
update Lambda function code.

Lambder simplifies the creation and deployment of these scheduled jobs.

## Installation

If you don't use `pipsi`, you're missing out.
Here are [installation instructions](https://github.com/mitsuhiko/pipsi#readme).

Simply run:

    $ pipsi install lambder

## Getting Started

To create a new Lambda Function project, specify a name and an S3 bucket to
store the code zipfile.

1. `lambder functions new --name foo --bucket mys3bucket`
2. `cd lambder-foo`
3. `lambder functions deploy`
4. `lambder functions list`
5. `lambder functions invoke`

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

Create a new AWS Lambda project. Specify a name and an S3 bucket to store
the Lambda function code. Optionally specify function configuration like
timeout, memory size, and description.

    lambder functions new \
      --name ebs-backups \
      --bucket my-s3-bucket \
      --timeout 30 \
      --memory 128 \
      --description "ebs backup function"

Deploy the Lambda function (from within the project directory)

    lambder functions deploy

Invoke the Lambda in AWS (from within the project directory)

    lambder functions invoke

Invoke the function with input (from within the project directory)

    lambder functions invoke --input input/ping.json

List all functions

    lambder functions list

Delete a function (from within the project directory)

    lambder functions rm

## Sample Lambda Functions

* https://github.com/LeafSoftware/lambder-create-images
* https://github.com/LeafSoftware/lambder-start-instances
* https://github.com/LeafSoftware/lambder-stop-instances
* https://github.com/LeafSoftware/lambder-create-snapshots

## TODO:

* add code to add site packages from virtualenvwrapper to zip
* add lambda name autodetection to 'lambder events add'
* add pagination where needed (lambda:list-functions)
