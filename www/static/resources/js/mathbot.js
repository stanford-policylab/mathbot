function findGetParameter(parameterName) {
    var result = null,
        tmp = []
    location.search.substr(1).split('&').forEach(function (item) {
        tmp = item.split('=')
        if (tmp[0] === parameterName) result = decodeURIComponent(tmp[1])
    })
    return result
}

/***
 * Mathbot Finite State Machine
 * MathbotFSM is supposed to maintain current state of the mathbot and decide what to say next
 * @param fsmJson
 * @param randomDict
 * @param startNodeName
 * @constructor
 */
function MathbotFSM(
    fsmJson, randomDict, startNodeName, mathbotProgressCheckpoints) {
    //init
    var self = this;
    self.fsmJson = fsmJson;
    self.fsmJson['dummy_start_node'] = {
        'says': [],
        'branch': [],
        'skip': startNodeName,
    };
	flip = Math.floor(Math.random() * Math.floor(2)) //0, 1
	self.which_policy = 'uniform'
	if (flip == 0){
		self.which_policy='bandit'
	}
	console.log('policy is')
	console.log(self.which_policy)
	self.type_speed = 50;
    self.lastSectionCheckpoint = 'welcome';
    self.currNodeId = 'dummy_start_node';
    self.lastRootNodeId = 'dummy_start_node';
    self.completeFraction = 0;
    self.mathbotProgressCheckpoints = mathbotProgressCheckpoints;
    self.rootNodeVisitCount = {};
    self.rootNodeVisitCountIncludingReview = {};	
    self.rootNodeAttemptCount = {};
    self.randomDict = randomDict;
    self.unfinishedQuestionStack = [];
    self.unfinishedQuestionNextPropStack = [];
    self.previousRandom = {};
	self.isomorph_flag = false;
	self.bandit_flag = false;
	self.last_test_question = 0;
	//when did we pull the bandit for question [key]?  The time that question [key] gets answered minus this is the wall to wall time used in reward.  
	self.bandit_pull_times = {}

	self.test_question_start_times = {}
	self.test_question_finish_times = {}
	self.skip_actions_taken = {}
	self.isomorph_actions_taken = {}
    self.mathbot_initialization_time = (new Date()).getTime();
	self.max_times = {'q-intro':100000000000, "1-1":120000, "1-2":75000, "2-1":160000, "2-2":125000, 
               "2-3":100000, "4-1":190000, "4-2":700000, "4-2b":450000, 
               "4-3":330000, "4-4":400000, "4-5":1070000}

	self.stable_test_questions = ['1-1', '1-2', '2-1', '2-2', '2-3', '4-1', '4-2', '4-2b', '4-3', '4-4', '4-5'] // to have one that isn't popped
	self.test_questions = ['q-intro', '1-1', '1-2', '2-1', '2-2', '2-3', '4-1', '4-2', '4-2b', '4-3', '4-4', '4-5'] // only pull bandit after hitting these (don't include last question)
	self.root_nodes = ['welcome', 'welcome-real', 'q-intro-isomorph', 'q-intro', 'sequence', '1-1-isomorph', '1-1', 'sequence-reflection', 'pattern', '1-2-isomorph', '1-2', 'pattern-reflection', 'end1', 'arithmetic', '2-1-isomorph', '2-1', 'arithmetic-reflection', 'end2', 'difference', '2-2-isomorph', '2-2', '2-3-isomorph', '2-3', 'difference-reflection', 'end3', 'formula', '4-1-isomorph', '4-1', 'formula-reflection', 'recursive', '4-2-isomorph', '4-2', '4-2b-isomorph', '4-2b', 'recursive-reflection', 'end4', 'explicit-1', '4-3-isomorph', '4-3', 'explicit-1-reflection', 'explicit-2', '4-4-isomorph', '4-4', 'explicit-2-reflection', 'end5', 'equivalent', '4-5-isomorph', '4-5b-isomorph', '4-5', '4-5b', 'equivalent-reflection']
	self.furthest_node = -1; //max over all nodes seen of self.root_nodes.indexOf(nodeid)
	
	// we don't pull the bandit for the first one, so use this to compute time
	self.bandit_pull_times[self.test_questions[0]] = (new Date()).getTime();
	self.question_to_isomorph = {}
	
	for (var tq in self.test_questions){
		self.question_to_isomorph[self.test_questions[tq]] = self.test_questions[tq]+"-isomorph"
	}

    this.getCurrNodeId = function () {
        return self.currNodeId
    };

    this.getCurrNodeSays = function () {
        if (self.fsmJson[self.currNodeId]['says']) {
            return self.fsmJson[self.currNodeId]['says']
        } else {
            var randomType = self.fsmJson[self.currNodeId]['random'];
            return sayRandom(randomType)
        }
    };

    this.isCurrNodeSkipNode = function () {
        return Boolean(self.fsmJson[self.currNodeId].skip)
    };

    this.getProgress = function () {
        return Math.floor(self.completeFraction * 10) / 10
    };

    this.getLastSectionCheckpoint = function () {
        return self.lastSectionCheckpoint
    };

    // build context 
    self.context = {};
    self.context['startTime'] = new Date();
    self.context['timezone'] = (new Date()).getTimezoneOffset() / 60;
    self.context['platform'] = navigator.platform;
    self.context['userAgent'] = navigator.userAgent;
	console.log('userAgent is')
	console.log(navigator.userAgent)
    self.context['cookieEnabled'] = navigator.cookieEnabled;
    self.context['questions'] = [];
    console.log(self.context);

    // response time
    self.beginResponseTime;

    // this is a hack
    self.currContext;

    /***
     * keep walking down the FSM until a response is required
     * @param response
     * @returns {Array}
     */
    this.keepSayingUntilNextResponseRequired = function (response) {
        self.currContext = {};
        self.currContext['response'] = response;
        self.currContext['currNodeId'] = self.currNodeId;
        self.currContext['responseTime'] = (new Date()).getTime() - self.beginResponseTime;
        var says = [];
        says = says.concat(moveAndSay(response))

        self.context['questions'].push(self.currContext)
        console.log(self.context)

        while (self.isCurrNodeSkipNode()) {
            says = says.concat(moveAndSay(response))
        }
        return says
    };
	
    this.getAction = function (context, callBack) {
        //Sends a GET request to url and will send the contents of the data object as query parameters.
        //When this is done, callBack is called to trigger the render
        foo = $.getJSON($SCRIPT_ROOT + '/_get_action', {
            context: context
        }, callBack(data)
					   )
    };
    // LOCAL PRIVATE FUNCTIONS

	//contextual bandit mockup. Given a context returns an action. 
	function policy(context){
		//compute the reward
		reward_dict = {}		
		//figure out what the last question we answered was
		console.log('we just answered')
		console.log(self.last_test_question)
		reward_dict['test_question'] = self.last_test_question
		
		num_tries = context['num_attempts_last_question']
		var reward = 150000;
		if (num_tries > 0) {
			reward = 0;
		}
		t = context['last_test_question_time']
		reward = reward - t
		console.log('reward is')
		console.log(reward)
		
		reward_dict['reward'] = reward
		
		//write reward to the reward table
		$.ajax({
			type: 'POST',
			async: true,
			url: '/api/record_reward',
			data: reward_dict,
			success: null,
			dataType: 'json',
		})
		
		//write the context of this pull to the context table
		$.ajax({
            type: 'POST',
            async: true,
            url: '/api/record_context',
            data: context,
            success: null,
            dataType: 'json',
        })
		
		//ask the bandit what action to take
		var action = $.ajax({
            type: 'POST',
            async: false,
            url: '/api/get_action',
            data: context,
            success: null,
            dataType: 'json',
        })
		

		//if there are no more test questions, disregard action
		if (self.test_questions.length == 0){
			var action_dict = {}
			action_dict['isomorph'] = 0;
			action_dict['skip_concept'] = 0;
		}
		else{
			var action_dict = action['responseJSON']['action_dict']
		}
		
		console.log(action_dict)
		var return_actions = []
		if (action_dict['isomorph'] == 1){
			return_actions.push('isomorph')			
		}
		if (action_dict['skip_concept'] == 1){
			return_actions.push('skip_concept')
		}
		/* uniform random is implemented in backend now 
		console.log('we are not using the bandit policy, and we are instead using uniform random.')
		action = Math.floor(Math.random() * Math.floor(4)) //0, 1, 2, 3
		if (action == 0){
			return([])
		}
		else if (action == 1){
			return(['skip_concept'])	
		}
		else if (action == 2){
			return(['isomorph'])	
		}
		else{
			return(["skip_concept", "isomorph"])	
		}
		*/
		return return_actions
		//mooclet id is 101
	}

    /***
     * Find and return node to forward to when get the current question wrong 3 times
     * @param currNode
     */
    function findForwardNode(currNodeId) {
        console.log(currNodeId);
        //if a skip node
        if (self.fsmJson[currNodeId]['skip']) {
            var nextNodeId = self.fsmJson[currNodeId]['skip'];
            if (nextNodeId.constructor === Array) {
                nextNodeId = nextNodeId[0];
            }
            var nextProp = self.fsmJson[currNodeId]['nextProp'];
            // stop recursion at next root node
            if (self.fsmJson[nextNodeId]['isRoot']) {
                if (nextProp['forward']) {
                    return nextNodeId
                } else {
                    return false
                }
            } else {
                var forwardNodeId = findForwardNode(nextNodeId);
                if (forwardNodeId) {
                    return forwardNodeId
                }
            }
        } else {
            if (self.fsmJson[currNodeId]['branch'].length > 0) {
                for (var i = 0; i <
                self.fsmJson[currNodeId]['branch'].length; i++) {
                    var branch = self.fsmJson[currNodeId]['branch'][i];
                    var nextNodeId = branch['next'];
                    var nextProp = branch['nextProp'];
                    // stop recursion at next root node
                    if (self.fsmJson[nextNodeId]['isRoot']) {
                        if (nextProp && nextProp['forward']) {
                            return nextNodeId
                        } else {
                            return false
                        }
                    } else {
                        var forwardNodeId = findForwardNode(nextNodeId);
                        if (forwardNodeId) {
                            return forwardNodeId
                        }
                    }
                }
            }
        }
        return false
    }
	
    /***
     * Find and return node to move to if we want to do the 'skip_concept' action.  
     * @param currNode
     */

    function findNextGradedNode(currNodeId) {
		return self.test_questions[0]
	}
	
    /***
     *
     * @param randomType
     */
    function sayRandom(randomType) {
        var idx = Math.floor(Math.random() *
            self.randomDict[randomType].length);
        // random but not previous
        while (self.previousRandom[randomType] === idx &&
        self.randomDict[randomType].length > 1) {
            idx = Math.floor(Math.random() *
                self.randomDict[randomType].length)
        }
        self.previousRandom[randomType] = idx;
        return self.randomDict[randomType][idx]
    }

    /***
     * More to the next node and return the says of the node
     * @param response user response
     */
    function moveAndSay(response) {
    	var ind = self.test_questions.indexOf(self.currNodeId)
    	if (ind >= 0){
			self.last_test_question = self.test_questions[ind]
    	    self.test_questions.splice(ind, 1);
    	    console.log('turning the bandit on')
    	    self.bandit_flag = true;
    	}
    	
    	var skip_concept_flag = false;
        var currNode = self.fsmJson[self.currNodeId];
		console.log('curr node is ')
		console.log(currNode)
        //if there's no next node, do not move anywhere and return
        if ((currNode.branch && currNode.branch.length === 0) &&
            !currNode.skip) {
            return []
        }

        var nextNodeId;
        // how we came to the current node
        var nextProp;
        var says = [];

        if (self.isCurrNodeSkipNode()) {
            //if current node is a skip node, skip to it
            nextNodeId = currNode.skip;
            nextProp = currNode.nextProp
        } else {
            //if current node is not a skip node, then we should expect branches or it is a terminal node
            var matchResult = match(currNode, response);
            nextNodeId = matchResult['next'];
            nextProp = matchResult['nextProp']

            // this is a hack
            // to pass next prop around
            self.nextProp = nextProp
        }

        var nextNodeIdList;
        if (nextNodeId.constructor === Array) {
            nextNodeIdList = nextNodeId;
            nextNodeId = nextNodeIdList[0];
        }

        /**
         *
         * 0 = 0000(binary), with each digit representing:
         * xxx1: we are going to a concept node, otherwise question
         * xx1x: get the current question wrong, otherwise correct
         * 00xx: we are going to a new node (00), review a node (01),
         * come back from a reviewed node (10), or just redo the same question (11)
         * by default is 0000 = correct-question-new
         * handle random says based on sayMarker
         *
         */
        var sayMarker = 0;
        //console.log(self.unfinishedQuestionStack);
        if (nextProp && nextProp['nextType']) {
            //Decide if we want to proceed to the next question in the graph or this is merely a review question by examining the stack
            if (nextProp && nextProp['nextType'] === 'new') {
                self.unfinishedQuestionStack.pop();
                self.unfinishedQuestionNextPropStack.pop();
                if (self.unfinishedQuestionStack.length > 0) {
                    //going back to previous question/concept
                    nextNodeId = self.unfinishedQuestionStack.pop();
                    self.unfinishedQuestionNextPropStack.pop();
                    sayMarker += 0b1000;
                    //if the node we are going back to (from the stack) is a concept or a question
                    // noinspection JSAnnotator
                    sayMarker += (self.fsmJson[nextNodeId]['prop'] &&
                        self.fsmJson[nextNodeId]['prop']['concept']) ? 0b0001 : 0b0000;
                    //if we get the CURRENT answer correct
                    sayMarker += nextProp['wrong'] ? 0b0010 : 0b0000
                } else {
                    // when there is no questions left in the stack, say new question stuff
                    sayMarker += 0b0000;
                    sayMarker += (self.fsmJson[nextNodeId]['prop'] &&
                        self.fsmJson[nextNodeId]['prop']['concept']) ? 0b0001 : 0b0000;
                    sayMarker += nextProp['wrong'] ? 0b0010 : 0b0000
                }
            } else if (nextProp && nextProp['nextType'] === 'review') {
                // if review, do not pop the stacks
                sayMarker += 0b0100;
                sayMarker += (self.fsmJson[nextNodeId]['prop'] &&
                    self.fsmJson[nextNodeId]['prop']['concept']) ? 0b0001 : 0b0000;
                sayMarker += nextProp['wrong'] ? 0b0010 : 0b0000
            } else if (nextProp && nextProp['nextType'] === 'self') {
                // if the next node is the question itself, simply pop out the current top element in the stack as it will be pushed back in again
                self.unfinishedQuestionStack.pop();
                self.unfinishedQuestionNextPropStack.pop();
                sayMarker += 0b1100;
                sayMarker += (self.fsmJson[nextNodeId]['prop'] &&
                    self.fsmJson[nextNodeId]['prop']['concept']) ? 0b0001 : 0b0000;
                sayMarker += nextProp['wrong'] ? 0b0010 : 0b0000;
            } else {
                console.error('Unexpected nextType:', nextProp['nextType'])
            }

            // disable reading property
            if (nextProp && nextProp['disable']) {
                sayMarker = -1
            }


            // after popping the stack, if nothing left, then we are done reviewing a node or going back to a node itself
            // either way, we'd like to check if we are revisiting the the next for multiple times
            // if > 3 times then we are going to find the forward node and skip this one
			console.log('done popping the stack')
			console.log(self.rootNodeVisitCount)
			console.log(self.rootNodeVisitCountIncludingReview)
            if (self.unfinishedQuestionStack.length === 0 &&
                self.fsmJson[nextNodeId]['isRoot']) {
                if (nextNodeId in self.rootNodeVisitCount) {
                    self.rootNodeVisitCount[nextNodeId] += 1;
					self.rootNodeVisitCountIncludingReview[nextNodeId] += 1;		    
                } else {
                    self.rootNodeVisitCount[nextNodeId] = 1;
					self.rootNodeVisitCountIncludingReview[nextNodeId] = 1;
                }
				
                var forwardNodeId;
                if (self.rootNodeVisitCountIncludingReview[nextNodeId] >= 4) {
					console.log('trigger find forward node')
                    forwardNodeId = findForwardNode(nextNodeId);
					console.log(forwardNodeId)
                } else {
                    forwardNodeId = false;
                }
                //if there is a forward node, skip to it, otherwise everything is the same as above
                if (forwardNodeId) {
                    nextNodeId = forwardNodeId;
                    //reset nextProp so that it has grade wrong and transition
                    nextProp = {
                        'no_grade': true,
                    };
                    sayMarker = 0b0010;
                    sayMarker += (self.fsmJson[nextNodeId]['prop'] &&
								  self.fsmJson[nextNodeId]['prop']['concept']) ? 0b0001 : 0b0000;
					//mark that we're seeing the forward node
                    if (nextNodeId in self.rootNodeVisitCount) {
						self.rootNodeVisitCount[nextNodeId] += 1;
						self.rootNodeVisitCountIncludingReview[nextNodeId] += 1;		    
                    } else {
						self.rootNodeVisitCount[nextNodeId] = 1;
						self.rootNodeVisitCountIncludingReview[nextNodeId] = 1;
                    }					
                }
            }
            // keep track of number of times we encounter [attempt tag]
            // only count towards attempt when we are not reviewing
            // unfinishedQuestionStack.length == 0 means no reviewing, and == 1 means just started reviewing
            if (self.unfinishedQuestionStack.length <= 1 && nextProp['attempt']) {
                console.log(self.lastRootNodeId, "ATTEMPT");
                if (self.lastRootNodeId in self.rootNodeAttemptCount) {
                    self.rootNodeAttemptCount[self.lastRootNodeId] += 1;
                } else {
                    self.rootNodeAttemptCount[self.lastRootNodeId] = 1;
                }
            }
        } else {
            sayMarker = -1;
        }

        if (sayMarker != -1) {
            switch (sayMarker) {
                case 0b1111:
                    // Give the wrong answer and going to redo the same concept
                    // THIS SHOULD RARELY HAPPEN BUT LET'S KEEP THIS ANYWAYS
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('wrong_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(
                            sayRandom('try_again_the_same_concept'))
                    }
                    break;
                case 0b1110:
                    // Give the wrong answer and going to redo the same question
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('wrong_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(
                            sayRandom('try_again_the_same_question'))
                    }
                    break;
                case 0b1101:
                    // Give the right answer but still redo the same concept
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('correct_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(
                            sayRandom('try_again_the_same_concept'))
                    }
                    break;
                case 0b1100:
                    // Give the right answer but still redo the same question
                    // happens when the student fail the main question but get the follow-up guiding sub-questions right
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('correct_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(
                            sayRandom('try_again_the_same_question'))
                    }
                    break;
                // case 0b1011:
                //     // Give the wrong answer and done reviewing coming back to a concept
                //     // SHOULD NOT HAPPEN
                //     break;
                // case 0b1010:
                //     // Give the wrong answer and done reviewing coming back to a question
                //     // SHOULD NOT HAPPEN
                //     break;
                case 0b1001:
                    // Give the right answer and done reviewing coming back to a question
                    // THIS SHOULD RARELY HAPPEN BUT LET'S KEEP THIS ANYWAYS
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('correct_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(
                            sayRandom('previously_failed_concept'))
                    }
                    break;
                case 0b1000:
                    // Give the right answer and done reviewing coming back to a question
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('correct_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(
                            sayRandom('previously_failed_question'))
                    }
                    break;
                case 0b0111:
                    // Got the answer wrong and going to review something concept
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('wrong_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(sayRandom('try_easier_concept'))
                    }
                    break;
                case 0b0110:
                    // Got the answer wrong and going to review something easier question
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('wrong_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(sayRandom('try_easier_question'))
                    }
                    break;
                // case 0b0101:
                // get the answer correct, but still going to review some concept
                // SHOULD NOT HAPPEN
                // break;
                // case 0b0100:
                // get the answer correct, but still going to review something
                // SHOULD NOT HAPPEN
                // break;
                case 0b0011:
                    // give the wrong answer but still going to do a new concept
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('wrong_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(
                            sayRandom('wrong_answer_but_new_concept'))
                    }
                    break;
                case 0b0010:
                    // give the wrong answer but still going to do a new question
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('wrong_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(
                            sayRandom('wrong_answer_but_new_question'))
                    }
                    break;
                case 0b0001:
                    // get the question correct and going to a concept
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('correct_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(sayRandom('another_concept'))
                    }
                    break;
                case 0b0000:
                    // get the question correct and going to a new question
                    if (!nextProp['no_grade']) {
                        says = says.concat(sayRandom('correct_answer'))
                    }
                    if (!nextProp['no_transition']) {
                        says = says.concat(sayRandom('another_question'))
                    }
                    break;
                default:
                    console.error('Random Branch [' + sayMarker.toString(2) +
                        ']; This should not happend!')

            }
        }

        //if the node we are about to move to is a root node, push it in the stack
        var nextNode = self.fsmJson[nextNodeId];
        if (nextNode['isRoot']) {
            if (nextNodeIdList) {
                // reversely push in
                for (var i = nextNodeIdList.length - 1; i >= 0; i--) {
                    self.unfinishedQuestionStack.push(nextNodeIdList[i]);
                    self.unfinishedQuestionNextPropStack.push(nextProp);
                }
            } else {
                self.unfinishedQuestionStack.push(nextNodeId);
                self.unfinishedQuestionNextPropStack.push(nextProp);
            }
        }

        // keep track of progress
        if (self.rootNodeVisitCount[nextNodeId] == 1 &&
            self.mathbotProgressCheckpoints[nextNodeId]) {
            self.completeFraction = self.mathbotProgressCheckpoints[nextNodeId]
        }


        // for experiment section progress track
        if ([
            'welcome', 'arithmetic', 'difference', 'formula', 'explicit-1',
            'explicit-3'].indexOf(nextNodeId) > -1) {
            self.lastSectionCheckpoint = nextNodeId
        }
		//update further_node_seen if this new node is the furthest node
		if (self.root_nodes.indexOf(nextNodeId) > self.furthest_node){
			self.furthest_node = self.root_nodes.indexOf(nextNodeId)
		}
		
        //make the move
        self.currNodeId = nextNodeId;
        if (self.fsmJson[self.currNodeId]['isRoot']) {
            self.lastRootNodeId = self.currNodeId;
        }
        var old_says = says;		
        says = says.concat(self.getCurrNodeSays());

		
    	//if the bandit flag is on and  we are hitting a root node which is the furthest we've been
        //we are progressing to a new concept or question which we haven't skipped before.
    	if (self.bandit_flag  && self.fsmJson[self.currNodeId]['isRoot'] && self.rootNodeVisitCountIncludingReview[self.currNodeId] == 1 && self.furthest_node == self.root_nodes.indexOf(self.currNodeId)){
    	    console.log('we are calling the policy')
    	    console.log('we are at node')
    	    console.log(self.currNodeId)
    	    console.log(self.unfinishedQuestionStack) //I think self.currNodeId should be the only thing in this stack.
			//TODO if we've been to a node which is later than self.currNodeId, 
			
			/* compute context for policy
			   Score on pre-learning quiz on arithmetic sequences
			   Prerequisite quiz score (potentially)
			   Algebra knowledge quiz in pre-learning survey
			*/
			var bandit_context = {};
			
			var time_since_starting_lesson = (new Date()).getTime() - self.mathbot_initialization_time
			console.log('type speed is')
			console.log(self.type_speed)
			bandit_context['type_speed'] = self.type_speed
			
			console.log('time since we have started the lesson is')
			console.log(time_since_starting_lesson)
			bandit_context['time_since_starting_lesson'] = time_since_starting_lesson

			console.log('the skip actions we have taken are:')
			console.log(self.skip_actions_taken)
			console.log('the isomorph actions we have taken are:')			
			console.log(self.isomorph_actions_taken)
			console.log('question we just finished is ')
			console.log(self.last_test_question)
			console.log('the test question we are about to hit is ')
			console.log(self.test_questions[0])
			if (self.test_questions.length > 0){
				bandit_context['next_test_question'] = self.test_questions[0];
			}
			else{
				bandit_context['next_test_question'] = "END"
			}
			bandit_context['skipped_last_question']	= 0			
			if (self.skip_actions_taken[self.last_test_question]){
				bandit_context['skipped_last_question']	= 1
				console.log('We skipped the previous question')				
			}
			bandit_context['isomorphed_last_question'] = 0			
			if (self.isomorph_actions_taken[self.last_test_question]){
				bandit_context['isomorphed_last_question']	= 1
				console.log('We isomorphed the previous question')				
			}
			
			var num_attempts_last_question = 0;
			if (self.last_test_question in self.rootNodeAttemptCount){
				num_attempts_last_question = self.rootNodeAttemptCount[self.last_test_question];
			}
			console.log("num_attempts_last_question is ")
			console.log(num_attempts_last_question)
			bandit_context['num_attempts_last_question'] = num_attempts_last_question
			
			var test_question_finish_time = (new Date()).getTime()
			if (!(self.currNodeId in self.test_question_finish_times)){
				self.test_question_finish_times[self.last_test_question] = test_question_finish_time;
				console.log('test question finish times are')
				console.log(self.test_question_finish_times)
			}
			else{//don't think this should ever happen
				console.log('this is not good?')
			}
			//this should instead be self.test_question_finish_times[self.last_test_question] - self.bandit_pull_times[self.last_test_question]
			console.log('when computing test question time last question is')
			console.log(self.last_test_question)
			
			var test_q_time = self.test_question_finish_times[self.last_test_question] - self.bandit_pull_times[self.last_test_question]
			console.log('the time is took to finish the last test question was')
			console.log(test_q_time)
			if(test_q_time > self.max_times[self.last_test_question]){
				console.log('we are capping the test question time for')
				console.log(self.last_test_question)
				test_q_time = self.max_times[self.last_test_question]
			}
			bandit_context['last_test_question_time'] = test_q_time
			bandit_context['which_policy'] = self.which_policy
			console.log('policy is')
			console.log(self.which_policy)
			//get the pre quiz score by looking at the url of the iframe
			pre_q_score = findGetParameter('pre_q_score')
			console.log('pre quiz score is ')
			console.log(pre_q_score)
			console.log('as int, pre quiz score is ')			
			console.log(parseInt(pre_q_score))
			self.pre_q = parseInt(pre_q_score)
			bandit_context['pre_q'] = self.pre_q
    	    var action = policy(bandit_context) //policy should return a list of actions
			//record when we start this question
			console.log('recording when we start wall-wall timer for test question')
			console.log(self.test_questions[0])
			self.bandit_pull_times[self.test_questions[0]] = (new Date()).getTime()//
			console.log(self.bandit_pull_times)
			//
    	    if (action.indexOf('isomorph') >= 0){
                self.isomorph_flag = true;
				self.isomorph_actions_taken[self.test_questions[0]] = true
            }
			else{
				self.isomorph_actions_taken[self.test_questions[0]] = false
			}
    	    if (action.indexOf('skip_concept') >= 0){
    		//skip until next question
    			skip_concept_flag = true
				self.skip_actions_taken[self.test_questions[0]] = true
    	    }
			else{
				self.skip_actions_taken[self.test_questions[0]] = false
			}
    	    self.bandit_flag = false
    	}
		if (skip_concept_flag){
			//at this moment, I think says will have the stuff before the root node?
			//silence the concept we just started
			if (self.fsmJson[self.currNodeId]['says']){
				says=old_says;
			}
			console.log("we are at node: ")
			console.log(self.currNodeId)
			console.log("here is the rootNodeVisitCountIncludingReview ")
			console.log(self.rootNodeVisitCountIncludingReview)

			// figure out where we want to skip to
			nextNodeId = findNextGradedNode(self.currNodeId)

			// if isomorph_flag is on, go to the isomorph of this instead
			if (self.isomorph_flag){
				nextNodeId = self.question_to_isomorph[nextNodeId]
				self.isomorph_flag = false;
			}
			
			console.log('we will skip to:')
			console.log(nextNodeId)

			//if this is the same as where we are right now, don't do anything
			
            // keep track of number of visit at each root node so that the student won't get stuck at somewhere
			
			//set the counter for seeing root nodes
            if (nextNodeId in self.rootNodeVisitCount) {
				console.log('1')		    
                self.rootNodeVisitCount[nextNodeId] += 1;
				self.rootNodeVisitCountIncludingReview[nextNodeId] += 1;		    
            } else {
				console.log('2')
				console.log('just initiated')
				console.log(nextNodeId);
                self.rootNodeVisitCount[nextNodeId] = 1;
				self.rootNodeVisitCountIncludingReview[nextNodeId] = 1;		    		    
            }
            //since all the test questions are root nodes, we want to pop the concept we just put in the stack (since we are skipping it),
            //and push the root node in
            //todo nextnodeidlist
            var nextnodeidlist = false;
            self.unfinishedQuestionStack.pop();
            self.unfinishedQuestionNextPropStack.pop();
            var nextNode = self.fsmJson[nextNodeId];
            if (nextNode['isRoot']) {
                if (nextNodeIdList) {
                    // reversely push in
                    for (var i = nextNodeIdList.length - 1; i >= 0; i--) {
                        self.unfinishedQuestionStack.push(nextNodeIdList[i]);
                        self.unfinishedQuestionNextPropStack.push(nextProp);
                    }
                } else {
                    self.unfinishedQuestionStack.push(nextNodeId);
                    self.unfinishedQuestionNextPropStack.push(nextProp);
                }
            }

            // for experiment section progress track
            if ([
				'welcome', 'arithmetic', 'difference', 'formula', 'explicit-1',
				'explicit-3'].indexOf(nextNodeId) > -1) {
				self.lastSectionCheckpoint = nextNodeId
            }
			
			//keep track of progress 
            if (self.rootNodeVisitCount[nextNodeId] == 1 &&
				self.mathbotProgressCheckpoints[nextNodeId]) {
				self.completeFraction = self.mathbotProgressCheckpoints[nextNodeId]
			}
			//update further_node_seen if this new node is the furthest node
			if (self.root_nodes.indexOf(nextNodeId) > self.furthest_node){
				self.furthest_node = self.root_nodes.indexOf(nextNodeId)
			}
			
			//actually make the move
			self.currNodeId = nextNodeId;
            if (self.fsmJson[self.currNodeId]['isRoot']) {
				self.lastRootNodeId = self.currNodeId;
            }
			says = says.concat(self.getCurrNodeSays());
		}
		else if (self.isomorph_flag){  
			//if we are isomorphing AND we are at a test question (now that we've made the move), go to the isomorph instead

			var ind = self.test_questions.indexOf(self.currNodeId)
			if (ind >= 0){
				//at this moment, I think says will have the stuff before the root node?
				//silence the concept we just started
				if (self.fsmJson[self.currNodeId]['says']){
					says=old_says;
				}

				
				// subtract one from the (attempts, rootnodevisit count, rootnodevisitcountincludingreview, experiment section, progress) of the original question (in self.currNodeId)
				//basically undo all the stuff we do before going to node since we're not really going to this node yet

				//undo rootnodevisitcount stuff
				self.rootNodeVisitCount[nextNodeId] -= 1;
				self.rootNodeVisitCountIncludingReview[nextNodeId] -= 1;		    

				//remove from the stack
				//TODO deal with nextNodeIdList				
				if (nextNodeIdList) {
					for (var i = nextNodeIdList.length - 1; i >= 0; i--) {
						self.unfinishedQuestionStack.pop()
						self.unfinishedQuestionNextPropStack.pop()
					}
				} else {
					self.unfinishedQuestionStack.pop()
					self.unfinishedQuestionNextPropStack.pop()
				}

				// undo progress
				if (self.rootNodeVisitCount[nextNodeId] == 1 &&
                    self.mathbotProgressCheckpoints[nextNodeId]) {
                    self.completeFraction = self.mathbotProgressCheckpoints[nextNodeId]
				}

				// for experiment section progress track (idk what this is but it's also annoying to undo so i'll ignore it for now)
				/*
				if ([
				'welcome', 'arithmetic', 'difference', 'formula', 'explicit-1',
				'explicit-3'].indexOf(nextNodeId) > -1) {
				self.lastSectionCheckpoint = nextNodeId
				}
				*/
				
				// get the isomorph node
				nextNodeId = self.question_to_isomorph[nextNodeId]
				self.isomorph_flag = false;		
				console.log('The isomorph we want is here:')
				console.log(nextNodeId)
				
				// keep track of the number of visits at each root node 
				if (nextNodeId in self.rootNodeVisitCount) {
                    self.rootNodeVisitCount[nextNodeId] += 1;
					self.rootNodeVisitCountIncludingReview[nextNodeId] += 1;		    
				} else {
					console.log(nextNodeId);
                    self.rootNodeVisitCount[nextNodeId] = 1;
					self.rootNodeVisitCountIncludingReview[nextNodeId] = 1;		    		    
				}
				//we just put the test question in the stack(I believe), so all we need to do is add the isomorph s.t. when we come back we're on the test question
				//todo nextnodeidlist
				var nextnodeidlist = false;
				self.unfinishedQuestionStack.pop();
				self.unfinishedQuestionNextPropStack.pop();
				var nextNode = self.fsmJson[nextNodeId];
				if (nextNode['isRoot']) {
                    if (nextNodeIdList) {
						// reversely push in
						for (var i = nextNodeIdList.length - 1; i >= 0; i--) {
                            self.unfinishedQuestionStack.push(nextNodeIdList[i]);
                            self.unfinishedQuestionNextPropStack.push(nextProp);
						}
                    } else {
						self.unfinishedQuestionStack.push(nextNodeId);
						self.unfinishedQuestionNextPropStack.push(nextProp);
                    }
				}

				// for experiment section progress track
				if ([
					'welcome', 'arithmetic', 'difference', 'formula', 'explicit-1',
					'explicit-3'].indexOf(nextNodeId) > -1) {
					self.lastSectionCheckpoint = nextNodeId
				}
				
				//keep track of progress 
				if (self.rootNodeVisitCount[nextNodeId] == 1 &&
					self.mathbotProgressCheckpoints[nextNodeId]) {
					self.completeFraction = self.mathbotProgressCheckpoints[nextNodeId]
				}
				//update further_node_seen if this new node is the furthest node
				if (self.root_nodes.indexOf(nextNodeId) > self.furthest_node){
					self.furthest_node = self.root_nodes.indexOf(nextNodeId)
				}
				
				//actually make the move
				self.currNodeId = nextNodeId;
				
				if (self.fsmJson[self.currNodeId]['isRoot']) {
					self.lastRootNodeId = self.currNodeId;
					console.log('we just set lastRootNodeId to ')
					console.log(self.lastRootNodeId)
				}
				says = says.concat(self.getCurrNodeSays());
				
			}
			else{
				console.log('isomorph flag is on but we are not at a test question')
			}
		}

		//set the start time of a test question when seeing the context
		if (self.stable_test_questions.indexOf(self.currNodeId) >= 0){
			var test_question_start_time = (new Date()).getTime()
			//first time going to the question			
			if (!(self.currNodeId in self.test_question_start_times)){
				self.test_question_start_times[self.currNodeId] = test_question_start_time;
				console.log('test question start times are')
				console.log(self.test_question_start_times)

			}
		}
		
        return says
    }

    /***
     * match user reponses with one of the branches; return null if none is matched
     * @param current current node
     * @param response user response
     */
    function match(current, response) {

        /***
         * =======HELPER MATCHING FUNCTIONS========
         *
         */


        function getNumAttempt() {
            if (!(self.lastRootNodeId in self.rootNodeAttemptCount)) {
                return 0;
            }
            return self.rootNodeAttemptCount[self.lastRootNodeId];
        }

        function currentAttempt(num) {
            return (getNumAttempt() == num);
        }

        /***
         * Match a kind of responses
         * @param response
         * @param typeName
         * @returns {boolean}
         */
        function typedResponseMatch(response, typeName) {
            var regexToMatch = '';
            var regexNotToMatch = '';
            switch (typeName) {
                case 'yes':
                    regexToMatch = '^(y)|(right|sure|ok|okay|of course|think so|got it)$';
                    regexNotToMatch = 'don\'t|no|nah';
                    break;
                case 'no':
                    regexToMatch = 'n|no|nah';
                    break;
                case 'idk':
                    regexToMatch = 'don\'t know|not know|don\'t understand|not understand|not sure|idk|hint';
                    break
            }
            return Boolean(response.match(regexToMatch)) &&
                (regexNotToMatch == '' ? true : !Boolean(
                    response.match(regexNotToMatch)))
        }

        /***
         * if response contains subString; Case insensitive
         * @param response
         * @param subString
         * @returns {boolean}
         */
        function containsSubstring(response, subString) {
            return response.toString().toLowerCase().indexOf(subString.toString().toLowerCase()) !== -1
        }


        // converts a(n) = A + B(n - 1) to usable form
        function explicitFormulaMatch(response, subString) {
            var str = response.toString().toLowerCase()
            //remove spaces
            str = str.replace(/\s/g, '')
            //remove multiplication signs
            str = str.replace(/\*/g, '')
            //change +- to -
            str = str.replace(/\+\-/g, '\-')
            //remove a(n)= or equivalent
            str = str.replace(/[a-z]\(n\)\=/g, '')
            return str === subString
        }

        /***
         * check if valToMatch is the only number in response
         * @param response
         * @param valToMatch
         * @returns {boolean}
         */
        function onlyNumberMatch(response, valToMatch) {
            var matched = extractNumbers(response);
            return (matched.length === 1) && (matched.includes(valToMatch))
        }

        // wrapper function
        function _e(eval_str, contextId = '', grade = 'wrong') {
            // this is a hack
            // else does not know what context id is
            if (contextId != '')
                self.currContext['contextId'] = contextId

            bool_res = eval(eval_str)
            if (bool_res)
                self.currContext['gradeStr'] = grade
            return bool_res
        }

        function expressionMatch(response, expToMatch) {
            // math is the global variable defined in math.js
            response = response.split('=');
            response = response[response.length - 1];

            var str = response + ' ' + expToMatch;
            var scope = {};

            var var_in_exp = str.match(/[A-Za-z]+/g);

            for (var i = 0; i < var_in_exp.length; i++) {
                var v = var_in_exp[i];
                scope[v] = Math.random()
            }
            return math.eval(response, scope) === math.eval(expToMatch, scope)
        }

        /***
         * extract numbers from the response
         * @param response
         */
        function extractNumbers(response) {
            var numbersExtracted = response.match(/[+\-]?\d+(,\d+)?(\.\d+)?/);
            var filteredNumbersExtracted = [];
            //if anything is extracted
            if (numbersExtracted) {
                for (var i = 0; i < numbersExtracted.length; i++) {
                    if (numbersExtracted[i]) {
                        filteredNumbersExtracted.push(
                            Number(numbersExtracted[i].replace(',', '')))
                    }
                }
            }
            return filteredNumbersExtracted
        }

        /***
         * ======END OF HELPER MATCHING FUNCTIONS=====
         */

        //convert all string to lower case for answer matching
        //sanitize text for search function
        // noinspection JSUnusedAssignment
        if (response) {
            response = response.toLowerCase()
            //do not strip
            // .replace(/[\s.,\/#!$%\^&\*;:{}=\-_'"`~()]/g, "");
        }
        console.log('user response', response);
        if (!current.hasOwnProperty('random')) {
            var found = false;
            var otherwise = false;
            var branchLength = current.branch.length;
            for (var k = 0; k < branchLength; k++) {
                var b = current.branch[k];
                var next = b.next;
                var match = true;
                if (b.hasOwnProperty('evals')) {
                    var evalsLength = b.evals.length;
                    for (var i = 0; i < evalsLength; i++) {
                        var e = b.evals[i];
                        if (!eval(e)) {
                            match = false
                        }
                    }
                    if (match && evalsLength > 0) {
                        found = next;
                        return {
                            'next': found,
                            'nextProp': b['nextProp']
                        }
                    }
                } else {
                    otherwise = next
                }
            }
            if (otherwise) {
                self.currContext['gradeStr'] = 'wrong'
                return {
                    'next': otherwise,
                    'nextProp': b['nextProp']
                }

            } else {
                //handle unmatched response here
                console.error('A response is not caught!');
                return null
            }
        }
    }
}

