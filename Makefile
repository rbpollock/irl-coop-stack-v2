.PHONY: test journeys

# Journey-based E2E suite — SSO, groups/RLS, membership, NocoDB read+write,
# anonymous isolation. Credentials are derived in-memory from master.key.
test: journeys

journeys:
	bash infra/scripts/journeys.sh
