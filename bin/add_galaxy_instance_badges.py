#!/usr/bin/env python
import argparse
import glob
import os
import re
import requests
import shutil
import subprocess
import time
import yaml
import csv


def extract_public_galaxy_servers(public_servers_url):
    """Extract a list of dictionaries for each public server."""
    csv_contents = requests.get(public_servers_url).text.splitlines()
    reader = csv.reader(csv_contents)
    header = next(reader)
    for row in reader:
        yield dict(zip(header, row))


def discover_trainings(topics_dir):
    """Auto-discover all topic metadata files."""
    for training in glob.glob(os.path.join(topics_dir, '*', 'metadata.yaml')):
        with open(training, 'r') as handle:
            training_data = yaml.load(handle)
            for material in training_data['material']:
                yield material['name'], material['title']


def safe_name(server, dashes=True):
    """Make human strings 'safe' for usage in paths."""
    safe_name = re.sub('\s', '_', server)
    if dashes:
        safe_name = re.sub('[^A-Za-z0-9_-]', '_', safe_name)
    else:
        safe_name = re.sub('[^A-Za-z0-9_]', '_', safe_name)

    return server


def get_badge_path(training, supported):
    """Return a string representing the expected badge filename. Returns something like 'Training Name|Supported' or 'Training Name|Unsupported'."""
    if supported:
        return '%s-%s-green.svg' % (training, 'Supported')

    return '%s-%s-gray.svg' % (training, 'Unsupported')


def realise_badge(badge, badge_cache_dir):
    """Download the badge to the badge_cache_dir (if needed) and return this real path to the user."""
    if not os.path.exists(badge, badge_cache_dir):
        # Download the missing image
        cmd = [
            'wget', 'https://img.shields.io/badge/%s' % badge,
            '--quiet', '-O', os.path.join(badge_cache_dir, badge)
        ]
        subprocess.check_call(cmd)
        # Be nice to their servers
        time.sleep(1.5)
    return os.path.join(badge_cache_dir, badge)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build the badge directory for instances to use.')
    parser.add_argument('--public-server-list', help='Url to access the public galaxy server list at',
                        default='https://raw.githubusercontent.com/martenson/public-galaxy-servers/master/servers.csv')
    parser.add_argument('--topics-directory', help='Path to the topics directory', default='./topics/')
    parser.add_argument('--instances', help='File containing the instances and their supported trainings', default='metadata/instances.yaml')

    parser.add_argument('--output', help='Path to the the directory where the badges should be stored. The directory will be created if it does not exist.', default='output')
    args = parser.parse_args()

    # Validate training dir argument
    if not os.path.exists(args.topics_directory) and os.path.is_dir(args.topics_directory):
        raise Exception("Invalid topics directory")
    trainings = dict(discover_trainings(args.topics_directory))
    training_keys = sorted(trainings.keys())
    if len(trainings) == 0:
        raise Exception("No trainings discovered!")

    # Create output directory if not existing.
    if not os.path.exists(args.output):
        os.makedirs(args.output)

    # Also check/create the badge cache directory.
    CACHE_DIR = os.path.join(args.output, '.cache')
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    # Load the validated list of instances which support trainings
    with open(args.instances, 'r') as handle:
        data = yaml.load(handle)

    instances = list(extract_public_galaxy_servers(args.public_server_list))
    index_html = open(os.path.join(args.output, 'index.html'), 'w')

    index_html.write("""
<html><head></head>
<body>
<h1>Galaxy Training Support</h1>
<p>
These badges are the results of regularly checking in with your Galaxy
instance to see if you support the various training courses that are available
to end users. This requires having all of the appropriate tools installed and
possibly datasets in specifically named data libraries.
</p>
<table>
    <thead>
          """)

    index_html.write("<tr>")
    index_html.write('<th>Instance</th>')
    for category in data:
        for training in data[category]:
            index_html.write('<th>' + training + '</th>')
    index_html.write("</tr>")
    index_html.write("</thead><tbody>")

    # All instances, not just checked
    for instance in instances:
        index_html.write('<tr><td>' + instance + '</td><td>')
        for category in data:
            # All trainings, not just those available
            for training in data[category]:
                # If available, green badge
                is_supported = training in data[category] and instance['name'] in data[category][training]
                # Get a path to a (cached) badge file.
                real_badge_path = realise_badge(get_badge_path(trainings[training], is_supported), CACHE_DIR)
                # Deteremine the per-instance output name
                output_filename = safe_name(instance['name']) + '__' + safe_name(training, dashes=True) + '.svg'
                output_filepath = os.path.join(args.output, output_filename)
                # Copy the badge to a per-instance named .svg file.
                shutil.copy(real_badge_path, output_filepath)
                # Write the table column
                index_html.write('<td><img src="' + output_filename + '"/></td>')

        index_html.write('</td></tr>')
    index_html.write("</tbody></table></body></html>")
