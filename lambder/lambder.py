import boto3
import botocore.session
import json
from cookiecutter.main import cookiecutter
import os
import zipfile
import tempfile
import time

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

  def add_event(self, name, function_name, cron, input_event={}, enabled=True):
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

  def list_events(self):
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

  def delete_event(self, name):
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

  def disable_event(self, name):
    rule_name = self.NAME_PREFIX + name
    resp = self.events.disable_rule(
      Name=rule_name
    )

  def enable_event(self, name):
    rule_name = self.NAME_PREFIX + name
    resp = self.events.enable_rule(
      Name=rule_name
    )

  def load_events(self, data):
    entries = json.loads(data)
    for entry in entries:
      self.add(
        name=entry['name'],
        cron=entry['cron'],
        function_name=entry['function_name'],
        input_event=entry['input_event'],
        enabled=entry['enabled']
      )

  def create_project(self, name, bucket, config):
    context = {
      'lambda_name': name,
      'repo_name': 'lambder-' + name,
      's3_bucket': bucket
    }
    context.update(config)

    cookiecutter(
      'https://github.com/LeafSoftware/cookiecutter-lambder',
      no_input=True,
      extra_context=context
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

  def _s3_rm(self, bucket, key):
    s3 = boto3.resource('s3')
    the_bucket = s3.Bucket(bucket)
    the_object = the_bucket.Object(key)
    the_object.delete()

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

  def _delete_lambda_role(self, name):
    iam = boto3.resource('iam')

    role_name   = self._role_name(name)
    policy_name = self._policy_name(name)

    role_policy = iam.RolePolicy(role_name, policy_name)
    role = iam.Role(self._role_name(name))

    # HACK: This 'if thing in things.all()' biz seems like
    # a very inefficient way to check for resource
    # existence...
    if role_policy in role.policies.all():
      role_policy.delete()

    if role in iam.roles.all():
      role.delete()

  def _put_role_policy(self, role, policy_name, policy_doc):
    iam = boto3.client('iam')
    policy = iam.put_role_policy(
      RoleName=role.name,
      PolicyName=policy_name,
      PolicyDocument=policy_doc
    )

  def _attach_vpc_policy(self, role):
    iam = boto3.client('iam')
    iam.attach_role_policy(
      RoleName=role,
      PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole'
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

  def _update_lambda(self, name, bucket, key, timeout, memory, description, vpc_config):
    awslambda = boto3.client('lambda')
    resp = awslambda.update_function_code(
      FunctionName=self._long_name(name),
      S3Bucket=bucket,
      S3Key=key
    )

    resp = awslambda.update_function_configuration(
      FunctionName=self._long_name(name),
      Timeout=timeout,
      MemorySize=memory,
      Description=description,
      VpcConfig=vpc_config
    )

  def _create_lambda(self, name, bucket, key, role_arn, timeout, memory, description, vpc_config):
    awslambda = boto3.client('lambda')
    resp = awslambda.create_function(
      FunctionName=self._long_name(name),
      Runtime='python2.7',
      Role=role_arn,
      Handler="{}.handler".format(name),
      Code={
        'S3Bucket': bucket,
        'S3Key': key
      },
      Timeout=timeout,
      MemorySize=memory,
      Description=description,
      VpcConfig=vpc_config
    )

  def _delete_lambda(self, name):
    awslambda = boto3.client('lambda')
    if self._lambda_exists(name):
      resp = awslambda.delete_function(
        FunctionName=self._long_name(name)
      )

  def _long_name(self, name):
    return 'Lambder-' + name

  def _s3_key(self, name):
    return "lambder/lambdas/{}_lambda.zip".format(name)

  def _role_name(self, name):
    return self._long_name(name) + 'ExecuteRole'

  def _policy_name(self, name):
    return self._long_name(name) + 'ExecutePolicy'

  def deploy_function(self, name, bucket, timeout, memory, description, vpc_config):
    long_name   = self._long_name(name)
    s3_key      = self._s3_key(name)
    role_name   = self._role_name(name)
    policy_name = self._policy_name(name)
    policy_file = os.path.join('iam', 'policy.json')

    # zip up the lambda
    zfile = os.path.join(tempfile.gettempdir(), "{}_lambda.zip".format(name))
    self._zipdir(zfile, os.path.join('lambda', name))

    # upload it to s3
    self._s3_cp(zfile, bucket, s3_key)

    # remove tempfile
    os.remove(zfile)

    # create the lambda execute role if it does not already exist
    role = self._create_lambda_role(role_name)

    # update the role's policy from the document in the project
    policy_doc = None
    with open(policy_file, 'r') as f:
      policy_doc = f.read()

    self._put_role_policy(role, policy_name, policy_doc)

    # add the vpc policy to the role if vpc_config is set
    if vpc_config:
      self._attach_vpc_policy(role_name)

    # create or update the lambda function
    timeout_i = int(timeout)
    if self._lambda_exists(name):
      self._update_lambda(name, bucket, s3_key, timeout_i, memory, description, vpc_config)
    else:
      time.sleep(5) # wait for role to be created
      self._create_lambda(name, bucket, s3_key, role.arn, timeout_i, memory, description, vpc_config)

  # List only the lambder functions, i.e. ones starting with 'Lambder-'
  def list_functions(self):
    awslambda = boto3.client('lambda')
    resp = awslambda.list_functions()
    functions = resp['Functions']
    return filter(
      lambda x: x['FunctionName'].startswith(self.NAME_PREFIX),
      functions
    )


  def _delete_lambda_zip(self, name, bucket):
    key = self._s3_key(name)
    self._s3_rm(bucket, key)

  # delete all the things associated with this function
  def delete_function(self, name, bucket):
    self._delete_lambda(name)
    self._delete_lambda_role(name)
    self._delete_lambda_zip(name, bucket)

  def invoke_function(self, name, input_event):
    awslambda = boto3.client('lambda')
    payload = '{}' # default to empty event

    if input_event:
      with open(input_event, 'r') as f:
        payload = f.read()

    resp = awslambda.invoke(
      FunctionName=self._long_name(name),
      InvocationType='RequestResponse',
      Payload=payload
    )
    results = resp['Payload'].read() # payload is a 'StreamingBody'
    return results
