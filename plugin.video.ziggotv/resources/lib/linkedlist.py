class Node:
    def __init__(self, data):
        self.data = data
        self.next = None
        self.prev = None


class LinkedList:
    def __init__(self):
        self.head: Node = None

    def insert_at_begin(self, data):
        newNode = Node(data)
        if self.head is None:  # it's the first node being inserted
            self.head = newNode
        else:
            currentFirstNode = self.head
            newNode.next = currentFirstNode
            currentFirstNode.prev = newNode
            self.head = newNode

    def insert_after_index(self, data, index):
        newNode = Node(data)
        currentNode = self.head
        position = 0
        if position == index:
            self.insert_at_begin(data)
        else:
            while currentNode is not None and (position + 1) != index:
                position = position + 1
                currentNode = currentNode.next

            if currentNode is not None:
                newNode.prev = currentNode
                newNode.next = currentNode.next
            else:
                print("Index not present")

    def insert_before(self, node: Node, data):
        if node is None:  # it will be inserted as the first node
            self.insert_at_begin(data)
        else:
            newNode = Node(data)
            nodeBefore = node.prev
            newNode.next = node
            newNode.prev = nodeBefore
            node.prev = newNode
            if nodeBefore is None:  # It will be the first node
                self.head = newNode
            else:
                nodeBefore.next = newNode

    def insert_after(self, node: Node, data):
        if node is None:  # it will be inserted as the first node
            self.insert_at_begin(data)
        else:
            newNode = Node(data)
            newNode.prev = node
            newNode.next = node.next
            if node.next is not None:
                node.next.prev = newNode

    def insert_at_end(self, data):
        newNode = Node(data)
        if self.head is None:
            self.head = newNode
            return

        currentNode = self.head
        while currentNode.next:
            currentNode = currentNode.next

        currentNode.next = newNode
        newNode.prev = currentNode

    # Update node of a linked list
    # at given position
    def update_node(self, val, index):
        currentNode = self.head
        position = 0
        if position == index:
            currentNode.data = val
        else:
            while currentNode is not None and position != index:
                position = position + 1
                currentNode = currentNode.next

            if currentNode is not None:
                currentNode.data = val
            else:
                print("Index not present")

    def remove_first_node(self):
        if self.head is None:
            return

        self.head = self.head.next

    def remove_last_node(self):
        if self.head is None:
            return

        currentNode = self.head
        while currentNode.next.next:
            currentNode = currentNode.next

        currentNode.next = None

    # Method to remove at given index
    def remove_at_index(self, index):
        if self.head is None:
            return

        currentNode = self.head
        position = 0
        if position == index:
            self.remove_first_node()
        else:
            while currentNode is not None and (position + 1) != index:
                position = position + 1
                currentNode = currentNode.next

            if currentNode is not None:
                prevNode = currentNode.prev
                nextNode = currentNode.next
                if prevNode is not None:
                    prevNode.next = nextNode
                if nextNode is not None:
                    nextNode.prev = prevNode
            else:
                print("Index not present")

    def remove_node(self, data):
        currentNode = self.head

        while currentNode is not None and currentNode.next.data != data:
            currentNode = currentNode.next

        if currentNode is None:
            return
        prevNode = currentNode.prev
        nextNode = currentNode.next
        if prevNode is not None:
            prevNode.next = nextNode
        if nextNode is not None:
            nextNode.prev = prevNode

    def size_of_ll(self):
        size = 0
        if self.head:
            currentNode = self.head
            while currentNode:
                size = size + 1
                currentNode = currentNode.next
            return size
        return 0
