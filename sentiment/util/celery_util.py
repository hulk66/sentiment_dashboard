import functools
import inspect
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Final, List

from celery import Task
from dateutil import parser
from redis import Redis

from functools import wraps
from typing import Callable, Type
import logging
from typing import Tuple
from datetime import datetime, timezone

from .redis_interface import make_redis_interface

PRIORITY_SEP: str = "\x06\x16"
DEFAULT_PRIORITY_STEPS: List[int] = [0, 3, 6, 9]


# -----
# This is shamelessly stolen and slightly adjusted from https://github.com/freelawproject/courtlistener
# many thanks!!
#
logger = logging.getLogger(__name__)

def parse_rate(rate: str) -> Tuple[int, int]:
    """

    Given the request rate string, return a two tuple of:
    <allowed number of requests>, <period of time in seconds>

    (Stolen from Django Rest Framework.)
    """
    num, period = rate.split("/")
    num_requests = int(num)
    if len(period) > 1:
        # It takes the form of a 5d, or 10s, or whatever
        duration_multiplier = int(period[0:-1])
        duration_unit = period[-1]
    else:
        duration_multiplier = 1
        duration_unit = period[-1]
    duration_base = {"s": 1, "m": 60, "h": 3600, "d": 86400}[duration_unit]
    duration = duration_base * duration_multiplier
    return num_requests, duration


