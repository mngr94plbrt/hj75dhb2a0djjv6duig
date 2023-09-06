import random
import string
import boto3
import time

dump = []
regions = []

with open('data.txt', 'r') as file:
    for line in file:
        x = line.split(" == ")
        region = x[1]
        limit_tmp = x[0]
        limit_tmp = limit_tmp[:-2]
        limit_tmp = int(limit_tmp)
        if limit_tmp > 5:
            limit = limit_tmp
            dump.append(str(region))
        else:
            continue
regions_tmp = [r.replace("\n", "") for r in dump]
print(limit)
for ulang in range(3):
    pick = random.choice(regions_tmp)
    regions.append(pick)
    regions_tmp.remove(pick)

# Menyimpan data subnet ke dalam file subnet.txt
def save_subnet_data(subnets):
    with open('subnet.txt', 'w') as file:
        for region, subnet_list in subnets.items():
            file.write(f"{region} = {', '.join(subnet_list)}\n")

# Membaca data subnet dari file subnet.txt
def read_subnet_data():
    subnets = {}
    with open('subnet.txt', 'r') as file:
        for line in file:
            region, subnet_data = line.strip().split(' = ')
            subnets[region] = subnet_data.split(', ')
    return subnets

# Menghapus file subnet.txt
def delete_subnet_file():
    import os
    if os.path.exists('subnet.txt'):
        os.remove('subnet.txt')
        os.remove("data.txt")

# Mengambil data subnet dari setiap region dan menyimpannya ke dalam file subnet.txt
def get_subnet_data():
    subnets = {}
    for region in regions:
        ec2_client = boto3.client('ec2', region_name=region)
        response = ec2_client.describe_subnets(Filters=[{'Name': 'default-for-az', 'Values': ['true']}])
        subnet_list = [subnet['SubnetId'] for subnet in response['Subnets']]
        
        if not subnet_list:
            # Buat VPC default di region yang tidak memiliki subnet
            vpc_response = ec2_client.create_default_vpc()
            vpc_id = vpc_response['Vpc']['VpcId']
            
            # Tunggu hingga VPC selesai dibuat
            while True:
                vpc_response = ec2_client.describe_vpcs(VpcIds=[vpc_id])
                state = vpc_response['Vpcs'][0]['State']
                if state == 'available':
                    break
                time.sleep(5)
            
            # Dapatkan subnet baru dari VPC default yang dibuat
            response = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
            subnet_list = [subnet['SubnetId'] for subnet in response['Subnets']]
        
        subnets[region] = subnet_list
    return subnets

# Input dari user
x = random.randint(7,9)
letters = string.ascii_uppercase + string.digits
cluster_name = 'B'+''.join(random.choice(letters) for i in range(x))
if limit == 32:
    cpu = 8192
    memory = 16384
    desired_count = 6
elif limit == 64:
    cpu = 16384
    memory = 32768
    desired_count = 8
elif limit == 256:
    cpu = 16384
    memory = 32768
    desired_count = 14
docker_image = input("Masukkan nama image Docker: ")

# Mendapatkan data subnet
subnet_data = get_subnet_data()

# Menyimpan data subnet ke dalam file subnet.txt
save_subnet_data(subnet_data)

# Definisi tugas JSON
task_definition = {
    "family": "task-2",
    "networkMode": "awsvpc",
    "containerDefinitions": [
        {
            "name": "fargate-app",
            "image": docker_image,
            "command": []
        }
    ],
    "requiresCompatibilities": [
        "FARGATE"
    ],
    "cpu": str(cpu),
    "memory": str(memory)
}

# Membuat layanan di setiap region dengan menggunakan data subnet
for region, subnet_ids in subnet_data.items():
    # Buat objek klien ECS di region yang diinginkan
    ecs = boto3.client('ecs', region_name=region)
    
    # Buat cluster baru
    response = ecs.create_cluster(clusterName=cluster_name)
    print(f"Cluster {cluster_name} berhasil dibuat di region {region}")
    
    # Buat definisi tugas
    response = ecs.register_task_definition(**task_definition)
    print(f"Definisi tugas berhasil dibuat di region {region}")
    
    # Buat layanan dengan subnet dari file subnet.txt
    if subnet_ids:
        response = ecs.create_service(
            cluster=cluster_name,
            serviceName=f"{cluster_name}-service",
            taskDefinition=task_definition['family'],
            capacityProviderStrategy=[
                {
                    'capacityProvider': 'FARGATE',
                    'weight': 1
                },
                {
                    'capacityProvider': 'FARGATE_SPOT',
                    'weight': 1
                }
            ],
            desiredCount=desired_count,
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': subnet_ids,
                    'assignPublicIp': 'ENABLED'
                }
            }
        )
        print(f"Layanan berhasil dibuat di region {region} dengan subnet {', '.join(subnet_ids)}")
    else:
        print(f"Tidak ada subnet yang tersedia di region {region}")

# Hapus file subnet.txt setelah selesai
delete_subnet_file()

print("DONE!")
