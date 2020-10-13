import json
import os
import random
import tempfile
import webbrowser

from jinja2 import Environment, select_autoescape, FileSystemLoader

curr_dir_path = os.path.dirname(os.path.realpath(__file__))


class TemplateWrapper:
    def __init__(self, template=None, root_dir=curr_dir_path, content=None):
        self.content = {} if content is None else content
        self.template_dir = os.path.join(root_dir, 'templates/survey')
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        self.template = self.env.get_template(template) if template is not None else None

    def render(self, **kwargs):
        return self.template.render(**self.content, **kwargs)

    def open(self, **kwargs):
        html = self.render(**kwargs)
        tmp = tempfile.NamedTemporaryFile(delete=False)
        path = tmp.name + '.html'

        with open(path, 'w') as f:
            f.write(html)
        webbrowser.open('file://' + path)


class Survey(TemplateWrapper):
    def __init__(self, root_dir=curr_dir_path, content=None):
        super(Survey, self).__init__("survey.html", root_dir, content)
        self.page_templates = []
        self.quiz_page = []
        self.question_page = []
        self.checkpoint_page = [0]
        self.khan_page = -1
        self.mathbot_page = -1

    def add_checkpoint(self):
        self.checkpoint_page.append(len(self.page_templates))

    def insert_question_page(self, content):
        self.question_page.append(len(self.page_templates))
        self.page_templates.append(QuestionPage(content=content))

    def insert_quiz_page(self, content):
        self.quiz_page.append(len(self.page_templates))
        self.page_templates.append(QuizPage(content=content))

    def insert_instruction_page(self, template):
        self.page_templates.append(InstructionPage(template=template))

    def insert_khan_page(self, content):
        self.page_templates.append(KhanPage(content=content))
        self.khan_page = len(self.page_templates)

    def insert_tutorial_page(self, content):
        self.page_templates.append(TutorialPage(content=content))
        self.khan_page = len(self.page_templates)

    def insert_mathbot_page(self):
        self.page_templates.append(MathbotPage())
        self.mathbot_page = len(self.page_templates)

    def render(self, **kwargs):
        self.content['pages'] = [template.render(**kwargs) for template in self.page_templates]
        self.content['quiz_page'] = self.quiz_page
        self.content['question_page'] = self.question_page
        self.content['checkpoint'] = self.checkpoint_page
        self.content['khan_page'] = self.khan_page
        self.content['mathbot_page'] = self.mathbot_page
        return self.template.render(**self.content, **kwargs)


class QuestionPage(TemplateWrapper):
    def __init__(self, root_dir=curr_dir_path, content=None):
        super(QuestionPage, self).__init__("questionPage.html", root_dir, content)


class InstructionPage(TemplateWrapper):
    def __init__(self, template, root_dir=curr_dir_path):
        super(InstructionPage, self).__init__(template, root_dir)


class QuizPage(TemplateWrapper):
    def __init__(self, root_dir=curr_dir_path, content=None):
        super(QuizPage, self).__init__("quizPage.html", root_dir, content)


class MathbotPage(TemplateWrapper):
    def __init__(self, root_dir=curr_dir_path, content=None):
        super(MathbotPage, self).__init__("mathbotPage.html", root_dir, content)


class KhanPage(TemplateWrapper):
    def __init__(self, root_dir=curr_dir_path, content=None):
        super(KhanPage, self).__init__("khanPage.html", root_dir, content)


class TutorialPage(TemplateWrapper):
    def __init__(self, root_dir=curr_dir_path, content=None):
        super(TutorialPage, self).__init__("tutorialPage.html", root_dir, content)


def get_survey(userGroup="Khan"):
    survey = Survey(
        content={
            'title': "Online Learning Experience Study"
        }
    )

    survey_json_path = os.path.join(curr_dir_path, "static/resources/json/survey.json")
    survey_content = json.load(open(survey_json_path, encoding='utf-8'), encoding='utf-8')["pages"]
    quiz_json_path = os.path.join(curr_dir_path, "static/resources/json/quiz.json")
    quiz_content = json.load(open(quiz_json_path, encoding='utf-8'), encoding='utf-8')


    survey.insert_instruction_page("consent.html")
    survey.add_checkpoint()

    survey.insert_instruction_page("prerequisiteInstructionPage.html")
    survey.insert_quiz_page(content={"session": 0,
                                     "questions": quiz_content['prerequisiteQuiz'],
                                     "title": "1st Eligibility Quiz",
                                     "description": "Please answer the following 4 questions.<ul><li>You are encouraged to use scratch paper.</li><li>You are welcome to use a calculator.</li><li>This is an academic study. Please do not consult any outside resources while completing the quiz.</li></ul><br>"
                                     })
    survey.add_checkpoint()

    survey.insert_instruction_page("prequizInstructionPage.html")
    survey.insert_quiz_page(content={"session": 1,
                                     "questions": quiz_content['preQuiz'],
                                     "confidence": True,
                                     "title": "2nd Eligibility Quiz",
                                     "description": "Please answer the following 14 questions.<ul><li>You are encouraged to use scratch paper.</li><li>You are welcome to use a calculator.</li><li>This is an academic study. Please do not consult any outside resources while completing the quiz.</li></ul><br>"
                                     })
    survey.add_checkpoint()

    survey.insert_question_page(content=survey_content["pre-page-demographics"])
    survey.insert_question_page(content=survey_content["pre-page-math-background"])
    survey.add_checkpoint()

    survey.insert_instruction_page("mathbotInstructionPage.html")
    survey.add_checkpoint()
    
    survey.insert_mathbot_page()
    survey.add_checkpoint()
    
    survey.insert_quiz_page(content={"session": 2,
                                     "questions": quiz_content['postQuiz'],
                                     "confidence": True,
                                     "title": "Post-Learning Quiz",
                                     "description": "Your bonus payment of up to $8 is determined from your score on this quiz.<ul><li>You are encouraged to use scratch paper.</li><li>You are welcome to use a calculator.</li><li>This is an academic study. Please do not consult any outside resources while completing the quiz.</li></ul><br>"
                                     })
    survey.add_checkpoint()
    
    survey.insert_question_page(content=survey_content["post-page-rate-mathbot"])
    survey.insert_question_page(content=survey_content["post-page-likert"])
    survey.insert_question_page(content=survey_content["post-page-describe-mathbot"])
    survey.insert_question_page(content=survey_content["post-page-misc"])

    return survey


if __name__ == "__main__":
    print(curr_dir_path)
    survey = get_survey()
    user = dict(session_id=3, assignment_id=3)
    survey.open(debug=False, user=user)
