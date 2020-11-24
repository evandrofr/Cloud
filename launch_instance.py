import boto3
import os
from decouple import config
from botocore.exceptions import ClientError

AWS_ACCESS_KEY_ID = config('ACCESS_KEY')
AWS_SECRET_ACCESS_KEY = config('SECRET_KEY')
REGION_NAME = "us-east-2" # Ohio

session = boto3.session.Session(aws_access_key_id=AWS_ACCESS_KEY_ID,
                                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                                region_name=REGION_NAME)

ec2_ohio = session.resource("ec2")
client_ohio = session.client("ec2")


key_name = "evandrofrKey"
file_name = "{0}.pem".format(key_name)

def key_pair(client, key_name):
    file_name = "{0}.pem".format(key_name)
    try:
        keyPair = ec2_ohio.create_key_pair(KeyName=key_name)
        with open(file_name, "w") as file:
            file.write(keyPair.key_material)
        os.system("chmod 400 {0}.pem".format(key_name))
        print("Ohio Database key pair criada com sucesso...")
    except:
        print("Ohio Database key pair já existe...")

def security_group(ec2_client, name, description):
    print("entrei")
    sg_response = ec2_client.describe_security_groups()
    for group in sg_response['SecurityGroups']:
        if group['GroupName'] == name:
            ec2_client.delete_security_group(GroupName=name)


    response = ec2_client.describe_vpcs()
    vpc_id = response.get('Vpcs', [{}])[0].get('VpcId', '')
    try:
        response = ec2_client.create_security_group(GroupName=name,
                                            Description=description,
                                            VpcId=vpc_id)
        security_group_id = response['GroupId']
        print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

        data = ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ])
        return security_group_id
    except ClientError as e:
        print(e)


sg_id = security_group(client_ohio,'security','description')
print(sg_id)
key_pair(client_ohio, key_name)

id_AMI = "ami-0dd9f0e7df0f0a138"
userdata = """
#!/bin/bash
sudo apt update
touch teste.txt
git clone https://github.com/evandrofr/Cloud.git
"""
id_instance = ec2_ohio.create_instances(ImageId=id_AMI,
                                        MinCount=1,
                                        MaxCount=1,
                                        InstanceType="t2.micro",
                                        SecurityGroupIds=[sg_id],
                                        KeyName=key_name,
                                        UserData=userdata
                                        )
print(id_instance)

# instance_id = client_ohio.describe_instances()
# print(instance_id)