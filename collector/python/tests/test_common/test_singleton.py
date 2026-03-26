import threading
import unittest

from witty_profiler.common.singleton import Singleton, ThreadSafeSingleton


class MockNonThreadSafeSingleton(Singleton):
    """Non-thread-safe singleton class for testing."""

    def __init__(self, value="default"):
        self.value = value


class MockThreadSafeSingleton(ThreadSafeSingleton):
    """Thread-safe singleton class for testing."""

    def __init__(self, value="default"):
        self.value = value


class TestSingleton(unittest.TestCase):
    """Test suite for the singleton decorator implementation."""

    def setUp(self):
        """Reset singleton instances before each test."""
        MockNonThreadSafeSingleton.clear_singleton()
        MockThreadSafeSingleton.clear_singleton()

    def test_non_thread_safe_singleton_returns_same_instance(self):
        """Test that non-thread-safe singleton returns the same instance."""
        instance1 = MockNonThreadSafeSingleton("test1")
        instance2 = MockNonThreadSafeSingleton("test2")

        self.assertIs(instance1, instance2)

    def test_non_thread_safe_singleton_preserves_first_initialization(self):
        """Test that non-thread-safe singleton preserves first initialization value."""
        instance1 = MockNonThreadSafeSingleton("test1")
        instance2 = MockNonThreadSafeSingleton("test2")

        self.assertEqual(instance1.value, "test1")
        self.assertEqual(instance2.value, "test1")

    def test_thread_safe_singleton_returns_same_instance(self):
        """Test that thread-safe singleton returns the same instance."""
        instance1 = MockThreadSafeSingleton("test1")
        instance2 = MockThreadSafeSingleton("test2")

        self.assertIs(instance1, instance2)

    def test_thread_safe_singleton_preserves_first_initialization(self):
        """Test that thread-safe singleton preserves first initialization value."""
        instance1 = MockThreadSafeSingleton("test1")
        instance2 = MockThreadSafeSingleton("test2")

        self.assertEqual(instance1.value, "test1")
        self.assertEqual(instance2.value, "test1")

    def test_class_method_get_instance_returns_same_instance(self):
        """Test that get_instance() class method returns the same instance."""
        instance1 = MockNonThreadSafeSingleton.get_instance("value1")
        instance2 = MockNonThreadSafeSingleton.get_instance("value2")

        self.assertIs(instance1, instance2)

    def test_class_method_get_instance_preserves_first_initialization(self):
        """Test that get_instance() preserves first initialization value."""
        instance1 = MockNonThreadSafeSingleton.get_instance("value1")
        instance2 = MockNonThreadSafeSingleton.get_instance("value2")

        self.assertEqual(instance1.value, "value1")
        self.assertEqual(instance2.value, "value1")

    def test_thread_safe_singleton_with_concurrent_access(self):
        """Test that thread-safe singleton handles concurrent instantiation correctly."""
        instances = set()
        errors = []

        def create_instance():
            """Helper to create instance in separate thread."""
            try:
                instance = MockThreadSafeSingleton.get_instance("thread_test")
                instances.add(id(instance))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_instance) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(instances), 1, "All threads should get the same instance")

    def test_different_decorated_classes_have_different_instances(self):
        """Test that different decorated classes maintain separate instances."""

        class FirstClass(Singleton):
            pass

        class SecondClass(Singleton):
            pass

        first_instance = FirstClass()
        second_instance = SecondClass()

        self.assertIsNot(first_instance, second_instance)

    def test_singleton_with_no_arguments_returns_same_instance(self):
        """Test that @singleton() with empty parentheses works correctly."""

        class EmptyParensClass(Singleton):
            def __init__(self, value="default"):
                self.value = value

        instance1 = EmptyParensClass("first")
        instance2 = EmptyParensClass("second")

        self.assertIs(instance1, instance2)
        self.assertEqual(instance1.value, "first")

    def test_singleton_inheritance_with_different_instance(self):
        class P1(Singleton):
            def __init__(self, value="P1"):
                self.value = value

        class C1(P1):
            def __init__(self, value="C1"):
                super().__init__(value)
                self.value = value

        class C2(P1):
            def __init__(self, value="C2"):
                super().__init__(value)
                self.value = value

        p1_instance = P1("parent")
        c1_instance = C1("child1")
        c2_instance = C2("child2")
        self.assertIsNot(p1_instance, c1_instance)
        self.assertIsNot(p1_instance, c2_instance)
        self.assertIsNot(c1_instance, c2_instance)


if __name__ == "__main__":
    unittest.main()
