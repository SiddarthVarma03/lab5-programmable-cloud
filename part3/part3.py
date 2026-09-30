import os
import time
import googleapiclient.discovery
from google.oauth2 import service_account

ZONE = 'us-west1-a'
VM1_NAME = 'lab5-vm1'
VM2_NAME = 'lab5-vm2'

credentials = service_account.Credentials.from_service_account_file(
    filename='service-credentials.json'
)

project = os.getenv('GOOGLE_CLOUD_PROJECT') or 'csci5253-lab2'

service = googleapiclient.discovery.build(
    'compute',
    'v1',
    credentials=credentials
)


def wait_for_zone_operation(compute, project, zone, operation):
    print("Waiting for operation to finish...")

    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation['name'] if isinstance(operation, dict) else operation
        ).execute()

        if result['status'] == 'DONE':
            if 'error' in result:
                raise Exception(result['error'])

            print("Operation completed.")
            return result

        time.sleep(1)

def get_vm2_startup_script():
    return """#!/bin/bash
apt-get update
apt-get install -y python3-pip
pip3 install flask

cat > /home/flask_app.py <<'EOF'
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello from VM-2!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
EOF

python3 /home/flask_app.py
"""

def create_vm2(compute, project, zone):
    print("Creating VM-2...")

    startup_script = get_vm2_startup_script()

    config = {
        'name': VM2_NAME,
        'machineType': f'zones/{zone}/machineTypes/e2-small',

        'disks': [
            {
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage':
                        'projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts'
                }
            }
        ],

        'networkInterfaces': [
            {
                'network': 'global/networks/default',
                'accessConfigs': [
                    {
                        'type': 'ONE_TO_ONE_NAT',
                        'name': 'External NAT'
                    }
                ]
            }
        ],

        'metadata': {
            'items': [
                {
                    'key': 'startup-script',
                    'value': startup_script
                }
            ]
        },

        'tags': {
            'items': ['allow-5000']
        }
    }

    operation = compute.instances().insert(
        project=project,
        zone=zone,
        body=config
    ).execute()

    wait_for_zone_operation(compute, project, zone, operation)

    print("VM-2 created successfully.")

def get_vm1_startup_script():
    return """#!/bin/bash
mkdir -p /srv
cd /srv

curl http://metadata/computeMetadata/v1/instance/attributes/vm2-startup-script \
-H "Metadata-Flavor: Google" > vm2-startup-script.sh

curl http://metadata/computeMetadata/v1/instance/attributes/service-credentials \
-H "Metadata-Flavor: Google" > service-credentials.json

curl http://metadata/computeMetadata/v1/instance/attributes/vm1-launch-vm2-code \
-H "Metadata-Flavor: Google" > vm1-launch-vm2-code.py

curl http://metadata/computeMetadata/v1/instance/attributes/project \
-H "Metadata-Flavor: Google" > project.txt

export GOOGLE_CLOUD_PROJECT=$(cat project.txt)

apt-get update
apt-get install -y python3-pip
pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

python3 /srv/vm1-launch-vm2-code.py
"""

def get_vm1_launch_code():
    return r'''
import os
import time
import googleapiclient.discovery
from google.oauth2 import service_account

ZONE = "us-west1-a"
VM2_NAME = "lab5-vm2"

credentials = service_account.Credentials.from_service_account_file(
    "/srv/service-credentials.json"
)

project = os.environ["GOOGLE_CLOUD_PROJECT"]

compute = googleapiclient.discovery.build(
    "compute",
    "v1",
    credentials=credentials
)

with open("/srv/vm2-startup-script.sh", "r") as f:
    startup_script = f.read()

config = {
    "name": VM2_NAME,
    "machineType": f"zones/{ZONE}/machineTypes/e2-small",

    "disks": [{
        "boot": True,
        "autoDelete": True,
        "initializeParams": {
            "sourceImage":
                "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
        }
    }],

    "networkInterfaces": [{
        "network": "global/networks/default",
        "accessConfigs": [{
            "type": "ONE_TO_ONE_NAT",
            "name": "External NAT"
        }]
    }],

    "metadata": {
        "items": [{
            "key": "startup-script",
            "value": startup_script
        }]
    },

    "tags": {
        "items": ["allow-5000"]
    }
}

print("VM-1 is creating VM-2...")

operation = compute.instances().insert(
    project=project,
    zone=ZONE,
    body=config
).execute()

while True:
    result = compute.zoneOperations().get(
        project=project,
        zone=ZONE,
        operation=operation["name"]
    ).execute()

    if result["status"] == "DONE":
        if "error" in result:
            raise Exception(result["error"])
        break

    time.sleep(1)

print("VM-2 created successfully.")
'''

def create_vm1(compute, project, zone):
    print("Creating VM-1...")

    vm1_startup_script = get_vm1_startup_script()
    vm2_startup_script = get_vm2_startup_script()
    vm1_launch_code = get_vm1_launch_code()

    with open("service-credentials.json", "r") as f:
        service_credentials = f.read()

    config = {
        "name": VM1_NAME,

        "machineType": f"zones/{zone}/machineTypes/e2-small",

        "disks": [{
            "boot": True,
            "autoDelete": True,
            "initializeParams": {
                "sourceImage":
                    "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
            }
        }],

        "networkInterfaces": [{
            "network": "global/networks/default",
            "accessConfigs": [{
                "type": "ONE_TO_ONE_NAT",
                "name": "External NAT"
            }]
        }],

        "metadata": {
            "items": [
                {
                    "key": "startup-script",
                    "value": vm1_startup_script
                },
                {
                    "key": "vm2-startup-script",
                    "value": vm2_startup_script
                },
                {
                    "key": "service-credentials",
                    "value": service_credentials
                },
                {
                    "key": "vm1-launch-vm2-code",
                    "value": vm1_launch_code
                },
                {
                    "key": "project",
                    "value": project
                }
            ]
        }
    }

    operation = compute.instances().insert(
        project=project,
        zone=zone,
        body=config
    ).execute()

    wait_for_zone_operation(
        compute,
        project,
        zone,
        operation
    )

    print("VM-1 created successfully.")

def main():
    print("Starting Part 3...")
    print("Project:", project)
    print("Zone:", ZONE)

    create_vm1(
        service,
        project,
        ZONE
    )

    print("VM-1 has been created.")
    print("VM-1 will now create VM-2 through its startup script.")


if __name__ == "__main__":
    main()
