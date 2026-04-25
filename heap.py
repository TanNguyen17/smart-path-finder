"""
heap.py — Custom MinHeap with O(log V) decrease-key support.

Standard Python does not provide a priority queue with decrease-key.
Without it, Dijkstra must insert duplicate entries and degrades toward
O(V^2) in dense graphs.  This implementation maintains a position lookup
table so that decrease_key, push, and pop all run in O(log V).

Time complexity:
    push          O(log V)
    pop           O(log V)
    decrease_key  O(log V)

Space complexity:  O(V)
"""


class MinHeap:
    """
    A binary min-heap keyed by numeric priority.

    Each element is a (key, value) pair where *key* is the priority
    (distance or time) and *value* is the node identifier.  A dictionary
    ``self.position`` maps each value to its current index in the
    underlying array, enabling O(log V) decrease-key.
    """

    def __init__(self):
        # Each entry: (key, value) where key = priority, value = node id
        self.data = []
        # Mapping: value -> index in self.data (enables O(1) lookup for decrease_key)
        self.position = {}

    def push(self, key, value):
        """Insert a new element or decrease its key if already present.  O(log V)."""
        if value in self.position:
            if key < self.data[self.position[value]][0]:
                self.decrease_key(value, key)
            return

        self.data.append((key, value))
        index = len(self.data) - 1
        self.position[value] = index
        self._heapify_up(index)

    def pop(self):
        """Remove and return the (key, value) pair with smallest key.  O(log V)."""
        if not self.data:
            raise IndexError("Pop from empty MinHeap")
        root = self.data[0]
        last = self.data.pop()
        del self.position[root[1]]

        if self.data:
            self.data[0] = last
            self.position[last[1]] = 0
            self._heapify_down(0)

        return root

    def decrease_key(self, value, new_key):
        """Decrease the key of an existing element and restore heap order.  O(log V)."""
        if value not in self.position:
            raise KeyError(f"Value {value} not found in heap")

        i = self.position[value]
        old_key, _ = self.data[i]

        if new_key >= old_key:
            return

        self.data[i] = (new_key, value)
        self._heapify_up(i)

    # ---- internal helpers ----

    def _heapify_up(self, index):
        while index > 0:
            parent = self._parent(index)
            if self.data[index][0] < self.data[parent][0]:
                self._swap(index, parent)
                index = parent
            else:
                break

    def _heapify_down(self, index):
        n = len(self.data)
        while True:
            left = self._left(index)
            right = self._right(index)
            smallest = index

            if left < n and self.data[left][0] < self.data[smallest][0]:
                smallest = left
            if right < n and self.data[right][0] < self.data[smallest][0]:
                smallest = right
            if smallest == index:
                break
            self._swap(index, smallest)
            index = smallest

    def _swap(self, i, j):
        self.data[i], self.data[j] = self.data[j], self.data[i]
        _, vi = self.data[i]
        _, vj = self.data[j]
        self.position[vi] = i
        self.position[vj] = j

    def _parent(self, index):
        return (index - 1) // 2

    def _left(self, index):
        return 2 * index + 1

    def _right(self, index):
        return 2 * index + 2

    def __len__(self):
        return len(self.data)

    def __bool__(self):
        return len(self.data) > 0


if __name__ == "__main__":
    h = MinHeap()
    h.push(10, "A")
    h.push(5, "B")
    h.push(15, "C")
    h.push(3, "D")
    h.push(8, "E")

    print(h.pop())  # (3, "D")
    print(h.pop())  # (5, "B")
    print(h.pop())  # (8, "E")
    print(h.pop())  # (10, "A")
    print(h.pop())  # (15, "C")