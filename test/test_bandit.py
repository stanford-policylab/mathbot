import unittest
from www.bandit import UniformRandom, ThompsonSampling
import pandas as pd
import numpy as np
import tempfile
import shutil
import os


class TestUniformRandom(unittest.TestCase):
    def setUp(self):
        self.action_set = ["A", "B", "C"]
        self.policy = UniformRandom(self.action_set)

    def testGetAction(self):
        action = self.policy.get_action()
        self.assertTrue(set(action) <= set(self.action_set))


class TestThompsonSampling(unittest.TestCase):
    def setUp(self):
        self.context_continuous = ["CONTINUOUS1", "CONTINUOUS2", "CONTINUOUS3"]
        self.context_discrete = ['DISCRETE1', 'DISCRETE2', 'DISCRETE3']
        self.context = self.context_discrete + self.context_continuous
        self.discrete_context = ["n", "a", "i", "v", "e"]
        self.action_set = ["A", "B", "C"]
        self.policy = ThompsonSampling(self.context, self.action_set)

    def testGetAction(self):
        self.context_table = self.sampleContext(200)
        self.sample_context = self.sampleContext(1)
        action = self.policy.get_action(df=self.context_table,
                                        sample_context=self.sample_context)
        self.assertTrue(set(action) <= set(self.action_set))

    def sampleContext(self, N):
        """
        Generate N random context samples with n_x features, n_action actions and discrete feature ids
        """
        data = {}
        data['y'] = np.random.rand(N)
        for c in self.context_discrete:
            data[c] = np.random.choice(self.discrete_context, size=(N,))
        for c in self.context_continuous:
            data[c] = np.random.rand(N)
        for a in self.action_set:
            data[a] = np.random.randint(0, 2, size=N)
        return pd.DataFrame.from_dict(data)
