import json
import zipfile
import textwrap
import random
random.seed(0)

import argparse
import os
import re
from bs4 import BeautifulSoup

# global vars
from shutil import rmtree


parser = argparse.ArgumentParser(description='An engine that compiles XMIND files to \
        JSON graphs for the FSM in MathBot.')
parser.add_argument('xmind', type=str, help='XMIND file to compile.')
parser.add_argument('json', type=str, help='Folder to dump JSON files.')
parser.add_argument('question_bank', type=str, default='question_bank.json', help='File to dump question bank.')
parser.add_argument('-v', '--verbose', action='store_true', help='Verbose for debugging.')
args = parser.parse_args()


output_img_folder = os.path.join(args.json, 'img/')
text_output_file_folder = os.path.join(args.json, 'conversation_text_preview.txt')
text_output_file = open(text_output_file_folder, 'w')

alpha_numeric_letter = list("abcdefghijklmnopqrstuvwxyz1234567890")

if not os.path.exists(output_img_folder):
    os.makedirs(output_img_folder)
else:
    rmtree(output_img_folder)
    os.makedirs(output_img_folder)

# xmind_name = "intro-sequence-module.xmind"
# xmind_zip = zipfile.ZipFile(os.path.join(xmind_folder, xmind_name), "r")
xmind_zip = zipfile.ZipFile(args.xmind, "r")
question_bank = {}


def represents_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


def choice(letters, size=1, replace=True):
    return [letters[random.randint(0, len(letters) - 1)] for i in range(0, size)]


def get_branch_regex(content):
    conditions = content.split(' and ')
    only_int_check = []
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
                    val_to_match = c.split('==')[-1].strip().strip('"')
                    if represents_int(val_to_match):
                        # if int, check if it's the only int in the doc
                        only_int_check.append(val_to_match)
                    else:
                        # exact match if string
                        regex.append('^' + val_to_match + '$')
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
                # if affirmative words are in response
                regex.append('^(y)|^(right|sure|ok|okay|of course)$')
            elif 'idk' == c:
                # if idk-like words are in response
                regex.append("don't know|not know|don't understand|not understand|not sure|idk|hint")
            elif 'no' == c:
                # if negation words are in response
                regex.append('^(n)|(no|nah)')

    evals = []
    # functions here should correspond to eval functions in mathbot.js
    for r in only_int_check:
        evals.append("onlyIntMatch(response, \"%s\")" % r)
    for r in regex:
        evals.append("Boolean(response.match(\"%s\"))" % r)
    for nr in no_regex:
        evals.append("!Boolean(response.match(\"%s\"))" % nr)
    return {
        'evals': evals
    }


def get_branch_eval(content):
    if content.lower() == 'else':
        return {}
    else:
        return {
            'evals': [content]
        }


def split_long_sentence(content):
    # split by punctuation
    # return re.split(r'(?<=[^A-Z].[.?]) +(?=[A-Z])', content.strip())
    return content.split("\n")


def strip_out_redirection_node_prop(jump_to_content):
    """
    strip out redirection node id and annotation
    example: [concept][correct]pattern
    :param jump_to_content: content inside angular bracket
    :return:
    """
    next_prop = {}
    node_id = None
    for component in jump_to_content.split("]"):
        if "[" in component:
            c = component.strip("[")
            c = c.lower()

            if "=" not in c:
                next_prop[c] = True
            else:
                c1, c2 = c.split("=")
                next_prop[c1.strip()] = c2.strip()
        else:
            node_id = re.compile(',\s*').split(component)
            if len(node_id) == 1:
                node_id = node_id[0]
    return node_id, next_prop


DEBUG = args.verbose


