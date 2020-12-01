import boto3
import os
import time
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

name_LB = 'LBORM'
name_AS = 'ASORM'
name_SG_ohio = 'security_ohio'
name_SG_oregon = 'security_oregon'
name_AMI = 'ORM_AMI'
name_LC = 'LC_ORM'
tag_ohio = 'DB'
tag_oregon = 'ORM'

### FUNÇÕES DELETE
def delete_autoscaling(session, name, region):
    client = session.client('autoscaling', region_name=region)

    print("Deletando Autoscaling...")
    try:
        response = client.describe_auto_scaling_groups()
        for group in response['AutoScalingGroups']:
            if group['AutoScalingGroupName'] == name:
                client.delete_auto_scaling_group(
                        AutoScalingGroupName=name,
                        ForceDelete=True
                )
        time.sleep(20)
        print("Autoscaling deletado com sucesso")
    except ClientError as e:
        print('Error no AS', e)

def delete_launch_configuration(session, name, region):
    client = session.client('autoscaling', region_name=region)
    
    print("Deletando Launch configuration...")
    try:
        if len(client.describe_launch_configurations(LaunchConfigurationNames=[name])['LaunchConfigurations']):
            response = client.delete_launch_configuration(
                LaunchConfigurationName=name
                )
            print("Launch_configuration deletado com sucesso.")

    except ClientError as e:
        print('Error no LC', e)

def delete_loadbalancer(session, name, region):
    client = session.client('elb', region_name=region)

    print("Deletando LoadBalancer...")
    try:
        client.delete_load_balancer(LoadBalancerName=name)
        print("Load Balancer deletado com sucesso.")
    except ClientError as e:
        print('Error no LB', e)

def delete_AMI(client, name):
    print("Deletando AMI...")
    try:
        AMI_id = client.describe_images(
        Filters=[{  'Name': 'name',
                    'Values': [name] }]
        )

        if len(AMI_id["Images"]) > 0:
            AMI_id = AMI_id["Images"][0]["ImageId"]
            response = client.deregister_image(ImageId=AMI_id)
            print("AMI deleteada com sucesso.")
    
    except ClientError as e:
        print('Error na AMI', e)

def terminate_instance(resource, client, name):
    print("Deletando Instacia {}...".format(name))
    try:
        instaces = resource.instances.filter(Filters=[
            {'Name': 'tag:Name', 'Values': [name]}
        ])
        instaces_id = []
        for instance in instaces:
            instaces_id.append(instance.id)
        if len(instaces_id) > 0:
            terminate_waiter = client.get_waiter('instance_terminated')
            instaces.terminate()
            terminate_waiter.wait(InstanceIds=instaces_id)
            print("Instancia {} deletada".format(name))    
        
    except ClientError as e:
        print('Error na Instancia {}'.format(name), e)


### FUNÇÕES CREATE
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

        ec2_client.authorize_security_group_ingress(
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
             'FromPort': 80,
             'ToPort': 80,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])
        return security_group_id
    except ClientError as e:
        print(e)

def create_AMI(client, instance, name):
    print("Criando imagem...")
    waiter = client.get_waiter('image_available')
    image = client.create_image(InstanceId=instance[0].id, NoReboot=True, Name=name)
    waiter.wait(ImageIds=[image["ImageId"]])
    print("AMI criada com sucesso.")
    return image['ImageId']


def create_launch_configuration(session, nameLC, sg_id, keypair, AMI, region):
    client = session.client('autoscaling', region_name=region)

    print("Criando Launch Configuration...")
    client.create_launch_configuration(
        LaunchConfigurationName=nameLC,
        ImageId=AMI,
        KeyName=keypair,
        SecurityGroups=[sg_id],
        InstanceType='t2.micro'
    )
    print("Launch Configuration criado.")

def create_load_balancer(session, nameLB, sg_id, region):
    client = session.client('elb', region_name=region)

    print("Criando LoadBalancer...")
    res = client.create_load_balancer(
        LoadBalancerName=nameLB,
        Listeners=[
            {
                'Protocol':'HTTP',
                'LoadBalancerPort':80,
                'InstancePort':8080
            }
        ],
        AvailabilityZones=[
            'us-west-2a',
            'us-west-2b',
            'us-west-2c',
            'us-west-2d',
        ],
        SecurityGroups=[sg_id],
        Tags=[
            {'Key': 'Name', 'Value': 'LBORM'},
        ]
    )
    with open("DNSName.txt", "w") as file:
            file.write(res['DNSName'])
    print("LoadBalancer criado.")

