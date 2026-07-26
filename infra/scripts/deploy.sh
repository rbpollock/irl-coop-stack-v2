#!/bin/bash
# Usage: ./deploy.sh
ansible-playbook -i ../ansible/inventory/hosts.yml ../ansible/playbooks/deploy.yml
