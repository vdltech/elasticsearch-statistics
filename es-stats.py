#!/usr/bin/env python

from flask import Flask, Response, current_app, send_from_directory, request
import json
from elasticsearch import Elasticsearch
import re
import yaml
import sys
import getopt

app = Flask(__name__)

def getconfig(argv):
    ''' process command line arguments '''
    try:
        opts, _ = getopt.getopt(argv, "c:h", ['config', 'help'])  # pylint: disable=unused-variable
        if not opts:
            raise SystemExit(usage())
    except getopt.GetoptError:
        raise SystemExit(usage())

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit(2)
        elif opt in ('-c', '--config'):
            with open(arg, 'r') as stream:
                config = yaml.load(stream, Loader=yaml.FullLoader)
        else:
            raise SystemExit(usage())

    return config

def usage():
    ''' usage info '''
    output = """
Usage:
  es-stats.py -c configfile
Options:
  -c <configfile>   Read config from configfile"""

    return output

@app.route("/")
def hello():
    return current_app.send_static_file('index.html')


@app.route("/js/<path:path>")
def send_js(path):
    return send_from_directory('js', path)


@app.route("/bower_components/<path:path>")
def send_bower(path):
    return send_from_directory('bower_components', path)


@app.route("/css/<path:path>")
def send_css(path):
    return send_from_directory('css', path)


@app.route("/views/<path:path>")
def send_view(path):
    return send_from_directory('views', path)


def index_prefix(name):
  match = re.search(r'(\D*).*', name)
  prefix = match.group(1).rstrip('_-')

  reindex_search = re.search(r'(.*)-reindexed.*', prefix)
  if reindex_search:
    prefix = reindex_search.group(1)

  return prefix

def is_rollover(name):
  match = re.search(r'\d{6}', name)
  if match:
    return True
  return False

def is_time_based(name):
  if not is_rollover(name):
    match = re.search(r'\d{4}\.', name)
    if match:
      return True
  return False

@app.route("/indices")
def indices():
  indices = index_summary()

  result = {
    'indices': indices,
    'tiers': tiers(indices)
  }
  return Response(json.dumps(result), mimetype="application/json")

@app.route("/tier")
def tier():
  tier = request.args.get('tier')

  result = tiers(index_summary())
  return Response(json.dumps(result), mimetype="application/json")


def tiers(indices):
  tiers = {
    'hot': {
      'name': 'hot',
      'docs': 0,
      'pri_size': 0,
      'total_size': 0,
      'shards': 0,
      'count': 0,
    }, 
    'warm': {
      'name': 'warm',
      'docs': 0,
      'pri_size': 0,
      'total_size': 0,
      'shards': 0,
      'count': 0,
    }
  }

  for item in indices:
    for tier in ['hot', 'warm']:
      tiers[tier]['docs'] += item[tier]['docs']
      tiers[tier]['pri_size'] += item[tier]['pri_size']
      tiers[tier]['total_size'] += item[tier]['total_size']
      tiers[tier]['shards'] += item[tier]['shards']
      tiers[tier]['count'] += item[tier]['count']
  
  return tiers

def index_summary():
  client = Elasticsearch(ELASTICSEARCH_HOST)

  indices = client.cat.indices(format="json",bytes="b")
  indices_settings = client.indices.get_settings(flat_settings=True,name="index.routing*")

  summary = {}

  # Generate initial summary by index prefix
  for index in indices:
    prefix = index_prefix(index['index'])
    tier = indices_settings[index['index']]['settings']['index.routing.allocation.require.data']

    if prefix not in summary.keys():
      summary[prefix] = {
        "time_based": False,
        "rollover": False,
        "hot": {
          'docs': 0,
          'pri_size': 0,
          'total_size': 0,
          'shards': 0,
          'count': 0,
          'rollover_count': 0,
        },
        "warm": {
          'docs': 0,
          'pri_size': 0,
          'total_size': 0,
          'shards': 0,
          'count': 0,
          'rollover_count': 0,
        }
      }

    if is_time_based(index['index']):
      summary[prefix]['time_based'] = True
    summary[prefix][tier]['docs'] += int(index['docs.count'])
    summary[prefix][tier]['pri_size'] += int(index['pri.store.size'])
    summary[prefix][tier]['total_size'] += int(index['store.size'])
    summary[prefix][tier]['shards'] += int(index['pri'])
    summary[prefix][tier]['count'] += 1
    if is_rollover(index['index']):
      summary[prefix][tier]['rollover_count'] += 1


  for prefix in summary:
    # Total values from all tiers
    warm = summary[prefix]['warm']
    hot = summary[prefix]['hot']
    summary[prefix]['total'] = {
      'docs': warm['docs'] + hot['docs'],
      'pri_size': warm['pri_size'] + hot['pri_size'],
      'total_size': warm['total_size'] + hot['total_size'],
      'shards': warm['shards'] + hot['shards'],
      'count': warm['count'] + hot['count'],
      'rollover_count': warm['rollover_count'] + hot['rollover_count'],
    }

    # Calculate average shard sizes per tier and total
    summary[prefix]['total']['average_shard'] = summary[prefix]['total']['total_size'] / summary[prefix]['total']['shards']
    if summary[prefix]['hot']['shards'] > 0:
      summary[prefix]['hot']['average_shard'] = summary[prefix]['hot']['total_size'] / summary[prefix]['hot']['shards']
    if summary[prefix]['warm']['shards'] > 0:
      summary[prefix]['warm']['average_shard'] = summary[prefix]['warm']['total_size'] / summary[prefix]['warm']['shards']


    # Set rollover value
    if summary[prefix]['total']['rollover_count']:
      summary[prefix]['rollover'] = True

    # Set index type value 
    if summary[prefix]['rollover'] and summary[prefix]['time_based']:
      summary[prefix]['type'] = "Time based and Rollover"
    elif summary[prefix]['rollover']:
      summary[prefix]['type'] = "Rollover"
    elif summary[prefix]['time_based']:
      summary[prefix]['type'] = "Time"
    else:
      summary[prefix]['type'] = "Individual"

    # Calculate time period for time based indices
    if summary[prefix]['time_based']:
      index_names = [d['index'] for d in indices if re.match(r'{}'.format(prefix), d['index'])]
      for index in index_names:
        if is_rollover(index):
          continue
        if re.match(r'.*\d{4}\.\d{2}\.\d{2}', index):
          summary[prefix]['time_period'] = 'Daily'
          break
        match = re.match(r'.*\d{4}\.(\d{1,2})', index)
        if match:
          if int(match.group(1)) > 12:
            summary[prefix]['time_period'] = 'Weekly'
            break
          else:
            summary[prefix]['time_period'] = 'Monthly'

  array_summary = []
  for prefix, data in summary.items():
    data['name'] = prefix
    array_summary.append(data)

  return array_summary

if __name__ == "__main__":
    # Load configuration file
    config = getconfig(sys.argv[1:])
    ELASTICSEARCH_HOST = config['elasticsearch_host']

    app.run(host='0.0.0.0', port=8000)
