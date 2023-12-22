class Node:
    def __init__(self, data):
        self.data = data
        self.next = None
        self.prev = None


class LinkedList:
    def __init__(self):
        self.head: Node = None

    def insertAtBegin(self, data):
        new_node = Node(data)
        if self.head is None:  # it's the first node being inserted
            self.head = new_node
        else:
            current_first_node = self.head
            new_node.next = current_first_node
            current_first_node.prev = new_node
            self.head = new_node

    def insertAfterIndex(self, data, index):
        new_node = Node(data)
        current_node = self.head
        position = 0
        if position == index:
            self.insertAtBegin(data)
        else:
            while current_node is not None and (position + 1) != index:
                position = position + 1
                current_node = current_node.next

            if current_node is not None:
                new_node.prev = current_node
                new_node.next = current_node.next
            else:
                print("Index not present")

    def insertBefore(self, node: Node, data):
        if node is None:  # it will be inserted as the first node
            self.insertAtBegin(data)
        else:
            new_node = Node(data)
            node_before = node.prev
            new_node.next = node
            new_node.prev = node_before
            node.prev = new_node
            if node_before is None:  # It will be the first node
                self.head = new_node
            else:
                node_before.next = new_node

    def insertAfter(self, node: Node, data):
        if node is None:  # it will be inserted as the first node
            self.insertAtBegin(data)
        else:
            new_node = Node(data)
            new_node.prev = node
            new_node.next = node.next
            if node.next is not None:
                node.next.prev = new_node

    def insertAtEnd(self, data):
        new_node = Node(data)
        if self.head is None:
            self.head = new_node
            return

        current_node = self.head
        while current_node.next:
            current_node = current_node.next

        current_node.next = new_node
        new_node.prev = current_node

    # Update node of a linked list
    # at given position
    def updateNode(self, val, index):
        current_node = self.head
        position = 0
        if position == index:
            current_node.data = val
        else:
            while current_node is not None and position != index:
                position = position + 1
                current_node = current_node.next

            if current_node is not None:
                current_node.data = val
            else:
                print("Index not present")

    def removeFirstNode(self):
        if self.head is None:
            return

        self.head = self.head.next

    def removeLastNode(self):
        if self.head is None:
            return

        current_node = self.head
        while current_node.next.next:
            current_node = current_node.next

        current_node.next = None

    # Method to remove at given index
    def removeAtIndex(self, index):
        if self.head is None:
            return

        current_node = self.head
        position = 0
        if position == index:
            self.removeFirstNode()
        else:
            while current_node is not None and (position + 1) != index:
                position = position + 1
                current_node = current_node.next

            if current_node is not None:
                prev_node = current_node.prev
                next_node = current_node.next
                if prev_node is not None:
                    prev_node.next = next_node
                if next_node is not None:
                    next_node.prev = prev_node
            else:
                print("Index not present")

    def removeNode(self, data):
        current_node = self.head

        while current_node is not None and current_node.next.data != data:
            current_node = current_node.next

        if current_node is None:
            return
        else:
            prev_node = current_node.prev
            next_node = current_node.next
            if prev_node is not None:
                prev_node.next = next_node
            if next_node is not None:
                next_node.prev = prev_node

    def sizeOfLL(self):
        size = 0
        if self.head:
            current_node = self.head
            while current_node:
                size = size + 1
                current_node = current_node.next
            return size
        else:
            return 0

