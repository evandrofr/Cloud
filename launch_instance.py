import boto3
import os
from decouple import config
from botocore.exceptions import ClientError

AWS_ACCESS_KEY_ID = config('ACCESS_KEY')
AWS_SECRET_ACCESS_KEY = config('SECRET_KEY')
REGION_NAME_Ohio = "us-east-2" # Ohio
REGION_NAME_Oregon = "us-west-2" # Oregon

session_ohio = boto3.session.Session(aws_access_key_id=AWS_ACCESS_KEY_ID,
                                     aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                                     region_name=REGION_NAME_Ohio)

session_oregon = boto3.session.Session(aws_access_key_id=AWS_ACCESS_KEY_ID,
                                       aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                                       region_name=REGION_NAME_Oregon)

ec2_ohio = session_ohio.resource("ec2")
client_ohio = session_ohio.client("ec2")
ec2_oregon = session_oregon.resource("ec2")
client_oregon = session_oregon.client("ec2")


key_name_ohio = "evandrofrKey"
key_name_oregon = "evandrofrKey2"

def key_pair(ec2, key_name):
    file_name = "{0}.pem".format(key_name)
    try:
        keyPair = ec2.create_key_pair(KeyName=key_name)
        with open(file_name, "w") as file:
            file.write(keyPair.key_material)
        print("{} Key pair criada com sucesso...".format(key_name))
    except:
        print("{} key pair já existe...".format(key_name))

def security_group(ec2_client, name, description):
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
             'FromPort': 8080,
             'ToPort': 8080,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 5432,
             'ToPort': 5432,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
        return security_group_id
    except ClientError as e:
        print(e)


sg_id_ohio = security_group(client_ohio,'security_ohio','description')
sg_id_oregon = security_group(client_oregon,'security_oregon','description')
print(sg_id_ohio)
print(sg_id_oregon)

key_pair(ec2_ohio, key_name_ohio)
key_pair(ec2_oregon, key_name_oregon)

id_AMI_ohio   = "ami-0dd9f0e7df0f0a138"
id_AMI_oregon = "ami-0ac73f33a1888c64a"

userdata_ohio = """#!/bin/sh
cd home/ubuntu
sudo apt update
echo "1">>log.txt
sudo apt install postgresql postgresql-contrib -y
echo "2">>log.txt
sudo -u postgres psql -c "CREATE USER cloud WITH PASSWORD 'cloud';"
echo "3">>log.txt
sudo -u postgres createdb -O cloud tasks
echo "4">>log.txt
sudo su - postgres
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" /etc/postgresql/10/main/postgresql.conf
echo "5">>log.txt
sudo echo host all all 192.168.0.0/20 trust >> /etc/postgresql/10/main/pg_hba.conf
echo "6">>log.txt
cd /
cd home/ubuntu
echo "7">>log.txt
sudo ufw allow 5432/tcp
echo "8">>log.txt
sudo systemctl restart postgresql
"""

userdata_oregon = """#!/bin/sh
cd home/ubuntu
sudo apt update
echo "1">>log.txt
git clone https://github.com/evandrofr/tasks.git
echo "2">>log.txt
./tasks/install.sh
echo "3">>log.txt
"""

# userdata="" sudo su - postgres -c "echo host all all 192.168.0.0/20 trust >> /etc/postgresql/10/main/pg_hba.conf"

id_instance_ohio = ec2_ohio.create_instances(ImageId=id_AMI_ohio,
                                        MinCount=1,
                                        MaxCount=1,
                                        InstanceType="t2.micro",
                                        SecurityGroupIds=[sg_id_ohio],
                                        KeyName=key_name_ohio,
                                        UserData=userdata_ohio,
                                        TagSpecifications=[
                                                            {
                                                                'ResourceType': 'instance',
                                                                'Tags': [
                                                                    {
                                                                        'Key': 'Ohio',
                                                                        'Value': 'DB',
                                                                    },
                                                                ],
                                                            },
                                                        ]
                                        )


id_instance_oregon = ec2_oregon.create_instances(ImageId=id_AMI_oregon,
                                        MinCount=1,
                                        MaxCount=1,
                                        InstanceType="t2.micro",
                                        SecurityGroupIds=[sg_id_oregon],
                                        KeyName=key_name_oregon,
                                        UserData=userdata_oregon,
                                        TagSpecifications=[
                                                            {
                                                                'ResourceType': 'instance',
                                                                'Tags': [
                                                                    {
                                                                        'Key': 'Oregon',
                                                                        'Value': 'ORM',
                                                                    },
                                                                ],
                                                            },
                                                        ]
                                        )
print(id_instance_ohio)
print(id_instance_oregon)

# instance_id = client_ohio.describe_instances()
# print(instance_id)