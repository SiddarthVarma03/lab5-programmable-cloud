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

BASE_INSTANCE = 'lab5-part1'
SNAPSHOT_NAME = 'base-snapshot-' + BASE_INSTANCE

CLONE_NAMES = [
    'lab5-clone-1',
    'lab5-clone-2',
    'lab5-clone-3'
]

def wait_for_zone_operation(compute, project, zone, operation):
    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation
        ).execute()

        if result['status'] == 'DONE':
            if 'error' in result:
                raise Exception(result['error'])
            return result

        time.sleep(1)

def wait_for_global_operation(compute, project, operation):
    while True:
        result = compute.globalOperations().get(
            project=project,
            operation=operation
        ).execute()

        if result['status'] == 'DONE':
            if 'error' in result:
                raise Exception(result['error'])
            return result

        time.sleep(1)

def get_boot_disk(compute, project, zone, instance_name):
    instance = compute.instances().get(
        project=project,
        zone=zone,
        instance=instance_name
    ).execute()

    for disk in instance['disks']:
        if disk.get('boot'):
            return disk['source'].split('/')[-1]

    raise Exception("Boot disk not found")

def create_snapshot(compute, project, zone, instance_name, snapshot_name):
    disk_name = get_boot_disk(
        compute,
        project,
        zone,
        instance_name
    )

    print("Boot disk:", disk_name)
    print("Creating snapshot:", snapshot_name)

    snapshot_body = {
        'name': snapshot_name
    }

    operation = compute.disks().createSnapshot(
        project=project,
        zone=zone,
        disk=disk_name,
        body=snapshot_body
    ).execute()

    wait_for_zone_operation(
        compute,
        project,
        zone,
        operation['name']
    )

    print("Snapshot created successfully.")

def get_snapshot_url(compute, project, snapshot_name):
    snapshot = compute.snapshots().get(
        project=project,
        snapshot=snapshot_name
    ).execute()

    return snapshot['selfLink']

def create_instance_from_snapshot(compute, project, zone, name, snapshot_url):
    machine_type = "zones/%s/machineTypes/f1-micro" % zone

    config = {
        'name': name,
        'machineType': machine_type,

        'disks': [
            {
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceSnapshot': snapshot_url
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

        'tags': {
            'items': ['allow-5000']
        }
    }

    return compute.instances().insert(
        project=project,
        zone=zone,
        body=config
    ).execute()

def create_and_time_clone(compute, project, zone, name, snapshot_url):
    print("Creating clone:", name)

    start_time = time.time()

    operation = create_instance_from_snapshot(
        compute,
        project,
        zone,
        name,
        snapshot_url
    )

    wait_for_zone_operation(
        compute,
        project,
        zone,
        operation['name']
    )

    end_time = time.time()
    elapsed_time = end_time - start_time

    print(
        "{} created in {:.2f} seconds".format(
            name,
            elapsed_time
        )
    )

    return elapsed_time

def write_timing_file(results):
    with open('TIMING.md', 'w') as timing_file:
        timing_file.write("# Part 2 VM Creation Timing\n\n")

        for name, elapsed_time in results:
            timing_file.write(
                "{}: {:.2f} seconds\n".format(
                    name,
                    elapsed_time
                )
            )

    print("Timing results written to TIMING.md")

def main():
    print("Project:", project)
    print("Base instance:", BASE_INSTANCE)

    create_snapshot(
        service,
        project,
        ZONE,
        BASE_INSTANCE,
        SNAPSHOT_NAME
    )

    snapshot_url = get_snapshot_url(
        service,
        project,
        SNAPSHOT_NAME
    )

    print("Snapshot URL:", snapshot_url)

    timing_results = []

    for clone_name in CLONE_NAMES:
        elapsed_time = create_and_time_clone(
            service,
            project,
            ZONE,
            clone_name,
            snapshot_url
        )

        timing_results.append(
            (clone_name, elapsed_time)
        )

    write_timing_file(timing_results)

    print("Part 2 completed successfully.")


if __name__ == '__main__':
    main()