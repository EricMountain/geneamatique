SHELL := /usr/bin/env bash

.PHONY: build_pwa terraform-init terraform-plan terraform-apply terraform-destroy fmt deploy package bootstrap

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

# Convenience bootstrap
bootstrap: build_pwa terraform-init
	@echo "Bootstrap complete. You can now run 'make terraform-apply'."

package: build_pwa
	@echo "Package created in lambda/dist (ready for Terraform packaging)."
