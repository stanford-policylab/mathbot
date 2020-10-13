import pandas as pd
import numpy as np
import statsmodels.formula.api as sm
import random
import itertools


class UniformRandom:
    def __init__(self, action_set):
        self._action_set = action_set

    def get_action(self):
        return [a for a in self._action_set if random.randint(0, 1)]


class ThompsonSampling:
    def __init__(self, context, action_set):
        self._context = context
        self._action_set = action_set
        self._formula = self._get_formula()
        self._model = None

    def _ols(self, df):
        """
        Run OLS using formula over dataframe df
        """
        #print(df)
        #print(df['pre_q'])
        self._model = sm.ols(formula=self._formula, data=df).fit()
        return self._model

    def _get_formula(self):
        """
        Get OLS formula for n_x features, n_action actions and discrete feature ids
        """
        Xs = self._context
        interactions = ['{}:{}'.format(x, a) for x in Xs for a in self._action_set]
        #print(list(Xs.keys()))
        #print(interactions)
        return 'reward ~ ' + '+'.join(list(Xs.keys()) + interactions)

    def _sample_beta(self, df):
        """
        Sample one beta according to its mean and covariance
        """
        self._ols(df)
        beta_name = self._model.cov_params().columns
        beta_mean = self._model.params
        print(beta_mean)
        beta_cov = self._model.cov_params()
        sampled_beta = np.random.multivariate_normal(beta_mean, beta_cov)
        #print('sampled beta is ')
        #print(sampled_beta)
        return {k: v for k, v in zip(beta_name, sampled_beta)}

    def _get_rewards(self, beta, sample_context):
        """
        Calculate the reward of sample_context given the beta for the OLS model
        """
        temp = self._model.params
        for k in self._model.params.index:
            self._model.params[k] = beta[k]
        rewards = self._model.predict(sample_context)
        self._model.params = temp
        return rewards

    def get_action(self, df, sample_context):
        """
        Brute-force search of all possible actions
        """
        X = sample_context
        beta = self._sample_beta(df)
        choices = list(itertools.product([0, 1], repeat=len(self._action_set)))
        rewards = {}
        for choice in choices:
            #print('analyzing choice {}'.format(choice))
            for i, a in enumerate(self._action_set):
                X[a] = choice[i]
            #print('covariate is')
            #print(X)
            rewards[choice] = float(self._get_rewards(beta, X))
            #print('pred reward is {}'.format(rewards[choice]))
        best_choice = max(rewards, key=rewards.get)
        best_action = [a for i, a in enumerate(self._action_set) if best_choice[i]]
        #print('best action is {}'.format(best_action))
        return best_action
