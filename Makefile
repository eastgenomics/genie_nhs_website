# NHS GENIE Infrastructure Makefile
#
# Usage:
#   make uat-up                                          Spin up UAT instance
#   make update-data ENV=uat VCF=s3://... CSV=s3://... VER=v19   Load data
#   make verify-db ENV=uat                               Check DB row counts
#   make acceptance-test                                 Run automated tests
#   make acceptance-checklist                            Print manual checklist
#   make uat-down                                        Tear down UAT
#   make deploy ENV=prod                                 Deploy latest code
#   make ssl                                             Run certbot on prod

SHELL := /bin/bash
.DEFAULT_GOAL := help

ENV           ?= prod
VCF           ?=
CSV           ?=
VER           ?=
PROD_URL      ?=
SCHEME        ?= https
CERTBOT_EMAIL ?=

TF_DIR  := terraform
SSH_USER := ubuntu

# Read a Terraform output without mutating .terraform/environment
define tf_output
$(shell cd $(TF_DIR) && TF_WORKSPACE=$(1) terraform output -raw $(2) 2>/dev/null)
endef

# ── Terraform ────────────────────────────────────────────────────────────────

.PHONY: tf-init tf-plan tf-apply tf-destroy

tf-init: ## Initialise Terraform
	terraform -chdir=$(TF_DIR) init

tf-plan: ## Plan changes for ENV (default: prod)
	cd $(TF_DIR) && terraform workspace select $(ENV) && terraform plan

tf-apply: ## Apply changes for ENV (default: prod)
	cd $(TF_DIR) && terraform workspace select $(ENV) && terraform apply

tf-destroy: ## Destroy resources for ENV (default: prod)
	cd $(TF_DIR) && terraform workspace select $(ENV) && terraform destroy

# ── UAT lifecycle ────────────────────────────────────────────────────────────

.PHONY: uat-up uat-down

uat-up: ## Provision the UAT instance
	cd $(TF_DIR) && \
		(terraform workspace select uat 2>/dev/null || terraform workspace new uat) && \
		terraform apply

uat-down: ## Destroy UAT instance (guarded — only works for ENV=uat)
	@if [ "$(ENV)" != "uat" ]; then \
		echo "ERROR: uat-down requires ENV=uat (got '$(ENV)')"; exit 1; \
	fi
	cd $(TF_DIR) && terraform workspace select uat && terraform destroy

# ── Deployment ───────────────────────────────────────────────────────────────

.PHONY: deploy

deploy: ## Deploy latest code to ENV instance
	$(eval IP := $(call tf_output,$(ENV),public_ip))
	@if [ -z "$(IP)" ]; then echo "ERROR: could not resolve IP for $(ENV)"; exit 1; fi
	bash scripts/deploy.sh $(IP)

# ── Data update ──────────────────────────────────────────────────────────────

.PHONY: update-data

update-data: ## Update GENIE data on ENV instance (requires VCF, CSV, VER)
	@if [ -z "$(VCF)" ]; then echo "ERROR: VCF= required (S3 URI)"; exit 1; fi
	@if [ -z "$(CSV)" ]; then echo "ERROR: CSV= required (S3 URI)"; exit 1; fi
	@if [ -z "$(VER)" ]; then echo "ERROR: VER= required (e.g. v19)"; exit 1; fi
	$(eval IP := $(call tf_output,$(ENV),public_ip))
	@if [ -z "$(IP)" ]; then echo "ERROR: could not resolve IP for $(ENV)"; exit 1; fi
	bash scripts/update_data.sh --host $(IP) --vcf $(VCF) --csv $(CSV) --version $(VER)

# ── Verification ─────────────────────────────────────────────────────────────

.PHONY: verify-db acceptance-test acceptance-test-known-values acceptance-checklist

verify-db: ## Check DB row counts on ENV instance
	$(eval IP := $(call tf_output,$(ENV),public_ip))
	@if [ -z "$(IP)" ]; then echo "ERROR: could not resolve IP for $(ENV)"; exit 1; fi
	@echo "Checking database on $(SSH_USER)@$(IP)..."
	@ssh $(SSH_USER)@$(IP) 'cd /home/ubuntu/genie_nhs_website && \
		docker compose exec -T web python manage.py shell -c \
		"from main.models import Variant, CancerType; \
		 print(\"variants:\", Variant.objects.count()); \
		 print(\"cancer_types:\", CancerType.objects.count())"'

acceptance-test: ## Run automated acceptance tests (UAT + optional parity vs prod)
	$(eval UAT_FQDN := $(call tf_output,uat,fqdn))
	@if [ -z "$(UAT_FQDN)" ]; then echo "ERROR: could not resolve UAT FQDN"; exit 1; fi
	python3 scripts/acceptance_test.py \
		--uat-url $(SCHEME)://$(UAT_FQDN) \
		$(if $(strip $(PROD_URL)),--prod-url $(PROD_URL),)

acceptance-test-known-values: ## Run known-value tests only against ENV
	$(eval FQDN := $(call tf_output,$(ENV),fqdn))
	@if [ -z "$(FQDN)" ]; then echo "ERROR: could not resolve FQDN for $(ENV)"; exit 1; fi
	python3 scripts/acceptance_test.py \
		--uat-url $(SCHEME)://$(FQDN) \
		--mode known-values

acceptance-checklist: ## Print manual acceptance checklist with UAT URL
	$(eval UAT_FQDN := $(call tf_output,uat,fqdn))
	@if [ -z "$(UAT_FQDN)" ]; then echo "ERROR: could not resolve UAT FQDN"; exit 1; fi
	@sed -e "s|__UAT_URL__|$(SCHEME)://$(UAT_FQDN)|g" \
		-e "s|__PROD_URL__|$(if $(strip $(PROD_URL)),$(PROD_URL),https://genie.genomics-resources.uk)|g" \
		scripts/acceptance_checklist.md

# ── SSL ──────────────────────────────────────────────────────────────────────

.PHONY: ssl

ssl: ## Run certbot on ENV instance (post-provisioning, after DNS propagation)
	$(eval IP := $(call tf_output,$(ENV),public_ip))
	@if [ -z "$(IP)" ]; then echo "ERROR: could not resolve IP for $(ENV)"; exit 1; fi
	$(eval FQDN := $(call tf_output,$(ENV),fqdn))
	@echo "Running certbot for $(FQDN) on $(IP)..."
	@if [ -n "$(CERTBOT_EMAIL)" ]; then \
		ssh $(SSH_USER)@$(IP) "sudo certbot --nginx -d $(FQDN) --non-interactive --agree-tos --email $(CERTBOT_EMAIL)"; \
	else \
		ssh $(SSH_USER)@$(IP) "sudo certbot --nginx -d $(FQDN) --non-interactive --agree-tos --register-unsafely-without-email"; \
	fi

# ── Help ─────────────────────────────────────────────────────────────────────

.PHONY: help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}'
