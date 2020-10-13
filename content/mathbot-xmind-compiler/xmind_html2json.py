import json
from pathlib import Path

import os
import re
from bs4 import BeautifulSoup
from shutil import copyfile, rmtree


def get_branch_regex(content):
    conditions = content.split(' and ')
    regex = []
    no_regex = []
    if_else = False

    # loose condition matching
    if content.lower() == 'else':
        return {}
    else:
        for condition in conditions:
            c = condition.lower()
            if '==' in c:
                if 'type' in c and 'int' in c:
                    # type(response) == int
                    regex.append('^[0-9]+$')
                else:
                    # response == "123"
                    regex.append('^' + c.split('==')[-1].strip().strip('"') + '$')
            elif '!=' in c:
                if 'type' in c and 'int' in c:
                    # type(response) != int
                    no_regex.append('^[0-9]+$')
                else:
                    # response != "123"
                    no_regex.append('^' + c.split('!=')[-1].strip().strip('"') + '$')
            elif 'in' in c:
                # "hello" in response
                regex.append(c.split('in')[0].strip().strip('"'))
            elif 'yes' == c:
                # "all affirmative words" in response
                regex.append('y|sure|ok|okay|of course')
            elif 'no' == c:
                # "all affirmative words" in response
                regex.append('no|nah')
            elif 'idk' == c:
                # "all affirmative words" in response
                regex.append("don't know|not know|don't understand|not understand|idk|hint")
            elif c.lower() == 'else':
                if_else = True

    evals = []
    for r in regex:
        evals.append("Boolean(response.match(\"%s\"))" % r)
    for nr in no_regex:
        evals.append("!Boolean(response.match(\"%s\"))" % nr)
    return {
        'evals': evals
    }


def split_long_sentence(content):
    return re.split(r'(?<=[^A-Z].[.?]) +(?=[A-Z])', content.strip())


