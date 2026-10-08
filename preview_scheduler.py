"""One native worker, cooperative frame boundaries, interactive work first."""
import heapq
import itertools
import threading
from concurrent.futures import Future


class PreviewScheduler:
    def __init__(self, cleanup=lambda: None):
        self.condition = threading.Condition()
        self.queue = []
        self.sequence = itertools.count()
        self.closed = False
        self.cleanup = cleanup
        self.thread = None

    def submit(self, priority, factory, *args):
        future = Future()
        with self.condition:
            if self.closed:
                raise RuntimeError('Preview worker is closed.')
            heapq.heappush(self.queue, (priority, next(self.sequence), future, factory, args, None))
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, name='fotufilm-preview', daemon=True)
                self.thread.start()
            self.condition.notify()
        return future

    def _run(self):
        try:
            while True:
                with self.condition:
                    while not self.queue and not self.closed:
                        self.condition.wait()
                    if self.closed:
                        pending, self.queue = self.queue, []
                        for _, _, future, _, _, iterator in pending:
                            if iterator is not None:
                                iterator.close()
                                future.set_exception(InterruptedError('Preview worker closed.'))
                            else:
                                future.cancel()
                        return
                    priority, sequence, future, factory, args, iterator = heapq.heappop(self.queue)
                if iterator is None:
                    if not future.set_running_or_notify_cancel():
                        continue
                try:
                    if iterator is None:
                        iterator = iter(factory(*args))
                    next(iterator)
                except StopIteration as done:
                    future.set_result(done.value)
                except BaseException as error:
                    if iterator is not None:
                        iterator.close()
                    future.set_exception(error)
                else:
                    with self.condition:
                        # Keep original FIFO position; only more urgent work preempts a clip.
                        heapq.heappush(self.queue, (priority, sequence, future, factory, args, iterator))
        finally:
            self.cleanup()

    def shutdown(self, wait=True):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        if wait and self.thread is not None:
            self.thread.join()
