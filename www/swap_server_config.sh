#!/usr/bin/env bash

mv server_config.json tmp && mv server_config.json.other server_config.json && mv tmp server_config.json.other
echo "Current Server Config:"
cat server_config.json