import click
import json
import os
from lambder import Lambder, Entry

lambder = Lambder()

@click.group()
def cli():
  pass

@cli.group()
def events():
  """ Manage scheduled events """
  pass

# lambder events list
@events.command()
def list():
  """ List all events """
  entries = lambder.list_events()
  for e in entries:
    click.echo(str(e))

# lambder events add
@events.command()
@click.option('--name', help='unique name for entry')
@click.option('--function-name', help='AWS Lambda name')
@click.option("--cron", help='cron expression')
def add(name, function_name, cron):
  """ Create an event """
  lambder.add_event(name=name, function_name=function_name, cron=cron)

# lambder events rm
@events.command()
@click.option('--name', help='event to remove')
def rm(name):
  """ Remove an existing entry """
  lambder.delete_event(name)

# lambder events disable
@events.command()
@click.option('--name', help='event to disable')
def disable(name):
  """ Disable an event """
  lambder.disable_event(name)

# lambder events enable
@events.command()
@click.option('--name', help='event to enable')
def enable(name):
  """ Enable a disabled event """
  lambder.enable_event(name)

# lambder events load
@events.command()
@click.option('--file', help='json file containing events to load')
def load(file):
  """ Load events from a json file """
  with open(file, 'r') as f:
    contents = f.read()
  lambder.load_events(contents)

class FunctionConfig:
  def __init__(self, config_file):
    with open(config_file, 'r') as f:
      contents = f.read()
    config = json.loads(contents)
    self.name   = config['name']
    self.bucket = config['s3_bucket']

@cli.group()
@click.pass_context
def functions(context):
  """ Manage AWS Lambda functions """
  # find lambder.json in CWD
  config_file = "./lambder.json"
  if os.path.isfile(config_file):
    context.obj = FunctionConfig(config_file)
  pass

# lambder functions list
@functions.command()
def list():
  """ List lambder functions """
  functions = lambder.list_functions()
  output = json.dumps(
    functions,
    sort_keys=True,
    indent=4,
    separators=(',', ':')
  )
  click.echo(output)

# lambder functions new
@functions.command()
@click.option('--name', help='name of the function')
@click.option('--bucket', help='S3 bucket used to deploy function', default='mybucket')
def new(name, bucket):
  """ Create a new lambda project """
  lambder.create_project(name, bucket)

# lambder functions deploy
@functions.command()
@click.option('--name', help='name of the function')
@click.option('--bucket', help='destination s3 bucket')
@click.pass_obj
def deploy(config, name, bucket):
  """ Deploy/Update a function from a project directory """
  # options should override config if it is there
  myname   = name or config.name
  mybucket = bucket or config.bucket

  click.echo('Deploying {} to {}'.format(myname, mybucket))
  lambder.deploy_function(myname, mybucket)

# lambder functions rm
@functions.command()
@click.option('--name', help='name of the function')
@click.option('--bucket', help='s3 bucket containing function code')
@click.pass_obj
def rm(config, name, bucket):
  """ Delete lambda function, role, and zipfile """
  # options should override config if it is there
  myname   = name or config.name
  mybucket = bucket or config.bucket

  click.echo('Deleting {} from {}'.format(myname, mybucket))
  lambder.delete_function(myname, mybucket)

# lambder functions invoke
@functions.command()
@click.option('--name', help='name of the function')
@click.option('--input', help='json file containing input event')
@click.pass_obj
def invoke(config, name, input):
  """ Invoke function in AWS """
  # options should override config if it is there
  myname = name or config.name

  click.echo('Invoking ' + myname)
  output = lambder.invoke_function(myname, input)
  click.echo(output)
