#!/usr/bin/env python3

### QUEUE CONFIGS ###

# functions used to select which type of queue to use. They must accept any number
# of keyword arguments and should only return a boolean (see autotest_enqueuer._get_queue)
def batch_filter(**kwargs):
    return kwargs.get('batch_id') is not None

def single_filter(**kwargs):
    return kwargs.get('user_type') == 'Admin' and not batch_filter(**kwargs)

def student_filter(**kwargs):
    return kwargs.get('user_type') == 'Student' and not batch_filter(**kwargs)

# list of worker queues. Values of each are a string indicating the queue name,
# and a function used to select whether or not to use this type of queue 
# (see autotest_enqueuer._get_queue)
batch_queue = {'name': 'batch', 'filter': batch_filter}
single_queue = {'name': 'single', 'filter': single_filter}
student_queue = {'name': 'student', 'filter': student_filter}
WORKER_QUEUES = [batch_queue, single_queue, student_queue]

### WORKER CONFIGS ###

WORKERS = [(4, [student_queue['name'], single_queue['name'], batch_queue['name']]),
           (2, [single_queue['name'], student_queue['name'], batch_queue['name']]),
           (2, [batch_queue['name'], student_queue['name'], single_queue['name']])]
