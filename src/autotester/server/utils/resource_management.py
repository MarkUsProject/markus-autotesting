import resource
from autotester.config import config

RLIMIT_ADJUSTMENTS = {'nproc': 10}

def rlimit_str2int(rlimit_string):
    return getattr(resource, f'RLIMIT_{rlimit_string.upper()}')

def set_rlimits_before_test():
    """
    Sets rlimit settings specified in config file
    This function ensures that for specific limits (defined in RLIMIT_ADJUSTMENTS),
    there are at least n=RLIMIT_ADJUSTMENTS[limit] resources available for cleanup
    processes that are not available for test processes.  This ensures that cleanup
    processes will always be able to run. 
    """
    for limit_str in config['rlimit_settings'].keys() | RLIMIT_ADJUSTMENTS.keys():
        limit = rlimit_str2int(limit_str)

        values = config['rlimit_settings'].get(limit_str, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        curr_soft, curr_hard = resource.getrlimit(limit)
        soft, hard = (min(vals) for vals in zip((curr_soft, curr_hard), values))
        # reduce the hard limit so that cleanup scripts will have at least 
        # adj more resources to use. 
        adj = RLIMIT_ADJUSTMENTS.get(limit_str, 0)
        if (curr_hard - hard) < adj:
            hard = curr_hard - adj
        # make sure the soft limit doesn't exceed the hard limit
        hard = max(hard, 0)
        soft = max(min(hard, soft), 0)
        
        resource.setrlimit(limit, (soft, hard))

def set_rlimits_before_cleanup():
    """
    Sets the rlimit settings specified in RLIMIT_ADJUSTMENTS
    so that both the soft and hard limits are set as high as possible. This ensures
    that cleanup processes will have as many resources as possible to run. 
    """
    for limit_str in RLIMIT_ADJUSTMENTS:
        limit = rlimit_str2int(limit_str)
        soft, hard = resource.getrlimit(limit)
        soft = max(soft, hard)
        resource.setrlimit(limit, (soft, hard))