def retry(
    ExceptionToCheck: Type[Exception],
    tries: int = 4,
    delay: float = 3,
    backoff: float = 2,
) -> Callable:
    """Retry calling the decorated function using an exponential backoff.
    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry
    :param ExceptionToCheck: the exception to check. may be a tuple of
    exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
    each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """

    def deco_retry(f: Callable) -> Callable:
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    logger.warning(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry

def clear_queue(queue_name: str):
    """Empty out a queue, nuking the tasks in it."""
    priority_names = [
        make_queue_name_for_pri(queue_name, pri)
        for pri in DEFAULT_PRIORITY_STEPS
    ]
    r = make_redis_interface("CELERY")
    return sum([r.delete(x) for x in priority_names])


def make_queue_name_for_pri(queue: str, pri: int) -> str:
    """Make a queue name for redis

    Celery uses PRIORITY_SEP to separate different priorities of tasks into
    different queues in Redis. Each queue-priority combination becomes a key in
    redis with names like:

     - batch1\x06\x163 <-- P3 queue named batch1

    There's more information about this in Github, but it doesn't look like it
    will change any time soon:

      - https://github.com/celery/kombu/issues/422

    In that ticket the code below, from the Flower project, is referenced:

      - https://github.com/mher/flower/blob/master/flower/utils/broker.py#L135

    :param queue: The name of the queue to make a name for.
    :param pri: The priority to make a name with.
    :return: A name for the queue-priority pair.
    """
    if pri not in DEFAULT_PRIORITY_STEPS:
        raise ValueError("Priority not in priority steps")
    return "{0}{1}{2}".format(
        *((queue, PRIORITY_SEP, pri) if pri else (queue, "", ""))
    )


def get_queue_length(queue_name: str = "celery") -> int:
    """Get the number of tasks in a celery queue.

    :param queue_name: The name of the queue you want to inspect.
    :return: the number of items in the queue.
    """
    priority_names = [
        make_queue_name_for_pri(queue_name, pri)
        for pri in DEFAULT_PRIORITY_STEPS
    ]
    r = make_redis_interface("CELERY")
    return sum([r.llen(x) for x in priority_names])


class CeleryThrottle(object):
    """A class for throttling celery."""

    def __init__(
        self,
        poll_interval: float = 3.0,
        min_items: int = 50,
        queue_name: str = "celery",
    ) -> None:
        """Create a throttle to prevent celery runaways.

        :param poll_interval: How long to wait between polling the queue
        length in seconds, when you know it's greater than the min length.
        :param min_items: Generally keep the queue longer than this, and
        always shorter than 2× this value.
        """
        # All these variables are Final, i.e., they're consts. The only
        # instance variable that changes is the shortage variable below.
        self.min: Final = min_items
        self.max: Final = min_items * 2
        self.poll_interval: Final = poll_interval
        self.queue_name: Final = queue_name

        # `shortage` stores the number of items that the queue is short by, as
        # compared to `self.max`. At init, the queue is empty, so it's short by
        # the full amount. Fill it up.
        self.shortage = self.max

    def maybe_wait(self) -> None:
        """Make the user wait until the queue is short enough"""
        self.shortage -= 1
        if self.shortage > 0:
            # No need to sleep. Add items to the queue.
            return

        # No shortage we know of. Measure the queue to see if it's below
        # self.min. If so, we have a shortage that we should rectify.
        while True:
            queue_length = get_queue_length(self.queue_name)
            if queue_length > self.min:
                # The queue is still pretty full. Let it process a bit.
                time.sleep(self.poll_interval)
            else:
                # Refill the queue. As Michelle Obama says, when it goes low,
                # we go high.
                self.shortage = self.max - queue_length
                break


def throttle_task(rate: str, key: Any = None) -> Callable:
    """A decorator for throttling tasks to a given rate.

    :param rate: The maximum rate that you want your task to run. Takes the
    form of '1/m', or '10/2h' or similar.
    :param key: An argument name whose value should be used as part of the
    throttle key in redis. This allows you to create per-argument throttles by
    simply passing the name of the argument you wish to key on.
    :return: The decorated function
    """

    def decorator_func(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Inspect the decorated function's parameters to get the task
            # itself and the value of the parameter referenced by key.
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            task = bound_args.arguments["self"]
            key_value = None
            if key:
                try:
                    key_value = bound_args.arguments[key]
                except KeyError:
                    raise KeyError(
                        f"Unknown parameter '{key}' in throttle_task "
                        f"decorator of function {task.name}. "
                        f"`key` parameter must match a parameter "
                        f"name from function signature: '{sig}'"
                    )
            delay = get_task_wait(task, rate, key=key_value)
            if delay > 0:
                # Decrement the number of times the task has retried. If you
                # fail to do this, it gets auto-incremented, and you'll expend
                # retries during the backoff.
                task.request.retries = task.request.retries - 1
                logger.info(
                    "Throttling task %s (%s) via decorator for %ss",
                    task.name,
                    task.request.id,
                    delay,
                )
                return task.retry(countdown=delay)
            else:
                # All set. Run the task.
                return func(*args, **kwargs)

        return wrapper

    return decorator_func


def set_for_next_window(
    r: Redis,
    throttle_key: str,
    schedule_key: str,
    n: datetime,
) -> float:
    """Set the schedule for the next window to start as soon as the current one
    runs out.
    """
    ttl = r.ttl(throttle_key)

    logger.debug("Throttle key %s, Schedule key %s, TTL %i", throttle_key, schedule_key, ttl)
    if ttl < 0:
        # Race condition. The key expired (-2) or doesn't have a
        # TTL (-1). Don't delay; run the task.
        return 0
    r.set(schedule_key, str(n + timedelta(seconds=ttl)))
    return ttl


@retry(ConnectionError, tries=4, delay=0.25, backoff=1.5)
def get_task_wait(
    task: Task,
    rate: str = "1/s",
    key: str = None,
) -> float:
    """Keep a global throttle for tasks

    Can be used via the `throttle_task` decorator above.

    This implements the timestamp-based algorithm detailed here:

        https://www.figma.com/blog/an-alternative-approach-to-rate-limiting/

    Basically, you keep track of the number of requests and use the key
    expiration as a reset of the counter.

    So you have a rate of 5/m, and your first task comes in. You create a key:

        celery_throttle:task_name = 1
        celery_throttle:task_name.expires = 60

    Another task comes in a few seconds later:

        celery_throttle:task_name = 2
        Do not update the ttl, it now has 58s remaining

    And so forth, until:

        celery_throttle:task_name = 6
        (10s remaining)

    We're over the threshold. Re-queue the task for later. 10s later:

        Key expires b/c no more ttl.

    Another task comes in:

        celery_throttle:task_name = 1
        celery_throttle:task_name.expires = 60

    And so forth.

    ---

    There is also a scheduler that figures out when to re-queue tasks. The idea
    of the scheduler is simple: If you know the rate the tasks can be
    processed, and if you're getting tasks faster than that rate, you can
    schedule each one to take its turn at a reasonable specified time. This is
    implemented by keeping a timestamp in redis indicating when the throttle
    will no longer be clogged up.

    Say you have a rate of 1/5s, and you get tasks as follows:

         Elapsed Time | Task Number
         -------------+------------
              1s      |     1
              2s      |     2
              3s      |     3

    Task number 1 runs immediately, but sets a throttle for five seconds until
    more work can be done. The second comes in and sees that the throttle has a
    ttl of three remaining seconds, so it waits that long. Next, task number 3
    comes in. It sees that the current window is full, and that the next one is
    too — only one task every five seconds, right? It has to wait seven
    seconds: two seconds (for the current window) *plus* 5 seconds (for the
    next one, which is occupied by task two).

    And so forth.

    :param task: The task that is being checked
    :param rate: How many times the task can be run during the time period.
    Something like, 1/s, 2/h or similar.
    :param key: If given, add this to the key placed in Redis for the item.
    Typically, this will correspond to the value of an argument passed to the
    throttled task.
    :return: If throttled returns a float of how many seconds the task should
    wait until the next open window for processing. If not throttled, returns
    zero (i.e., don't wait).
    """
    task_sub_key = f"{task.name}{':' + str(key) if key else ''}"
    throttle_key = f"celery_throttle:{task_sub_key}"
    logger.debug("Throttle key %s", throttle_key)
    r = make_redis_interface("CACHE")

    allowed_task_count, duration = parse_rate(rate)

    # Check the count in redis
    actual_task_count = r.get(throttle_key)
    if actual_task_count is None:
        # No key. Set the value to 1 and set the ttl of the key.
        expiry = timedelta(seconds=duration / allowed_task_count)
        logger.debug("Setting 1 for %s with expiry %i", throttle_key, expiry.total_seconds())
        r.set(throttle_key, 1, ex=expiry)
        return 0

    # Key found. Check if we should throttle.
    if int(actual_task_count) < allowed_task_count:
        # We're OK to run the task. Increment our counter, and say things are
        # OK by returning 0.
        new_count = r.incr(throttle_key, 1)
        logger.debug("Incrementing %s, new_count is %i", throttle_key, new_count)

        if new_count == 1:
            # Safety check. If the count is 1 after incrementing, that means we
            # created the key via the incr command. This can happen when it
            # expires between when we `get` its value up above and when we
            # increment it here. If that happens, it lacks a ttl! Set one.
            #
            # N.B. There's no need to worry about a race condition between our
            # incr above, and the `expire` line here b/c without a ttl on this
            # key, it can't expire between these two commands.
            r.expire(throttle_key, duration)
        return 0

    # Over the threshold. Find the next window and schedule the task.
    schedule_key = f"celery_throttle:schedule:{task_sub_key}"
    logger.debug("Schedule key %s", schedule_key)
    # n = now() # was django now function
    n = datetime.now()
    delay = r.get(schedule_key)
    logger.debug("Delay from Redis %s", delay)
    if delay is None:
        # No schedule yet. Run the task when the current throttle expires.
        return set_for_next_window(r, throttle_key, schedule_key, n)

    # We have a delay, so use it if it's in the future
    delay = parser.parse(delay)
    if delay < n:
        # Delay is in the past. Run the task when the current throttle expires.
        return set_for_next_window(r, throttle_key, schedule_key, n)

    # Delay is in the future; use it and supplement it
    new_time = delay + timedelta(seconds=duration / allowed_task_count)
    logger.debug("Delay is in the future. Old time %s, new time %s", delay.strftime("%H:%M:%S"), new_time.strftime("%H:%M:%S")) 
    logger.debug(delay)
    logger.debug(new_time)
    r.set(schedule_key, str(new_time))

    delay_seconds = (new_time - n).total_seconds()       
    logger.debug("Resulting Delay Seconds %i", delay_seconds)
    return delay_seconds