/***
 * Class Bubbles is responsible for rendering the conversation and handle front-end interaction
 * Bubbles contains a MathbotFSM instance, which responsible for handling the back-end finite state machine
 * @param container
 * @param name
 * @param options
 * @constructor
 */
function Bubbles(container, name, options) {
    /**********************************************************************************************************
     Init.
     **********************************************************************************************************/
    var lastSay = '';
    var giveMeBubbles = this;
    var MQ = MathQuill.getInterface(2); // this is a math expression render, we might want to use it later
    // options
    options = typeof options !== 'undefined' ? options : {};
    var animationTime = options.animationTime || 0;			// how long it takes to animate chat bubble, also set in CSS
    var typeSpeed = options.typeSpeed || 0;				// delay per character, to simulate the machine "typing"
    var widerBy = options.widerBy || 2;				// add a little extra width to bubbles to make sure they don't break
    var sidePadding = options.sidePadding || 6; 				// padding on both sides of chat bubbles
    var randomDict = options.randomDict;
    var mathbotProgressCheckpoints = options.mathbotProgressCheckpoints;
    var standingAnswer = 'ice'; // remember where to restart convo if interrupted
    var _convo = {};		// local memory for conversation JSON object
    var loggedConversation = [];
    var proposeBubble = false;
    var bubbleQueue = false;
    var proposal = null;
    var botSayingLock = true;
    //--> NOTE that this object is only assigned once, per session and does not change for this

    // set up DOMs
    var current_base_url = window.location.protocol + '//' +
        window.location.hostname + ':' + window.location.port;

    container.classList.add('bubble-container');
    container.setAttribute('ss-container', true);
    // add mathbot progress bar
    var mathbotProgress = document.createElement('div');
    mathbotProgress.id = 'mathbot-progress-container';
    var mathbotProgressBar = document.createElement('div');
    mathbotProgressBar.id = 'mathbot-progress-bar';
    mathbotProgress.appendChild(mathbotProgressBar);
    container.appendChild(mathbotProgress);

    var speedSliderContainer = $("<div></div>").attr('id', 'speed-slider-container')
        .append("<span>-</span>")
        .append("<input id='speed-slider' type='range' min='25' max='75' value=" + (100 - typeSpeed) + ">")
        .append("<span>+</span>");
    $(container).append(speedSliderContainer);
    var speedSlider = $("#speed-slider");
    speedSlider.change(function() {
        typeSpeed = 100 - $(this).val();
		giveMeBubbles.mathbotFsm["type_speed"] = typeSpeed
		console.log(giveMeBubbles.mathbotFsm["type_speed"])
    });

    // add bubble wrap
    var bubbleWrap = document.createElement('div');
    bubbleWrap.className = 'bubble-wrap';

    // init typing bubble
    var bubbleTyping = document.createElement('div');
    bubbleTyping.className = 'bubble-typing imagine';
    for (dots = 0; dots < 3; dots++) {
        var dot = document.createElement('div');
        dot.className = 'dot_' + dots + ' dot';
        bubbleTyping.appendChild(dot)
    }
    bubbleWrap.appendChild(bubbleTyping);

    // init text area
    var inputWrap = document.createElement('div');
    inputWrap.className = 'input-wrap';
    var inputText = document.createElement('textarea');
    inputText.setAttribute('placeholder', 'Type your reply here...');
    inputText.setAttribute('id', 'answer');
    inputWrap.appendChild(inputText);

    container.appendChild(bubbleWrap);
    container.appendChild(inputWrap);


    // before the page is closed
    window.onbeforeunload = function () {
        console.log('Logged conversation to the server!');
        //upload to conversation
        $.ajax({
            type: 'POST',
            async: false,
            url: '/api/record',
            data: {'loggedConversation': loggedConversation.join('\n')},
            success: null,
            dataType: 'json',
        })
    };

    /**********************************************************************************************************
     Graph logic
     **********************************************************************************************************/
    this.startConversation = function (convJson, startNode) {
        console.log('start from', startNode);
        giveMeBubbles.mathbotFsm = new MathbotFSM(convJson, randomDict,
            startNode, mathbotProgressCheckpoints);
        var says = giveMeBubbles.mathbotFsm.keepSayingUntilNextResponseRequired();
        orderBubbles(says, function () {
            botSayingLock = false
        })
    };

    /**********************************************************************************************************
     Help function
     **********************************************************************************************************/
    function insertAfter(newElement, targetElement) {
        var parent = targetElement.parentNode;
        if (parent.lastChild === targetElement) {
            parent.appendChild(newElement)
        }
        else {
            parent.insertBefore(newElement, targetElement.nextSibling)
        }
    }

    /**********************************************************************************************************
     record conversation
     **********************************************************************************************************/
    var recordConversation = function (speaker, say, nodeId) {
        var say_log = speaker + ': ' + say;
        var datetime_log = new Date().toISOString().replace('T', ' ').replace(/\..*$/, '');
        loggedConversation.push('[' + datetime_log + '][' + nodeId + '] ' +
            say_log)
    };

    /**********************************************************************************************************
     User input matching
     **********************************************************************************************************/

        //check user input
    var check = function (o) {
            recordConversation('Student', o.input,
                giveMeBubbles.mathbotFsm.getCurrNodeId());

            var says = giveMeBubbles.mathbotFsm.keepSayingUntilNextResponseRequired(
                o.input);
            orderBubbles(says, function () {
                botSayingLock = false
            })
        };

    var answer = $('textarea#answer');
    var flag = 1;
    var oldText = answer.val();
    answer.on('keyup', function (e) { // register user input
        if (botSayingLock) {
            console.log('User input area locked.');
            return;
        }

        var key = e.keyCode ? e.keyCode : e.which;
        var newText = answer.val();

        if (flag) {
            oldText = newText;
            propose(oldText);
            flag = 0
        }
		//13 is the enter key
        if (key === 13) {
            // if only space, prevent submitting
            if (oldText.trim() === "") {
                answer.val(answer.val().slice(0, -1));
                console.log('Empty response detected.');
                return;
            }
            if (botSayingLock) {
                console.log('User input area locked.');
                answer.val(answer.val().slice(0, -1));
                return;
            }
            e.preventDefault();
            botSayingLock = true;
            typeof bubbleQueue !== false ? clearTimeout(bubbleQueue) : false; // allow user to interrupt the bot
            var lastBubble = document.querySelectorAll('.bubble.say');
            lastBubble = lastBubble[lastBubble.length - 1];
            lastBubble.classList.contains('reply') &&
            !lastBubble.classList.contains('reply-freeform')
                ? lastBubble.classList.add('bubble-hidden')
                : false;
            confirm();
            flag = 1;

            // callback
            check({
                'input': oldText,
                'convo': _convo,
                'standingAnswer': standingAnswer,
            });
            var input = '';
            answer.val(input)
        } else {
            if (newText !== oldText) {
                oldText = newText;
                propose(oldText)
            }
        }
    });

    /**********************************************************************************************************
     Below are renders
     **********************************************************************************************************/

    /***
     * Scroll the conversation panel to the end
     */
    var scrollDown = function () {
        var scrollDifference = bubbleWrap.scrollHeight - bubbleWrap.scrollTop;
        var scrollHop = scrollDifference / 200;
        for (var i = 1; i <= scrollDifference / scrollHop; i++) {
            setTimeout(function () {
                bubbleWrap.scrollTop += scrollHop
            }, (i * 5))
        }
    };

    /***
     * Preview a reply
     * @param say: user's reply
     */
    var propose = function (say) {
        var bubbleTextList = document.getElementsByClassName(
            'bubble-button bubble say');

        var bubble;
        var bubbleContent;
        var bubbleText;

        if (bubbleTextList.length) {
            bubbleText = bubbleTextList[0];
            bubbleText.innerHTML = say
        }
        else {
            bubble = document.createElement('div');
            bubbleContent = document.createElement('span');
            bubbleText = document.createElement('span');

            bubble.className = 'bubble reply reply-freeform say';
            bubbleContent.className = 'bubble-content';
            bubbleText.className = 'bubble-button bubble say';

            bubbleText.innerHTML = say;
            bubbleContent.appendChild(bubbleText);
            bubble.appendChild(bubbleContent);
            if (!proposeBubble) {
                bubble.classList.add('bubble-hidden')
            }
            proposal = bubble;
            bubbleWrap.insertBefore(bubble, bubbleTyping)
        }
        scrollDown()
    };

    /***
     * Confirm a reply
     *
     */
    var confirm = function () {
        if (!proposeBubble) {
            var bubbleList = document.getElementsByClassName(
                'bubble reply reply-freeform say bubble-hidden');
            bubbleList[0].classList.remove('bubble-hidden')
        }

        var bubbleTextList = document.getElementsByClassName(
            'bubble-button bubble say');

        if (bubbleTextList.length) {
            var bubbleText = bubbleTextList[0];
            bubbleText.className = 'bubble-button bubble-pick';
            proposal = null
        }
    };

    /***
     * [Not used] api for typing bubble
     */
    var think = function () {
        bubbleTyping.classList.remove('imagine');
        this.stop = function () {
            bubbleTyping.classList.add('imagine')
        }
    };
    /***
     * Add bubbles to the conversation panel
     * @param q: queue of bubbles
     * @param callback: callback function
     */
    var orderBubbles = function (q, callback) {
        var start = function () {
            setTimeout(function () {
                if (typeof callback === 'function') {
                    callback()

                    //response time
                    console.log('beginResponseTime logged');
                    bubble["mathbotFsm"].beginResponseTime = (new Date()).getTime();
                }
            }, animationTime)
        };

        var position = 0;
        for (var nextCallback = position + q.length - 1; nextCallback >=
        position; nextCallback--) {
            (function (callback, index) {
                if (nextCallback == position) {
                    // fix the first reply time after user response
                    start = function () {
                        addBubble(q[index], callback, "", null, 1000)
                    }
                } else {
                    start = function () {
                        addBubble(q[index], callback, "", null, null)
                    }
                }
            })(start, nextCallback)
        }
        start();

        //update the mathbot progress bar
        mathbotProgressBar.style.width = (giveMeBubbles.mathbotFsm.getProgress() *
            100) + '%'
    };


    /***
     * Add a single bubble to the conversation panel
     * @param say
     * @param posted
     * @param style
     * @param delay
     */
    var addBubble = function (say, posted, style, delay, forceWait) {
        delay = animationTime;
        //delay = delay || animationTime;			// how long it takes to animate chat bubble, also set in CSS

        style = typeof style !== 'undefined' ? style : '';
        // create bubble element
        var bubble = document.createElement('div');
        var bubbleContent = document.createElement('span');
        bubble.className = 'bubble imagine ' + style;
        bubbleContent.className = 'bubble-content';
        bubbleContent.innerHTML = say;
        bubble.appendChild(bubbleContent);
        if (proposal !== null) {
            bubbleWrap.insertBefore(bubble, proposal)
        } else {
            bubbleWrap.insertBefore(bubble, bubbleTyping)
        }

        // answer picker styles
        if (style !== '') {
            var bubbleButtons = bubbleContent.querySelectorAll(
                '.bubble-button');

            for (var z = 0; z < bubbleButtons.length; z++) {
                (function (el) {
                    if (!el.parentNode.parentNode.classList.contains(
                        'reply-freeform'))
                        el.style.width = el.offsetWidth - sidePadding * 2 +
                            widerBy + 'px'
                })(bubbleButtons[z])
            }
            bubble.addEventListener('click', function () {
                for (var i = 0; i < bubbleButtons.length; i++) {
                    (function (el) {
                        el.style.width = 0 + 'px';
                        el.classList.contains('bubble-pick')
                            ? el.style.width = ''
                            : false;
                        el.removeAttribute('onclick')
                    })(bubbleButtons[i])
                }
                this.classList.add('bubble-picked')
            })
        }

        scrollDown();
        // time, size & animate
        var wait = delay * 2;
        var minTypingWait = delay * 6;
        var DEBUG = 0;

        if (Math.max(lastSay.length, 50) * typeSpeed > delay && style === '') {
            // slow down equation typing speed
            var res = lastSay.split('<span>&#8203;</span>');
            if (res.length % 2 === 1) {
                var lengths = res.map(x => x.length);
                for (var i = 0; i < res.length; i++) {
                    switch (i % 2) {
                        case 1:
                            wait += lengths[i] * 3 * typeSpeed;
                        case 0:
                            wait += lengths[i] * typeSpeed
                    }
                }
            } else {
                wait += typeSpeed * Math.max(lastSay.length, 50);
                console.log('Make sure equations are closed correctly!')
            }

            wait < minTypingWait ? wait = minTypingWait : false;

            if (DEBUG) {
                wait = 0
                delay = 0
            }

            setTimeout(function () {
                bubbleTyping.classList.remove('imagine')
            }, delay)
        }

        wait = forceWait || wait;

        setTimeout(function () {
            bubbleTyping.classList.add('imagine')
        }, wait - delay * 2);

        bubbleQueue = setTimeout(function () {
            bubble.classList.remove('imagine');
            var bubbleWidthCalc = bubbleContent.offsetWidth + widerBy + 'px';
            bubble.style.width = style === '' ? bubbleWidthCalc : '';
            bubble.style.width = say.includes('<img src=')
                ? '50%'
                : bubble.style.width;
            bubble.classList.add('say');
            if (posted) {
                posted()
            }
            setTimeout(scrollDown, delay / 2)
        }, wait + delay * 2);

        recordConversation('MathBot', say,
            giveMeBubbles.mathbotFsm.getCurrNodeId());
        lastSay = say
    }

}
