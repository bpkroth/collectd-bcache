# collectd-bcache.py
# vim: set ft=python et smarttab tw=100:
# 2016-04-07
# bpkroth
#
# Adapted from https://github.com/pommi/collectd-bcache and rewritten as a
# libpython style plugin.
# NOTE: I intentionally left as much of the original source code as is.  In
# particular, I did not object-orient-ify any of the code.

import collectd

import os

SYSFS_BCACHE_PATH = '/sys/fs/bcache/'

PLUGIN_NAME = 'bcache'

verbose_logging = False

def file_to_lines(fname):
    try:
        with open(fname, "r") as fd:
            return fd.readlines()
    except:
        return []


def file_to_line(fname):
    ret = file_to_lines(fname)
    if ret:
        return ret[0].strip()
    return ''


def interpret_bytes(x):
    '''Interpret a pretty-printed disk size.'''
    factors = {
        'k': 1 << 10,
        'M': 1 << 20,
        'G': 1 << 30,
        'T': 1 << 40,
        'P': 1 << 50,
        'E': 1 << 60,
        'Z': 1 << 70,
        'Y': 1 << 80,
    }

    factor = 1
    if x[-1] in factors:
        factor = factors[x[-1]]
        x = x[:-1]
    return int(float(x) * factor)


def bcache_uuids():
    uuids = []

    if not os.path.isdir(SYSFS_BCACHE_PATH):
        print('# bcache is not loaded.')
        return uuids

    for cache in os.listdir(SYSFS_BCACHE_PATH):
        if not os.path.isdir('%s%s' % (SYSFS_BCACHE_PATH, cache)):
            continue
        uuids.append(cache)

    return uuids


def get_dirty_data(uuid):
    dirty_data = 0
    for obj in os.listdir(os.path.join(SYSFS_BCACHE_PATH, uuid)):
        if obj.startswith('bdev'):
            val = interpret_bytes(file_to_line('%s/%s/%s/dirty_data' %
                                               (SYSFS_BCACHE_PATH, uuid, obj)))
            dirty_data = dirty_data + int(val)
    return dirty_data


def get_cache_ratio(uuid, time):
    for obj in os.listdir(os.path.join(SYSFS_BCACHE_PATH, uuid)):
        if obj.startswith('bdev'):
            hits = float(file_to_line('%s/%s/%s/stats_%s/cache_hits' %
                                    (SYSFS_BCACHE_PATH, uuid, obj, time)))
            misses = float(file_to_line('%s/%s/%s/stats_%s/cache_misses' %
                                      (SYSFS_BCACHE_PATH, uuid, obj, time)))
            if (hits + misses) == 0:
                return 100
            return hits / (hits + misses) * 100
    return 0


def get_cache_result(uuid, stat):
    value = 0
    for obj in os.listdir(os.path.join(SYSFS_BCACHE_PATH, uuid)):
        if obj.startswith('bdev'):
            value = int(file_to_line('%s/%s/%s/stats_five_minute/cache_%s' %
                                    (SYSFS_BCACHE_PATH, uuid, obj, stat)))
    return value


def get_bypassed(uuid):
    value = 0
    for obj in os.listdir(os.path.join(SYSFS_BCACHE_PATH, uuid)):
        if obj.startswith('bdev'):
            value = interpret_bytes(file_to_line('%s/%s/%s/stats_five_minute/bypassed' %
                                               (SYSFS_BCACHE_PATH, uuid, obj)))
    return value


def map_uuid_to_bcache(uuid):
    devices = []
    for obj in os.listdir(os.path.join(SYSFS_BCACHE_PATH, uuid)):
        if obj.startswith('bdev'):
           devices.append(os.path.basename(os.readlink(os.path.join(SYSFS_BCACHE_PATH, uuid, obj, 'dev'))))
    return devices


def log_verbose(msg):
    if not verbose_logging:
        return
    collectd.info('%s plugin [verbose]: %s' % PLUGIN_NAME, msg)


def dispatch_value(plugin_instance, value_type, type_instance, value):
    log_verbose('Sending value: %s.%s.%s=%s' % (plugin_instance, value_type, type_instance, value))
    # Get a collectd Values object.
    val = collectd.Values()
    # Fill it with the right data.
    val.plugin = PLUGIN_NAME
    val.plugin_instance = plugin_instance
    val.type = value_type
    val.type_instance = type_instance
    val.values = [value, ]
    # Leave these blank to let the server assign the host from the conf file and now() as the time.
    #val.host = None
    #val.time = None
    # Dispatch it to the server.
    val.dispatch()


def read_callback():
    uuids = bcache_uuids()
    for uuid in uuids:
        dirty_data = get_dirty_data(uuid)
        devices = map_uuid_to_bcache(uuid)
        for device in devices:
            # Here's the original unixsock/exec plugin style format:
            #
            #print('PUTVAL "%s/bcache-%s/df_complex-dirty_data" interval=%s N:%s' %
            #        (hostname, device, interval, dirty_data))
            #
            # It produces an RRD file on disk (if you're using that write plugin) like this:
            #
            # $hostname/bcache-bcache0/df_complex-dirty_data.rrd
            #
            # Where "bcache" in the "/bcache-bcache0/" portion of the path is the plugin_type,
            # "bcache0" is the plugin_instance, and "df_complex" is the data type of the plugin
            # value named "dirty_data"
            #
            # In our method, that's translated into the following, where the dispatch_value
            # handles assembling those parts into a collectd Values object for sending to the
            # server process.
            dispatch_value(device, 'df_complex', 'dirty_data', dirty_data)

            # TODO: Also track cache_available_percent in the cache device.

            for t in ['five_minute', 'hour', 'day', 'total']:
                cache_ratio = get_cache_ratio(uuid, t)
                dispatch_value(device, 'cache_ratio', t, cache_ratio)

            for c in ['bypass_hits', 'bypass_misses', 'hits', 'miss_collisions', 'misses', 'readaheads']:
                cache_result = get_cache_result(uuid, c)
                dispatch_value(device, 'requests', c, cache_result)

            bypassed = get_bypassed(uuid)
            dispatch_value(device, 'bytes', 'bypassed', bypassed)


def configure_callback(conf):
    for node in conf.children:
        if node.key == 'Verbose':
            verbose_logging = bool(node.values[0])
        else:
            collectd.warning('%s plugin: Unknown config key: %s.' % PLUGIN_NAME)


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(read_callback)
