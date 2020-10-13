# -*- coding: utf-8 -*-

import datetime
import io
import json
import logging
import os
import sys
import uuid
import random
from logging.handlers import RotatingFileHandler
from . import db
from . import survey
from .config import TestConfig, BaseConfig
from flask import Flask, session, request, render_template, current_app
from werkzeug.datastructures import ImmutableMultiDict
from .bandit import ThompsonSampling, UniformRandom
from collections import defaultdict
import string
import pandas as pd
if sys.version_info.major > 2:
    import urllib.parse as urlparse
else:
    import urlparse

'''
Initialization
'''


def create_app(_config=BaseConfig):
    """
    ===========LOAD CONFIG============
    """
    app = Flask(__name__)
    app.config.from_object(_config)

    """ 
    ===========INITIALIZATION============
    """
    # Check logging and saving dirs
    for path in [app.config['CONV_SAVE_DIR'],
                 app.config['HEATMAP_SAVE_DIR']]:
        os.makedirs(path, exist_ok=True)

    # Additional handler for debugging
    if app.config['DEBUG']:
        app.config.update(PROPAGATE_EXCEPTIONS=True)
        handler = RotatingFileHandler(app.config['APP_LOG_PATH'], maxBytes=10000, backupCount=1)
        #handler.setLevel(logging.DEBUG)
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)

    """ 
    ===========APP ROUTING============
    """

    @app.route('/')
    def redirect_index():
        app.logger.warning(session)
        # set up random session ID on enter homepage if not exists and create conversation history each time
        if 'id' not in session:
            # if there is no session created, create a new user session
            add_new_user_to_session()
        else:
            # if there is a existing user id in session, recreate a log file for each visit
            create_new_log_file()
        return app.send_static_file('index.html')

    @app.route('/mathbot')
    def redirect_mathbot():
        # set up random session ID on enter homepage if not exists and create conversation history each time
        if 'id' not in session:
            # if there is no session created, create a new user session
            add_new_user_to_session()
        else:
            # if there is a existing user id in session, recreate a log file for each visit
            create_new_log_file()
        return app.send_static_file('mathbot.html')

    @app.route('/video')
    def redirect_video():
        # set up random session ID on enter homepage if not exists and create conversation history each time
        if 'id' not in session:
            # if there is no session created, create a new user session
            add_new_user_to_session()
        else:
            # if there is a existing user id in session, recreate a log file for each visit
            create_new_video_log_file()

        return app.send_static_file('video.html')

    @app.route('/ineligible')
    def ineligible_page():
        if 'id' not in session:
            # if there is no session created, create a new user session
            return "You may have landed on the wrong page."

        return render_template('landing.html', error_msg="Thank you for participating! Unfortunately, you are "
                                                         "ineligible for the experiment. If you completed the 2nd eligibility quiz, you will receive your "
                                                         "$0.25 compensation within the next week.")

    @app.route('/finished')
    def user_id_page():
        if 'id' not in session:
            # if there is no session created, create a new user session
            return "You may have landed on the wrong page."

        return render_template('finished.html')

    @app.route('/survey', methods=["GET", "POST"])
    def redirect_survey():
        # if the request is from mturk
        args = None
        referrer = None

        # Redirect
        if request.referrer:
            parsed = urlparse.urlparse(request.referrer)
            args_qs = urlparse.parse_qs(parsed.query)
            temp = []
            for k, vs in args_qs.items():
                temp += [(k, v) for v in vs]
            referrer = ImmutableMultiDict(temp)

        # GET/POST

        if len(request.values):
            args = request.values

        try:
            workerId = args.get('workerId')
            assignmentId = args.get('assignmentId')
            hitId = args.get('hitId')
            turkSubmitTo = args.get('turkSubmitTo')
        except:
            workerId = None
            assignmentId = None
        if workerId is None:
            return render_template('landing.html')
        elif (workerId in current_app.config['BLACKLIST']) or (workerId not in current_app.config['WHITELIST'] and \
                                                               db.get_db().experimentTable.query_if_contains_user(
                                                                   user_id=workerId)):
            return render_template('landing.html', error_msg="You've previously participated in this HIT.")
        else:
            agent = request.headers.get('User-Agent')
            browser = str(request.user_agent.browser).lower()
            if any(phone in agent.lower() for phone in ["iphone", "android", "blackberry"]):
                return render_template('landing.html', error_msg="Please use a desktop for this HIT.")
            elif browser == 'msie' or browser == 'safari':
                return render_template('landing.html',
                                       error_msg="Please do not use Internet Explorer or Safari for this HIT.")
            else:
                # @Jerry TODO: should change to:
                # add_new_user_to_session(args, referrer)
                add_new_user_to_session(workerId)
                user = {
                    'session_id': session['id'],
                    'assignment_id': assignmentId,
                    'external_submit_url': app.config['EXTERNAL_SUBMIT_URL'],
                    'turkSubmitTo': turkSubmitTo
                }
            print("!" * 32)

            s = survey.get_survey()
            return s.render(user=user)

    @app.route('/api/<api_name>', methods=['GET', 'POST'])
    def handle_api(api_name):
        if request.method == 'POST':
            if api_name == 'record':
                return record_conversation()
            elif api_name == 'log_progress':
                table = db.get_db().experimentTable
                table.record_progress(request)
                json.dumps({'success': True}), 200, {'ContentType': 'application/json'}
            elif api_name == 'dump_form':
                return "".join(["{} = {}\n".format(k, v) for k, v in request.form.items()])
            elif api_name == 'heatmap':
                table = db.get_db().experimentTable
                return table.save_heatmap()
            elif api_name == 'record_context' or api_name == 'record_reward':
                # print('calling record api')
                # if for some reason there is no existing session, recreate a user session
                #print(session)
                if 'id' not in session:
                    print("no existing user session!")
                    add_new_user_to_session()
                new_row = dict(request.form)
                new_row['unique_user_id'] = session['id']
                if 'context' in api_name:
                    table = db.get_db().contextTable
                else:
                    table = db.get_db().rewardTable
                table.insert(new_row)
                return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}
            elif api_name == 'get_action':
                print('calling the get_action function')
                # check if the action database is empty.
                # if it is, generate synthetic data and insert it
                # actually, this  should really never happen, so commenting out so it breaks if the table is empty
                # generate_initial_action_table()

                context_table = db.get_db().contextTable.fetch().to_json()
                reward_table = db.get_db().rewardTable.fetch().to_json()
                action_table = db.get_db().actionTable.fetch().to_json()
                # get action doesn't need the real unique_user_id
                action_set = ["isomorph", "skip_concept"]
                """
                # The current policy is uniform random
                actions = UniformRandom(action_set).get_action()
                """
                #create the (context, action, reward) table
                context_table = json.loads(context_table)
                action_table = json.loads(action_table)
                reward_table = json.loads(reward_table)
                tables = [context_table, action_table, reward_table]
                new_dicts = [defaultdict(list),defaultdict(list),defaultdict(list)]
                for i, t in enumerate(tables):
                    for key in t.keys():
                        for index_key in t[key]:
                            val = t[key][index_key]
                            try:
                                val = val.replace('\"', '').replace('\'', '').replace('[', '').replace(']', '')
                                new_val = float(val)
                            except:
                                new_val = val
                            new_dicts[i][key].append(new_val)
                context = pd.DataFrame.from_dict(new_dicts[0]).drop(['id'], axis=1)
                #Filter context to only rows where pre_quiz is not nan                
                context = context[context['pre_q'].notnull()]
                #make sure pre quiz is numeric
                context["pre_q"] = pd.to_numeric(context["pre_q"])
                #Filter context to only rows where policy == 'bandit'
                context = context[context['which_policy'] == "bandit"]
                action = pd.DataFrame.from_dict(new_dicts[1]).drop(['id'], axis=1)
                #print('action table is')
                #print(action)
                reward = pd.DataFrame.from_dict(new_dicts[2]).drop(['id'], axis=1)
                #print('reward table is')
                #print(reward)
                #Paste them together
                df = pd.merge(reward, context, how='inner', left_on=['unique_user_id', 'test_question'], right_on=['unique_user_id', 'next_test_question'])
                df = pd.merge(df, action, how='inner', on=['unique_user_id', 'test_question'])
                df = df.drop(['unique_user_id'], axis=1)    
                #print('df is')
                #print(df)
                # Check on the current policy
                sample_context = {}
                for k in request.form.keys():
                    try:
                        val = float(request.form[k])
                    except:
                        val = request.form[k]
                    sample_context[k] = val
                # Currently, the only contextual variables should be next_test_question, pre_q
                which_policy = sample_context['which_policy']
                print('called policy is {} '.format(which_policy))
                keys = list(sample_context.keys())
                for k in keys:
                    if k != 'pre_q' and k != 'next_test_question':
                        sample_context.pop(k, None)
                print('sample context is {}'.format(sample_context))
                
                if which_policy == 'uniform' or sample_context['next_test_question'] == 'END': #if next_test_question is "END", don't send them to thompson sampling
                    print('using uniform ')
                    actions = UniformRandom(action_set).get_action()
                else:
                    ts = ThompsonSampling(sample_context, action_set)
                    actions = ts.get_action(df, sample_context)
                print('actions are')
                print(actions)
                action_dict = {k: 1 if k in actions else 0 for k in action_set}
                # Who is this person?
                #print(session)
                if 'id' not in session:
                    print("no existing user session!")
                    add_new_user_to_session()
                action_dict['unique_user_id'] = session['id']
                action_dict['test_question'] = request.form['next_test_question']
                table = db.get_db().actionTable
                table.insert(action_dict)
                return json.dumps({'success': True, 'action_dict': action_dict}), 200, {
                    'ContentType': 'application/json'}
        elif request.method == 'GET':
            if api_name == 'assign_group':
                table = db.get_db().experimentTable
                return table.assign_group()
        return "ok"

    @app.route('/<path:path>', methods=['GET'])
    def redirect_static_file(path):
        return app.send_static_file(path)

    """
    ===========DB INITIALIZATION============
    """
    db.init_app(app)

    with app.app_context():
        current_app.logger.info("Current App name: {}".format(current_app.name))
    return app


