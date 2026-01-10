import unittest
from app.utils import parse_dependency_line

class TestUtils(unittest.TestCase):

    def test_parse_dependency_line(self):
        line = "+--- org.springframework.boot:spring-boot-starter-web:2.5.4 -> 3.0.0"
        node, level = parse_dependency_line(line)
        self.assertEqual(level, 1)
        self.assertEqual(node['module'], "org.springframework.boot:spring-boot-starter-web")
        self.assertEqual(node['version'], "3.0.0")
        self.assertEqual(node['full'], "org.springframework.boot:spring-boot-starter-web:2.5.4 -> 3.0.0")

    def test_parse_dependency_line_indented(self):
        line = "|    +--- org.springframework:spring-beans:5.3.9 -> 6.0.0 (c)"
        node, level = parse_dependency_line(line)
        self.assertEqual(level, 2)
        self.assertEqual(node['module'], "org.springframework:spring-beans")
        self.assertEqual(node['version'], "6.0.0")
        self.assertEqual(node['resolution'], "c")
        self.assertEqual(node['full'], "org.springframework:spring-beans:5.3.9 -> 6.0.0 (c)")

    def test_parse_dependency_line_with_star(self):
        line = "|    \--- org.springframework:spring-core:5.3.9 -> 6.0.0 (*)"
        node, level = parse_dependency_line(line)
        self.assertEqual(level, 2)
        self.assertEqual(node['module'], "org.springframework:spring-core")
        self.assertEqual(node['version'], "6.0.0")
        self.assertEqual(node['resolution'], "*")
        self.assertEqual(node['full'], "org.springframework:spring-core:5.3.9 -> 6.0.0 (*)")

if __name__ == '__main__':
    unittest.main()
