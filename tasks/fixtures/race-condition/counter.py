"""A threaded counter with a race condition."""
import time
import threading
from typing import Optional


class ThreadSafeCounter:
    """A counter intended to be thread-safe, but has a race condition.
    
    WARNING: This class is NOT actually thread-safe due to a race condition
    in the increment operation.
    """

    def __init__(self, initial: int = 0):
        """Initialize the counter.
        
        Args:
            initial: Initial counter value
        """
        self._value = initial

    def increment(self) -> None:
        """Increment the counter by 1.
        
        RACE CONDITION: This operation is not atomic!
        Between reading the value and writing it back, another thread
        may read and modify it, causing lost updates.
        """
        # Read current value
        current = self._value
        
        # Simulate some work (makes race condition more likely)
        time.sleep(0.00001)
        
        # Write updated value
        self._value = current + 1

    def decrement(self) -> None:
        """Decrement the counter by 1.
        
        RACE CONDITION: Same as increment.
        """
        current = self._value
        time.sleep(0.00001)
        self._value = current - 1

    def value(self) -> int:
        """Get the current counter value.
        
        Returns:
            Current value
        """
        return self._value

    def reset(self) -> None:
        """Reset the counter to 0."""
        self._value = 0


def stress_test(num_threads: int = 10, operations_per_thread: int = 100) -> Optional[int]:
    """Stress test the counter with multiple threads.
    
    Args:
        num_threads: Number of threads to spawn
        operations_per_thread: Operations per thread
        
    Returns:
        The error in the final count (should be 0 if thread-safe)
    """
    counter = ThreadSafeCounter(0)
    
    def worker() -> None:
        """Worker thread that increments counter."""
        for _ in range(operations_per_thread):
            counter.increment()
    
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=worker)
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    expected = num_threads * operations_per_thread
    actual = counter.value()
    error = expected - actual
    
    return error


def test_basic_increment() -> None:
    """Test basic increment operation."""
    counter = ThreadSafeCounter(0)
    counter.increment()
    assert counter.value() == 1


def test_single_thread() -> None:
    """Test in single thread (should pass even with race condition)."""
    counter = ThreadSafeCounter(0)
    for _ in range(100):
        counter.increment()
    assert counter.value() == 100


if __name__ == "__main__":
    test_basic_increment()
    test_single_thread()
    
    # Stress test - will likely show race condition
    error = stress_test(num_threads=10, operations_per_thread=100)
    if error != 0:
        print(f"Race condition detected: missing {error} increments!")
    else:
        print("All tests passed!")
