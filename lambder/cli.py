import click
import boto3
import botocore.session
import json

class Entry:
  name = None
  cron = None
  function_name = None
  input_event = {}
  enabled = True

  def __init__(self, Name=None, Cron=None, FunctionName=None, InputEvent={}, Enabled=True):
    self.name = Name
    self.cron = Cron
    self.function_name = FunctionName
    self.input_event = InputEvent
    self.enabled = Enabled

  def __str__(self):
    return "\t".join([self.name, self.cron, self.function_name, str(self.enabled)])

class Lambder:
  NAME_PREFIX = 'Lambder-'

  def __init__(self):
    self.awslambda = boto3.client('lambda')
    session = botocore.session.get_session()
    self.events = session.create_client('events')

  def permit_rule_to_invoke_function(self, rule_arn, function_name):
    statement_id = function_name + "RulePermission"
    resp = self.awslambda.add_permission(
      FunctionName=function_name,
      StatementId=statement_id,
      Action='lambda:InvokeFunction',
      Principal='events.amazonaws.com',
      SourceArn=rule_arn
    )

  def add(self, name, function_name, cron, input_event={}, enabled=True):
    rule_name = self.NAME_PREFIX + name

    # events:put-rule
    resp = self.events.put_rule(
      Name=rule_name,
      ScheduleExpression=cron
    )
    rule_arn = resp['RuleArn']

    # try to add the permission, if we fail because it already
    # exists, move on.
    try:
      self.permit_rule_to_invoke_function(rule_arn, function_name)
    except botocore.exceptions.ClientError as e:
      if e.response['Error']['Code'] != 'ResourceConflictException':
        raise

    # retrieve the lambda arn
    resp = self.awslambda.get_function(
      FunctionName=function_name
    )

    function_arn = resp['Configuration']['FunctionArn']

    # events:put-targets (needs lambda arn)
    resp = self.events.put_targets(
      Rule=rule_name,
      Targets=[
        {
          'Id':    name,
          'Arn':   function_arn,
          'Input': json.dumps(input_event)
        }
      ]
    )

  def list(self):
    # List all rules by prefix 'Lambder'
    resp = self.events.list_rules(
      NamePrefix=self.NAME_PREFIX
    )

    rules = resp['Rules']

    entries = []

    # For each rule, list-targets-by-rule to get lambda arn
    for rule in rules:
      resp = self.events.list_targets_by_rule(
        Rule=rule['Name']
      )
      targets = resp['Targets']
      # assume only one target for now
      name = targets[0]['Id']
      arn  = targets[0]['Arn']
      function_name = arn.split(':')[-1]
      cron = rule['ScheduleExpression']
      enabled = rule['State'] == 'ENABLED'

      entry = Entry(
        Name=name,
        Cron=cron,
        FunctionName=function_name,
        Enabled=enabled
      )
      entries.append(entry)

    return entries

  def delete(self, name):
    rule_name = self.NAME_PREFIX + name

    # get the function name
    resp = self.events.list_targets_by_rule(
      Rule=rule_name
    )
    targets = resp['Targets']
    # assume only one target for now
    arn = targets[0]['Arn']
    function_name = arn.split(':')[-1]
    statement_id = function_name + "RulePermission"

    # delete the target
    resp = self.events.remove_targets(
      Rule=rule_name,
      Ids=[name]
    )

    # delete the permission
    resp = self.awslambda.remove_permission(
      FunctionName=function_name,
      StatementId=statement_id
    )

    # delete the rule
    resp = self.events.delete_rule(
      Name=rule_name
    )

  def disable(self, name):
    rule_name = self.NAME_PREFIX + name
    resp = self.events.disable_rule(
      Name=rule_name
    )

  def enable(self, name):
    rule_name = self.NAME_PREFIX + name
    resp = self.events.enable_rule(
      Name=rule_name
    )

  def load(self, data):
    entries = json.loads(data)
    for entry in entries:
      self.add(
        name=entry['name'],
        cron=entry['cron'],
        function_name=entry['function_name'],
        input_event=entry['input_event'],
        enabled=entry['enabled']
      )

lambder = Lambder()

@click.group()
def cli():
  pass

# lambder list
@cli.command()
def list():
  """ List all entries """
  entries = lambder.list()
  for e in entries:
    click.echo(str(e))

# lambder add
@cli.command()
@click.option('--name', help='unique name for entry')
@click.option('--function-name', help='AWS Lambda name')
@click.option("--cron", help='cron expression')
def add(name, function_name, cron):
  """ Create an entry """
  lambder.add(name=name, function_name=function_name, cron=cron)

# lambder rm
@cli.command()
@click.option('--name', help='entry to remove')
def rm(name):
  """ Remove an existing entry """
  lambder.delete(name)

# lambder disable
@cli.command()
@click.option('--name', help='entry to disable')
def disable(name):
  """ Disable an entry """
  lambder.disable(name)

# lambder enable
@cli.command()
@click.option('--name', help='entry to enable')
def enable(name):
  """ Enable a disabled entry """
  lambder.enable(name)

@cli.command()
@click.option('--file', help='json file containing entries to load')
def load(file):
  """ Load entries from a json file """
  with open(file, 'r') as f:
    contents = f.read()
  lambder.load(contents)
