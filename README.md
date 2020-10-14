# Mathbot [![Build Status](https://travis-ci.com/stanford-policylab/mathbot.svg?token=ExpCLt6UBYajQ6vSnGpy&branch=master)](https://travis-ci.com/stanford-policylab/mathbot)
This repo is for the [Mathbot](https://mathbot.stanford.edu) interactive UI and the content. 

## Repo structure 
``` 
 . 
 ├-- content/                            # content files that compilers can ingest
 ├-- test/                               # unit tests
 ├-- www/                                # all frontend files
 |   ├-- static/ 
 |   |      └-- resources/js/mathbot.js  # mathbot FSM logic  
 |   └-- templates/
 ├-- run.sh                              # start the mathbot server
 └-- README.md 
``` 

## How to run?
```
pip install -r requirements.txt
sh run.sh 
```
