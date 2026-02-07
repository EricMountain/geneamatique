SHELL := /usr/bin/env bash

.PHONY: build_pwa terraform-init terraform-plan terraform-apply terraform-destroy fmt deploy package bootstrap npm-audit

# Build the PWA and install lambda runtime deps
build_pwa:
	@echo "Building PWA into lambda/dist and installing lambda deps..."
	@./build_pwa.sh

terraform-init:
	@echo "Initializing Terraform (terraform/aws)..."
	@terraform -chdir=terraform/aws init

terraform-plan: terraform-init
	@echo "Planning Terraform (terraform/aws)..."
	@terraform -chdir=terraform/aws plan -out=terraform/aws/tfplan

terraform-apply: terraform-init
	@echo "Applying Terraform (terraform/aws)..."
	@terraform -chdir=terraform/aws apply -auto-approve

terraform-destroy: terraform-init
	@echo "Destroying Terraform-managed infrastructure (terraform/aws)..."
	@terraform -chdir=terraform/aws destroy -auto-approve

fmt:
	@echo "Running terraform fmt (terraform/aws)..."
	@terraform -chdir=terraform/aws fmt

# Deploy: build site, then deploy infra
deploy: build_pwa terraform-apply
	@echo "Deploy complete. Use the Terraform output 'function_url' to access the site. Ensure you have created an API key in DynamoDB."

# Run frontend + backend locally for development (backend auth disabled in local mode)
dev_local: build_pwa
	@echo "Starting local backend (lambda) and frontend (src)..."
	@./scripts/dev_local.sh

# Convenience bootstrap
bootstrap: build_pwa terraform-init
	@echo "Bootstrap complete. You can now run 'make terraform-apply'."

package: build_pwa
	@echo "Package created in lambda/dist (ready for Terraform packaging)."

# Run npm audit fix in JS packages (src, lambda).
# Set FORCE=true when running the make target to allow --force fixes (may update major versions).
npm-audit:
	@echo "Running npm audit fix in src and lambda..."
	@for d in src lambda; do \
	  if [ -f $$d/package.json ]; then \
	    echo "=== $$d ==="; \
	    (cd $$d && npm install --silent) || true; \
	    (cd $$d && npm audit fix --silent) || true; \
	    if [ "$(FORCE)" = "true" ]; then \
	      echo "(running npm audit fix --force)"; \
	      (cd $$d && npm audit fix --force --silent) || true; \
	    fi; \
	  fi; \
	done
	@echo "npm audit completed. Re-run with 'make npm-audit FORCE=true' to apply forceful fixes."
