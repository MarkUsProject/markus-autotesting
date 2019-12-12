import autotest_server as ats

with ats.rq.Connection(ats.redis_connection()):
    for job in ats.rq.get_failed_queue().jobs:
        print(job.exc_info)