def create_auto_scalling(session, AutoScalingGroupName, LaunchConfigurationName, region):
    client = session.client('autoscaling', region_name=region)

    print("Criando AS...")
    client.create_auto_scaling_group(
        AutoScalingGroupName=AutoScalingGroupName,
        LaunchConfigurationName=LaunchConfigurationName,
        MinSize=2,
        MaxSize=5,
        DesiredCapacity=2,
        AvailabilityZones=[
            'us-west-2a',
            'us-west-2b',
            'us-west-2c',
            'us-west-2d',
        ],
        LoadBalancerNames=['LBORM'],
        CapacityRebalance=True
    )
    print("AS criado.")

### APAGANDO ANTES DE COMEÇAR
delete_autoscaling(session_oregon, name_AS, REGION_NAME_Oregon)
delete_launch_configuration(session_oregon, name_LC, REGION_NAME_Oregon)
delete_loadbalancer(session_oregon, name_LB, REGION_NAME_Oregon)
delete_AMI(client_oregon, name_AMI)
terminate_instance(ec2_ohio, client_ohio, tag_ohio)

### COMEÇO
sg_id_ohio = security_group(client_ohio, name_SG_ohio,'description')
print(sg_id_ohio)
sg_id_oregon = security_group(client_oregon,name_SG_oregon,'description')
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
sudo echo host all all 0.0.0.0/0 trust >> /etc/postgresql/10/main/pg_hba.conf
echo "6">>log.txt
cd /
cd home/ubuntu
echo "7">>log.txt
sudo ufw allow 5432/tcp
echo "8">>log.txt
sudo systemctl restart postgresql
"""
# terminate_instance(ec2_ohio,client_ohio,"DB")
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
                                                                        'Key': 'Name',
                                                                        'Value': tag_ohio,
                                                                    },
                                                                ],
                                                            },
                                                        ]
                                        )
print("Waiting...")
id_instance_ohio[0].wait_until_running()
print("Instancia Ohio rodando.")
#teste -> psql -h localhost -p 5432 -U cloud tasks



Filters = [{'Name':'tag:Name','Values':[tag_ohio]},
           {'Name':'instance-state-name','Values':['running']}]

instances = client_ohio.describe_instances(Filters=Filters)
public_ip = instances['Reservations'][0]['Instances'][0]['PublicIpAddress']
print("ip: ", public_ip)


userdata_oregon = """#!/bin/sh
cd home/ubuntu
sudo apt update
echo "1">>log.txt
git clone https://github.com/evandrofr/tasks.git    
echo "2">>log.txt
sudo sed -i 's/node1/{0}/' /home/ubuntu/tasks/portfolio/settings.py
echo "3">>log.txt
cd tasks
./install.sh    
cd ..
echo "4">>log.txt
sudo reboot
""".format(public_ip)


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
                                                                        'Key': 'Name',
                                                                        'Value': tag_oregon,
                                                                    },
                                                                ],
                                                            },
                                                        ]
                                        )

print("Waiting...")
id_instance_oregon[0].wait_until_running()
print(id_instance_oregon[0])
res = client_oregon.describe_instance_status(InstanceIds=[id_instance_oregon[0].id])
while (res['InstanceStatuses'][0]['InstanceStatus']['Status'] != 'ok'):
    print("Status: {}".format(res['InstanceStatuses'][0]['InstanceStatus']['Status']))
    time.sleep(20)
    res = client_oregon.describe_instance_status(InstanceIds=[id_instance_oregon[0].id])
print("Instancia Oregon rodando.")


print(id_instance_ohio)
print(id_instance_oregon)

image_id = create_AMI(client_oregon, id_instance_oregon, name_AMI)

terminate_instance(ec2_oregon, client_oregon, tag_oregon)

create_launch_configuration(session_oregon, name_LC, sg_id_oregon, key_name_oregon, image_id, REGION_NAME_Oregon)

create_load_balancer(session_oregon, name_LB, sg_id_oregon, REGION_NAME_Oregon)

create_auto_scalling(session_oregon, name_AS, name_LC, REGION_NAME_Oregon)
# waiter = client_ohio.get_waiter('instance_running')
# waiter.wait(InstanceIds=id_instance_ohio.id)