"""
linked list module
"""
import dataclasses


@dataclasses.dataclass
class Node:
    """
    Node class.
    """

    def __init__(self, data):
        self.data = data
        self.next = None
        self.prev = None


class LinkedList:
    """
    Linked list implementation using the Node class
    """
    def __init__(self):
        self.head: Node = None

    def insert_at_begin(self, data):
        """
        Insert a node at the beginning of the list
        @param data:
        @return: nothing
        """
        newNode = Node(data)
        if self.head is None:  # it's the first node being inserted
            self.head = newNode
        else:
            currentFirstNode = self.head
            newNode.next = currentFirstNode
            currentFirstNode.prev = newNode
            self.head = newNode

    def insert_after_index(self, data, index):
        """
        Insert a node with data after a specific number of nodes
        @param data:
        @param index:
        @return:
        """
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
        """
        Insert a new node with data after the node
        @param node: node after which the new node must be inserted
        @param data: data to store in the new node
        @return:
        """
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
        """
        Insert a new node with data before the node
        @param node: node before which the new node must be inserted
        @param data: data to store in the new node
        @return:
        """
        if node is None:  # it will be inserted as the first node
            self.insert_at_begin(data)
        else:
            newNode = Node(data)
            newNode.prev = node
            newNode.next = node.next
            if node.next is not None:
                node.next.prev = newNode

    def insert_at_end(self, data):
        """
        insert a new node with data at the end of the list
        @param data:
        @return:
        """
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
        """
        Update a node at a specific position with the new val
        @param val:
        @param index:
        @return:
        """
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
        """
        remove the first node from the list
        @return:
        """
        if self.head is None:
            return

        self.head = self.head.next

    def remove_last_node(self):
        """
        remove the last node from the list
        @return:
        """
        if self.head is None:
            return

        currentNode = self.head
        while currentNode.next.next:
            currentNode = currentNode.next

        currentNode.next = None

    # Method to remove at given index
    def remove_at_index(self, index):
        """
        remove a node at the given position
        @param index: position to remove
        @return:
        """
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
        """
        remove node which contain the same data
        @param data: data to search for
        @return:
        """
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
        """
        returns the size of the linked list
        @return:
        """
        size = 0
        if self.head:
            currentNode = self.head
            while currentNode:
                size = size + 1
                currentNode = currentNode.next
            return size
        return 0