def generate_initial_action_table():
    action_table = db.get_db().actionTable
    # for i in range(10):
    #    print()
    # print('action table is ')
    at_json = json.loads(action_table.fetch().to_json())
    # print(at_json)
    num_rows = len(at_json[list(at_json.keys())[0]])
    # print('num rows is {}'.format(num_rows))

    if num_rows < 5:
        print('generating synthetic data')
        return  # we don't need to generate synthetic data for uniform random
        synthetic = generate_synthetic_data()

        s_actions = synthetic['actions']
        for sa in s_actions:
            action_table.insert(sa)
            action_table = db.get_db().actionTable
            # print('new action table')
            # print(action_table.fetch().to_json())

        context_table = db.get_db().contextTable
        s_contexts = synthetic['contexts']
        for sc in s_contexts:
            context_table.insert(sc)
            context_table = db.get_db().contextTable
            # print('new context table')
            # print(context_table.fetch().to_json())

        reward_table = db.get_db().rewardTable
        s_rewards = synthetic['rewards']
        for sr in s_rewards:
            reward_table.insert(sr)
            reward_table = db.get_db().rewardTable
            # print('new reward table')
            # print(reward_table.fetch().to_json())


def generate_random_user_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))


def generate_synthetic_data():
    test_questions = ['1-1', '1-2', '2-1', '2-2', '2-3', '4-1', '4-2', '4-2b', '4-3', '4-4', '4-5']
    contexts = []
    rewards = []
    actions = []

    for i in range(10):  # for each person
        total_time = 10000
        unique_user_id = generate_random_user_id()
        for tq in test_questions:
            data_point = {}
            reward = {}
            action = {}
            skipped_last_question = random.randint(0, 1)
            isomorphed_last_question = random.randint(0, 1)
            num_attempts_last_question = random.randint(0, 3)
            last_test_question_time = random.random() * 10000
            total_time += last_test_question_time
            # (skipped_last_question, isomorphed_last_question, tq, unique_user_id) should go into action
            action['skip_concept'] = skipped_last_question
            action['isomorph'] = isomorphed_last_question
            action['test_question'] = tq
            action['unique_user_id'] = unique_user_id
            actions.append(action)

            # (correctness * 100000 - last_test_question_time, tq, unique_user_id) should go into reward
            reward['test_question'] = tq
            reward['unique_user_id'] = unique_user_id
            correct = random.randint(0, 1)
            reward_num = 100000 * correct - last_test_question_time
            reward['reward'] = reward_num
            rewards.append(reward)

            try:
                next_test_question = test_questions[test_questions.index(tq) + 1]
            except:
                continue
            """
            print('next_test_question: {}'.format(next_test_question))
            print('skipped_last_question: {}'.format(skipped_last_question))
            print('isomorphed_last_question: {}'.format(isomorphed_last_question))   
            print('num_attempts_last_question: {}'.format(isomorphed_last_question))   
            print('last_test_question_time: {}'.format(last_test_question_time))
            print('time_since_starting_lesson: {}'.format(total_time))
            print('unique_user_id: {}'.format(unique_user_id))
            """
            data_point['time_since_starting_lesson'] = total_time
            data_point['next_test_question'] = next_test_question
            data_point['skipped_last_question'] = skipped_last_question
            data_point['isomorphed_last_question'] = isomorphed_last_question
            data_point['num_attempts_last_question'] = num_attempts_last_question
            data_point['last_test_question_time'] = last_test_question_time
            data_point['unique_user_id'] = unique_user_id
            contexts.append(data_point)

    return_dict = {}
    return_dict['contexts'] = contexts
    return_dict['actions'] = actions
    return_dict['rewards'] = rewards
    return return_dict