def html2question_bank(html_folder, json_dump_folder, html_raw, question_name):
    soup = BeautifulSoup(html_raw, 'html.parser')

    sub_q_count = 0
    for e in soup.body.find_all(True, {"class": re.compile("^(root|topic|topicImage)$")}):
        # init stuff if it's a root node
        if e['class'][0] == 'root':
            question_bank = {
                question_name: {
                    'is_root': True,
                    'says': split_long_sentence(e.a.contents[0]),
                    'branch': [

                    ]
                }
            }
            q_stack = [question_name]
            indent_stack = [-1]
            pending_branch = None
        elif e['class'][0] == 'topicImage':
            # move all images to one folder and add the img tag to "says"
            output_img_folder = os.path.join(json_dump_folder, 'img/')

            img_base_source_name = os.path.basename(e.img['src'])
            img_base_source_name = img_base_source_name.replace(" ", "_");
            old_path = os.path.join(html_folder, e.img['src'])
            new_path = os.path.join(output_img_folder, img_base_source_name)
            img_web_link_relative_path = os.path.join('resources/json/img', img_base_source_name)
            if not os.path.exists(new_path):
                copyfile(old_path, new_path)
            question_bank[q_stack[len(q_stack) - 1]]['says'].append(
                '<span><img src=%s></span>' % (img_web_link_relative_path))
        elif e['class'][0] == 'topic':
            content = e.a.contents[0]
            curr_indent = len(content) - len(content.lstrip())
            content = content.strip()

            # if the parent node is a condition
            if pending_branch is None:
                # if the parent node is not a branch, popping the stack until we find the appropriate parent level,
                # which has to be a conversation node
                while indent_stack[len(indent_stack) - 1] != (curr_indent - 1):
                    q_stack.pop()
                    indent_stack.pop()

                if bool(re.match('^\$.*\$$', content)):
                    # if a branch node follows the conversation node, create a pending node awaiting for next node
                    pending_branch = get_branch_regex(content.strip('$'))
                elif bool(re.match('^<.*>$', content)):
                    # if a redirection node follows the conversation node
                    if bool(re.match('^<<.*>>$', content)):
                        # if a redirectino with return node
                        skip_to_id = content[2:-2]
                        question_bank[q_stack[len(q_stack) - 1]]['next_type'] = "review"
                    else:
                        skip_to_id = content[1:-1]
                        question_bank[q_stack[len(q_stack) - 1]]['next_type'] = "new"
                    question_bank[q_stack[len(q_stack) - 1]]['skip'] = skip_to_id
                else:
                    # if a (random) conversation node follows a conversation node, create a new sub-question and skip directly
                    #  to it
                    sub_q_count += 1
                    sub_q_name = "%s-%d" % (question_name, sub_q_count)

                    # check if this is a random conversation node or regular conversation graph
                    if bool(re.match('^&.*&$', content)):
                        new_sub_q = {
                            'random': content.strip('&'),
                            'branch': []
                        }
                    else:
                        new_sub_q = {
                            'says': split_long_sentence(content),
                            'branch': []
                        }

                    # add the new question in the question bank
                    question_bank[sub_q_name] = new_sub_q

                    # add skip label to the current parent conversation node
                    question_bank[q_stack[len(q_stack) - 1]]['skip'] = sub_q_name

                    # update indentation and question stack
                    q_stack.append(sub_q_name)
                    indent_stack.append(curr_indent)

            else:
                if bool(re.match('^<.*>$', content)):
                    # if a redirection node follows a branch node if the sub prompt is in the form of <conv_id>,
                    # instead of creating a pending branch, link it to a existing question
                    if bool(re.match('^<<.*>>$', content)):
                        # if a redirectino with return node
                        skip_to_id = content[2:-2]
                        pending_branch['next_type'] = "review"
                    else:
                        skip_to_id = content[1:-1]
                        pending_branch['next_type'] = "new"
                    pending_branch['next'] = skip_to_id
                    question_bank[q_stack[len(q_stack) - 1]]['branch'].append(pending_branch)
                    pending_branch = None
                else:
                    # if a (random) conversation node follows a branch node
                    sub_q_count += 1
                    sub_q_name = "%s-%d" % (question_name, sub_q_count)

                    # check if this is a random conversation node or regular conversation graph
                    if bool(re.match('^&.*&$', content)):
                        new_sub_q = {
                            'random': [
                                content.strip('&')
                            ],
                            'branch': []
                        }
                    else:
                        new_sub_q = {
                            'says': split_long_sentence(content),
                            'branch': []
                        }

                    # add current sub question to the pending current branch
                    pending_branch['next'] = sub_q_name
                    question_bank[q_stack[len(q_stack) - 1]]['branch'].append(pending_branch)
                    pending_branch = None

                    # add the new question in the question bank
                    question_bank[sub_q_name] = new_sub_q

                    # update indentation and question stack
                    q_stack.append(sub_q_name)
                    indent_stack.append(curr_indent)

    return question_bank


def main():
    xmind_html_folder = "../../xmind_files/intro-sequence-module/"
    json_dump_folder = "../../www/static/resources/json/"
    output_img_folder = os.path.join(json_dump_folder, 'img/')
    if not os.path.exists(output_img_folder):
        os.makedirs(output_img_folder)
    else:
        rmtree(output_img_folder)
        os.makedirs(output_img_folder)

    question_bank = {}

    for filename in Path(xmind_html_folder).glob('*.html'): \
            # for filename in tqdm(Path(xmind_html_folder).glob('*.html')):
        filename = str(filename)
        print(filename);
        question_name = os.path.basename(filename).split(".html")[0]
        print("Compiling question [{}] ... ".format(question_name), end="\r")
        with open(filename, "r") as html_file:
            html_raw = html_file.read()
            question_bank.update(html2question_bank(xmind_html_folder, json_dump_folder, html_raw, question_name))
        print("Compiling question [{}]: Done".format(question_name))

    with open(json_dump_folder + 'question_bank.json', 'w') as outfile:
        outfile.write(json.dumps(question_bank, indent=4, separators=(',', ': ')))


if __name__ == '__main__':
    main()
