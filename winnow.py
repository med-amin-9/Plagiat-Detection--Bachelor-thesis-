class RingBuffer(object):
    """
    Implements a simple ring buffer to access
    characters from and write items to (circular queue) for use in sliding window operations.
    """
    def __init__(self, k):
        """
        Create a new buffer holding k elements
        :param k: Number of elements in the ring buffer
        """
        self.index  = -1
        self.data = [None] * k
        self.offset = 0
        self._length = 0          #underscore means this is a private Python does not force privacy. It's just a strong suggestion to other programmers: it's internal dont mess with it

    @property
    def full(self) -> bool:
        return len(self.data) == self._length

    @property
    def length(self) -> int:
        return self._length

    def __len__(self):    #DUnder methods or magic methods These are special functions that Python automatically calls for you when you use built-in operations so you can do: if len(buffer) instead of if buffer.length or by print.  
        return self._length

    def __getitem__(self, index):
        if index >= self._length:
            raise IndexError("Index out of bounds")

        index = (self.offset + index) % len(self.data)
        return self.data[index]

    def peek(self):
        """
        Return the element at the front of the buffer
        :return: item at the front of the buffer
        """
        if self._length == 0:
            raise IndexError("No data in the buffer")

        return self.data[self.index]

    def push(self, item):
        """
        Insert an item into the buffer
        :param item: Item to insert
        :return: None
        """
        if self.full:
            raise ValueError("RingBuffer is full")

        self.index = (self.index + 1) % len(self.data)
        self.data[self.index] = item
        self._length = self._length + 1

    def push_many(self, iterable) -> int:
        """
        Insert multiple items into the buffer from the given iterable
        :param iterable: Elements to read
        :return: Number of items inserted
        """
        count = 0
        space = len(self.data) - self._length
        i = iter(iterable)
        try:
            for _ in range(space):
                self.push(next(i))
                count += 1
        except StopIteration:
            pass

        return count

    def pop(self):
        """
        Remove and return the item at the begin of the buffer
        :return: Current item at the end of the buffer
        """
        if self._length == 0:
            raise ValueError("RingBuffer is empty")

        value = self.data[self.offset]
        self.offset = (self.offset + 1) % len(self.data)
        self._length = self._length - 1
        return value
    

def get_kgrams(text: str, k: int) -> list[str]:
    """
    Generate a list of k-grams from the input text.
    """
    pass


def rolling_hash(kgrams: list[str], base: int = 256, prime: int = 101) -> list[int]:
    """
    Compute rolling hashes for each k-gram using a simple polynomial hash.
    """
    pass


def select_fingerprints(hashes: list[int], window_size: int) -> set[int]:
    """
    Perform Winnowing by selecting the minimum hash in each sliding window.
    """
    pass


def robust_winnowing(text: str, k: int, window_size: int) -> set[int]:
    """
    Perform the full robust winnowing pipeline:
    normalize -> k-grams -> rolling hash -> fingerprint selection.
    """
    pass