def build_question_bank(topic_soup, sheet_name, curr_node_prop, node_id_count, parent_node_id, pending_branch,
                        indentation):
    content = topic_soup.find("title", recursive=False).text.strip()
    img_soup = topic_soup.find("xhtml:img", recursive=False)

    if DEBUG:
        print('|'.join(['\t'] * indentation) + '{')
        print('|'.join(['\t'] * indentation) + content)

    child_soup_list = topic_soup.find("children", recursive=False)
    if child_soup_list is None:
        child_soup_list = []
    else:
        child_soup_list = child_soup_list.find("topics", recursive=False).find_all("topic", recursive=False)

    # handle current node
    if bool(re.match('^\$.*\$$', content)):
        # if branch node
        pending_branch = get_branch_eval(content.strip('$'))

        for child_soup in child_soup_list:
            # curr_node_prop only exists for root nodes
            node_id_count = build_question_bank(topic_soup=child_soup,
                                                sheet_name=sheet_name,
                                                curr_node_prop={},
                                                node_id_count=node_id_count,
                                                parent_node_id=parent_node_id,
                                                pending_branch=pending_branch,
                                                indentation=indentation + 1)
    else:
        if bool(re.match('^<.*>$', content)):
            # if redirection node

            # if a redirection node follows the conversation node
            if bool(re.match('^<<.*>>$', content)):
                # if a redirection with return node
                jump_to_content = content[2:-2]
                next_type = "review"
            else:
                jump_to_content = content[1:-1]
                next_type = "new"

            next_node_id, next_prop = strip_out_redirection_node_prop(jump_to_content)

            if next_node_id == sheet_name:
                next_type = "self"

            next_prop['nextType'] = next_type
            if pending_branch is None:
                # if there is no pending branch, current node is a skip node
                question_bank[parent_node_id]['skip'] = next_node_id
                question_bank[parent_node_id]['nextProp'] = next_prop
            else:
                # if there is a pending branch, make next the jump node
                pending_branch['next'] = next_node_id
                pending_branch['nextProp'] = next_prop
                question_bank[parent_node_id]['branch'].append(pending_branch)

                # redirection node should not have any child
        else:
            # if the current node is a statement node, create a new node:

            # if not a branch node
            node_id_count += 1
            node_id_name = "%s-%d-%s" % (sheet_name, node_id_count, ''.join(choice(alpha_numeric_letter,
                                                                                   size=6,
                                                                                   replace=True)))

            # if the current node is a statement node, also log it in a text file for preview
            preview_wrapped_text = textwrap.wrap(content.replace('\n', ' '), width=55)
            text_output_file.write(' ' * indentation + '[' + node_id_name + ']\n')
            for preview_line in preview_wrapped_text:
                text_output_file.write(' ' * indentation + preview_line + '\n')
            text_output_file.write('\n')

            # quote equations with regular expression
            arithmetic_eq_re = re.compile(
                r'((((-?\d?\d?\d,\s*)+(\.\.\.)?(?!\ufe0f))|([a-z]\(.*?\))|((?<!\<)([\+\-\*/\d]\s*)+(?!\ufe0f))))',
                re.UNICODE)
            content, _n = re.subn(arithmetic_eq_re, r'<span>&#8203;</span>\1<span>&#8203;</span>', content)

            # if random node or not
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

            # if there's an image
            if img_soup is not None:
                img_zip_url = img_soup['xhtml:src'].split("xap:")[1]
                img_base_name = os.path.basename(img_zip_url)
                with open(os.path.join(output_img_folder, img_base_name), 'wb') as f:
                    f.write(xmind_zip.read(img_zip_url))
                img_web_link_relative_path = os.path.join('resources/json/img', img_base_name)
                new_sub_q['says'].append('<span><img src=%s></span>' % img_web_link_relative_path)

            if pending_branch is None:
                # if there is no pending branch, current node is a skip node
                if parent_node_id is not None:
                    question_bank[parent_node_id]['skip'] = node_id_name
                else:
                    new_sub_q['isRoot'] = True
                    new_sub_q['prop'] = curr_node_prop
                    node_id_count -= 1
                    node_id_name = sheet_name

            else:
                # if there is a pending branch, make next the jump node then append the pending branch
                pending_branch['next'] = node_id_name
                question_bank[parent_node_id]['branch'].append(pending_branch)

            question_bank[node_id_name] = new_sub_q

            for child_soup in child_soup_list:
                node_id_count = build_question_bank(topic_soup=child_soup,
                                                    sheet_name=sheet_name,
                                                    curr_node_prop={},
                                                    node_id_count=node_id_count,
                                                    parent_node_id=node_id_name,
                                                    pending_branch=None,
                                                    indentation=indentation + 1)

    if DEBUG:
        print('|'.join(['\t'] * indentation) + '}')

    return node_id_count


def check_fsm_flow(question_bank):
    for node_id in question_bank:
        if "skip" in question_bank[node_id]:
            if question_bank[node_id]["skip"] not in question_bank:
                raise Exception("There's an error at node %s, please check your xmind file" % node_id)
        elif len(question_bank[node_id]['branch']) > 0:
            for branch in question_bank[node_id]['branch']:
                if branch['next'] not in question_bank:
                    raise Exception("There's an error at node %s, please check your xmind file" % node_id)


def main():
    xmind_content_root = BeautifulSoup(xmind_zip.read("content.xml"), features="xml").find("xmap-content")

    for sheet in xmind_content_root.find_all("sheet", recursive=False):
        sheet_name = sheet.find("title", recursive=False).text
        sheet_name, curr_node_prop = strip_out_redirection_node_prop(sheet_name)
        root_topic_soup = sheet.find("topic", recursive=False)

        text_output_file.write('===[' + sheet_name + ']===\n')
        build_question_bank(topic_soup=root_topic_soup,
                            sheet_name=sheet_name,
                            curr_node_prop=curr_node_prop,
                            node_id_count=0,
                            parent_node_id=None,
                            pending_branch=None,
                            indentation=0)
        text_output_file.write('\n')
        text_output_file.write('\n')

    # check_fsm_flow(question_bank)

    with open(os.path.join(args.json, args.question_bank), 'w') as outfile:
        outfile.write(json.dumps(question_bank, indent=4, separators=(',', ': ')))

    text_output_file.close()


if __name__ == '__main__':
    main()
