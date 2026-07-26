# Infrastructure Deployment Guide

## Topology
- **server1** (`identity-data`): Authentication, Authorization, Compliance, Finance, Storage, Communication.
- **server2** (`workflow-ops`): Workflow, Lifecycle.

## Pillar-Tool Mapping
| Pillar | Tools |
|---|---|
| Authentication | Keycloak (Stubs) |
| Authorization | Custom (Reserved) |
| Compliance | Postgres/Citus/Temporal Logs |
| Finance | Firefly III |
| Storage | Postgres/Citus, Redis, MinIO, NocoDB, CryptPad |
| Communication | Stalwart, Matrix, Jitsi, Element, Cal.com, FusionPBX/Asterisk |
| Workflow | Temporal, OpenProject, Formbricks, Postiz, Webstudio |
| Lifecycle | Hi.Events |

## Deployment
1. Update `infra/ansible/inventory/hosts.yml` with real host IPs.
2. Ensure you have SSH key access to both hosts.
3. Run bootstrap: `ansible-playbook -i infra/ansible/inventory/hosts.yml infra/ansible/playbooks/bootstrap.yml`
4. Run deploy: `./infra/scripts/deploy.sh`
