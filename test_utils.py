import unittest
from utils import parse_dependency_line

class TestUtils(unittest.TestCase):

    def test_parse_dependency_line(self):
        line = "+--- org.springframework.boot:spring-boot-starter-web:2.5.4 -> 3.0.0"
        node, level = parse_dependency_line(line)
        self.assertEqual(level, 5)
        self.assertEqual(node['module'], "org.springframework.boot:spring-boot-starter-web")
        self.assertEqual(node['version'], "3.0.0")
        self.assertEqual(node['full'], "org.springframework.boot:spring-boot-starter-web:2.5.4 -> 3.0.0")

if __name__ == '__main__':
    unittest.main()