def create_new_log_file():
    # even for the same user ID, recreate a new conversation log for each time hit the homepage
    saved_file_name = "[{}]{}.log".format(str(datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S')),
                                          str(session['id']))
    session['saved_conv_path'] = os.path.join(current_app.config['CONV_SAVE_DIR'], saved_file_name)
    current_app.logger.info("Saving path: {}".format(session['saved_conv_path']))


def create_new_video_log_file():
    # even for the same user ID, recreate a new conversation log for each time hit the homepage
    saved_file_name = "[{}]{}.log".format(str(datetime.datetime.now().strftime('%Y-%m-%d')),
                                          str(session['id']))
    session['saved_heatmap_path'] = os.path.join(current_app.config['HEATMAP_SAVE_DIR'], saved_file_name)
    current_app.logger.info("Saving path: {}".format(session['saved_heatmap_path']))


def add_new_user_to_session(userId=None, create_log=create_new_log_file):
    # print('adding new user')
    if userId is None:
        session['id'] = str(uuid.uuid4())
    else:
        session['id'] = userId

    current_app.logger.info("New session with id = [{}] starts".format(session['id']))
    create_log()


def save_heatmap():
    app.logger.warning("POST request received for heatmap")

    # if for some reason there is no existing session, recreate a user session
    if 'id' not in session:
        print("no existing user session!")
        add_new_user_to_session(create_log=create_new_video_log_file)

    # record heatmap
    saved_conv_path = session['saved_heatmap_path']
    with io.open(saved_conv_path, "a+", encoding='utf8') as conv_file:
        videoId, conv_to_write = request.form['videoId'], request.form["heatmap"]
        conv_file.write('%s\t%s\n' % (videoId, json.dumps(conv_to_write)))
    current_app.logger.warning("Log file saved {}: ".format(saved_conv_path))
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


def record_conversation():
    current_app.logger.warning("POST request received")

    # if for some reason there is no existing session, recreate a user session
    if 'id' not in session:
        print("no existing user session!")
        add_new_user_to_session()

    # record conversation
    saved_conv_path = session['saved_conv_path']
    with io.open(saved_conv_path, "a+", encoding='utf8') as conv_file:
        conv_to_write = request.form["loggedConversation"]
        conv_to_write = conv_to_write.encode('utf-8', 'ignore')
        conv_to_write = conv_to_write.decode('utf-8', 'ignore')
        conv_file.write(conv_to_write)
    current_app.logger.warning("Log file saved {}: ".format(saved_conv_path))
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


"""
if __name__ == '__main__':
    app = create_app()
    app.run(debug=False, use_reloader=False)
"""
