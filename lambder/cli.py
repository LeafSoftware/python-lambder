import click
import boto3
import botocore.session
import json
from cookiecutter.main import cookiecutter
import os
import zipfile
import tempfile

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

  def create(self, name):
    cookiecutter(
      'https://github.com/LeafSoftware/cookiecutter-lambder',
      no_input=True,
      extra_context={
        'lambda_name': name,
        'repo_name': 'lambder-' + name
      }
    )

  # Recursively zip path, creating a zipfile with contents
  # relative to path.
  # e.g. lambda/foo/foo.py     -> ./foo.py
  # e.g. lambda/foo/bar/bar.py -> ./bar/bar.py
  #
  def _zipdir(self, zfile, path):
    with zipfile.ZipFile(zfile, 'w') as ziph:
      for root, dirs, files in os.walk(path):

        # strip path from beginning of full path
        rel_path = root
        if rel_path.startswith(path):
          rel_path = rel_path[len(path):]

        for file in files:
          ziph.write(os.path.join(root, file), os.path.join(rel_path, file))

  def _s3_cp(self, src, dest_bucket, dest_key):
    s3 = boto3.client('s3')
    s3.upload_file(src, dest_bucket, dest_key)

  def _create_lambda_role(self, role_name):
    iam = boto3.resource('iam')
    role = iam.Role(role_name)
    # return the role if it already exists
    if role in iam.roles.all():
      return role

    trust_policy = json.dumps(
      {
        "Statement": [
           {
             "Effect": "Allow",
             "Principal": {
               "Service": ["lambda.amazonaws.com"]
             },
             "Action": ["sts:AssumeRole"]
           }
        ]
      }
    )

    role = iam.create_role(
      RoleName=role_name,
      AssumeRolePolicyDocument=trust_policy
    )
    return role

  def _put_role_policy(self, role, policy_name, policy_doc):
    iam = boto3.client('iam')
    policy = iam.put_role_policy(
      RoleName=role.name,
      PolicyName=policy_name,
      PolicyDocument=policy_doc
    )

  def _lambda_exists(self, name):
    awslambda = boto3.client('lambda')
    try:
      resp = awslambda.get_function(
        FunctionName=self._long_name(name)
      )
    except botocore.exceptions.ClientError as e:
      if e.response['Error']['Code'] == 'ResourceNotFoundException':
        return False
      else:
        raise

    return True

  def _update_lambda(self, name, bucket, key):
    awslambda = boto3.client('lambda')
    resp = awslambda.update_function_code(
      FunctionName=self._long_name(name),
      S3Bucket=bucket,
      S3Key=key
    )

  # TODO: allow user to set timeout and memory
  def _create_lambda(self, name, bucket, key, role_arn):
    awslambda = boto3.client('lambda')
    resp = awslambda.create_function(
      FunctionName=self._long_name(name),
      Runtime='python2.7',
      Role=role_arn,
      Handler="{}.handler".format(name),
      Code={
        'S3Bucket': bucket,
        'S3Key': key
      }
    )

  def _long_name(self, name):
    return 'Lambder-' + name

  def deploy(self, name, bucket):
    long_name   = 'Lambder-' + name
    s3_key      = "lambder/lambdas/{}_lambda.zip".format(name)
    role_name   = long_name + 'ExecuteRole'
    policy_name = long_name + 'ExecutePolicy'
    policy_file = os.path.join('iam', 'policy.json')

    # zip up the lambda
    zfile = os.path.join(tempfile.gettempdir(), "{}_lambda.zip".format(name))
    self._zipdir(zfile, os.path.join('lambda', name))

    # upload it to s3
    self._s3_cp(zfile, bucket, s3_key)

    # remote tempfile
    os.remove(zfile)

    # create the lambda execute role if it does not already exist
    role = self._create_lambda_role(role_name)

    # update the role's policy from the document in the project
    policy_doc = None
    with open(policy_file, 'r') as f:
      policy_doc = f.read()

    self._put_role_policy(role, policy_name, policy_doc)

    # create or update the lambda function
    if self._lambda_exists(name):
      self._update_lambda(name, bucket, s3_key)
    else:
      self._create_lambda(name, bucket, s3_key, role.arn)

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

@cli.command()
@click.option('--name', help='name of the lambda')
def create(name):
  """ Create a new lambda project """
  lambder.create(name)

@cli.command()
@click.option('--name', help='name of the lambda')
@click.option('--bucket', help='destination s3 bucket')
def deploy(name, bucket):
  """ Deploy a lambda from a project directory """
  lambder.deploy(name, bucket)
