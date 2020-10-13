import unittest
from www.config.config import TestConfig
from www import create_app
from www import db


class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = create_app(_config=TestConfig)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ID = "ID"
        self.MESSAGE_WRONG = "You may have landed on the wrong page."
        self.MESSAGE_INELIGIBLE = "Thank you for participating!"
        self.MESSAGE_HOMEPAGE = "<title>MathBot - Ada</title>"
        self.MESSAGE_FINISHED = "Thank you for completing the study!"
        self.MESSAGE_VIDEO = "https://www.youtube.com/iframe_api"
        self.MESSAGE_MATHBOT = "<title>MathBot - Ada</title>"

    def tearDown(self):
        pass

    def testIneligibleWrong(self):
        rv = self.client.get("/ineligible")
        self.assertIn(self.MESSAGE_WRONG, str(rv.data))

    def testIneligibleCorrect(self):
        with self.client.session_transaction() as sess:
            sess['id'] = self.ID
        rv = self.client.get("/ineligible")
        self.assertIn(self.MESSAGE_INELIGIBLE, str(rv.data))

    def testFinishedWrong(self):
        rv = self.client.get("/finished")
        self.assertIn(self.MESSAGE_WRONG, str(rv.data))

    def testFinishedCorrect(self):
        with self.client.session_transaction() as sess:
            sess['id'] = self.ID
        rv = self.client.get("/finished")
        self.assertIn(self.MESSAGE_FINISHED, str(rv.data))

    def testHomepage(self):
        with self.client.session_transaction() as sess:
            self.assertNotIn('id', sess)

        rv = self.client.get("/")
        self.assertIn(self.MESSAGE_HOMEPAGE, str(rv.data))

        with self.client.session_transaction() as sess:
            self.assertIn('id', sess)

    def testVideo(self):
        with self.client.session_transaction() as sess:
            self.assertNotIn('id', sess)

        rv = self.client.get("/video")
        self.assertIn(self.MESSAGE_VIDEO, str(rv.data))

        with self.client.session_transaction() as sess:
            self.assertIn('id', sess)

    def testMathbot(self):
        with self.client.session_transaction() as sess:
            self.assertNotIn('id', sess)

        rv = self.client.get("/mathbot")
        self.assertIn(self.MESSAGE_MATHBOT, str(rv.data))

        with self.client.session_transaction() as sess:
            self.assertIn('id', sess)

    def testRecordContext(self):
        data = {TestConfig.CONTEXT_SCHEMA[0]: 'A',
                TestConfig.CONTEXT_SCHEMA[1]: 'B'}
        rv = self.client.post("/api/record_context",
                              data=data)
        with self.app.app_context():
            df = db.get_db().contextTable.fetch()
            # Due to the version of sqlite, sometimes the cell is a list
            col1 = df[TestConfig.CONTEXT_SCHEMA[0]][0]
            col2 = df[TestConfig.CONTEXT_SCHEMA[1]][0]
            id = df['id'][0]

            self.assertIn('A', col1)
            self.assertIn('B', col2)
            self.assertEqual(id, 1)


if __name__ == '__main__':
    unittest.main()
