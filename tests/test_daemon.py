import unittest
import time
from pipeline.daemon import tick

class TestDaemon(unittest.TestCase):
    def test_daemon_tick_rules(self):
        now = time.time()
        
        # 1. Less than 4 hours -> None
        self.assertIsNone(tick(now - 3600*2, 9, False, False))
        
        # 2. Morning Greeting (8-10 AM)
        self.assertEqual(tick(now - 3600*5, 9, False, False), 'morning')
        
        # 3. Reminder (11 AM - 6 PM) priority
        self.assertEqual(tick(now - 3600*5, 14, True, True), 'reminder')
        
        # 4. Hobby (12-4 PM)
        self.assertEqual(tick(now - 3600*5, 15, True, False), 'hobby')
        
        # 5. Silence (5-8 PM)
        self.assertEqual(tick(now - 3600*5, 18, False, False), 'silence')
        
        # 6. Late night -> None
        self.assertIsNone(tick(now - 3600*5, 22, True, True))

if __name__ == '__main__':
    unittest.main()
