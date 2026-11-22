"""Dependency classifications only: no model imports, sockets or credentials."""
import unittest
from recovery import classify_error
from langgraph.errors import GraphInterrupt
from psycopg import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

class Categories(unittest.TestCase):
    def test_six_categories_and_dependency_types(self):
        class RateLimited(Exception): status_code=429
        class AuthenticationFailed(Exception): status_code=401
        for error, expected in [(RateLimited(),'transient_error'),(AuthenticationFailed(),'permanent_error'),
                (TimeoutError(),'timeout_error'),(OperationalError(),'dependency_unavailable'),
                (ValueError(),'validation_error'),(GraphInterrupt(()),'workflow_interrupt'),
                (RedisConnectionError(),'dependency_unavailable'),(RedisTimeoutError(),'timeout_error')]:
            with self.subTest(expected=expected,error=type(error).__name__):
                self.assertEqual(classify_error(error),expected)

if __name__=='__main__': unittest.main(verbosity=2)
