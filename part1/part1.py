#!/usr/bin/env python3

import argparse
import os
import time
from pprint import pprint

import googleapiclient.discovery
import google.auth

credentials, project = google.auth.default()
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)
ZONE = 'us-west1-b'
INSTANCE_NAME = 'lab5-part1'

startup_script = """#!/bin/bash
apt-get update
apt-get install -y python3 python3-pip git

mkdir -p /opt/lab5
cd /opt/lab5

git clone https://github.com/cu-csci-4253-datacenter/flask-tutorial.git
cd flask-tutorial

python3 setup.py install
pip3 install -e .

export FLASK_APP=flaskr
flask init-db

nohup flask run -h 0.0.0.0 > /var/log/flask.log 2>&1 &
"""

def create_instance(compute, project, zone, name, startup_script):
    image_response = compute.images().getFromFamily(
        project='ubuntu-os-cloud',
        family='ubuntu-2204-lts'
    ).execute()

    source_disk_image = image_response['selfLink']

    machine_type = "zones/%s/machineTypes/f1-micro" % zone

    config = {
        'name': name,
        'machineType': machine_type,

        'disks': [
            {
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage': source_disk_image
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

    return compute.instances().insert(
        project=project,
        zone=zone,
        body=config
    ).execute()

def wait_for_operation(compute, project, zone, operation):
    print("Waiting for operation to finish...")

    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation
        ).execute()

        if result['status'] == 'DONE':
            print("Operation completed.")

            if 'error' in result:
                raise Exception(result['error'])

            return result

        time.sleep(1)

def create_firewall_rule(compute, project):
    firewall_name = 'allow-5000'

    try:
        compute.firewalls().get(
            project=project,
            firewall=firewall_name
        ).execute()

        print("Firewall rule allow-5000 already exists.")

    except Exception:
        print("Creating firewall rule allow-5000...")

        firewall_body = {
            'name': firewall_name,
            'network': 'global/networks/default',
            'allowed': [
                {
                    'IPProtocol': 'tcp',
                    'ports': ['5000']
                }
            ],
            'sourceRanges': ['0.0.0.0/0'],
            'targetTags': ['allow-5000']
        }

        compute.firewalls().insert(
            project=project,
            body=firewall_body
        ).execute()

        print("Firewall rule creation requested.")

def get_external_ip(compute, project, zone, name):
    instance = compute.instances().get(
        project=project,
        zone=zone,
        instance=name
    ).execute()

    return instance['networkInterfaces'][0]['accessConfigs'][0]['natIP']

def main():
    print("Project:", project)
    print("Creating firewall rule...")
    create_firewall_rule(service, project)

    print("Creating VM:", INSTANCE_NAME)

    operation = create_instance(
        service,
        project,
        ZONE,
        INSTANCE_NAME,
        startup_script
    )

    wait_for_operation(
        service,
        project,
        ZONE,
        operation['name']
    )

    ip_address = get_external_ip(
        service,
        project,
        ZONE,
        INSTANCE_NAME
    )

    print("VM created successfully.")
    print("External IP:", ip_address)
    print("Flask application:")
    print("http://{}:5000".format(ip_address))


if __name__ == '__main__':
    main()