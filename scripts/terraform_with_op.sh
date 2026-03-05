#!/usr/bin/env bash
# Helper for running terraform in terraform/aws while sourcing the
# Google OAuth client secret from 1Password via the `op` CLI.
#
# Usage: ./scripts/terraform_with_op.sh apply    # same arguments as `terraform`
#        ./scripts/terraform_with_op.sh plan -var='foo=bar'
#
# Requirements:
#   * 1Password CLI (`op`) must be installed and you must be signed in:
#       eval "$(op signin)"
#   * The item name must be exactly "Google OAuth - enry/genealogy" and
#     it must have a field called "client_secret".
#
# The script reads the secret, exports it as TF_VAR_google_client_secret
# (Terraform will pick it up automatically), then `cd` into the aws
# subdirectory and invokes terraform with whatever arguments you pass.

set -euo pipefail

item="Google OAuth - xxxx/genealogy"
field="client_secret"

# If the CLI is not logged in this will prompt you; that's fine.

secret=$(op item get "$item" --fields "$field" --format=json | jq -r '.value' || true)
if [[ -z "$secret" ]]; then
    echo "error: could not read $field from $item in 1Password" >&2
    exit 1
fi

export TF_VAR_google_client_secret="$secret"

# run terraform in the appropriate directory
(cd terraform/aws && terraform "$@")
