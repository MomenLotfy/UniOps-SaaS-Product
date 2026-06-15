# UniOps Terraform Bootstrap Layer

This layer manages **only the persistent / shared resources** that the
application Terraform layer depends on:

- S3 state bucket
- DynamoDB lock table
- ECR repositories for the application's container images
- (optionally) IAM roles for Terraform execution

The state for this layer is **isolated** from the application layer:

| Property        | Bootstrap                                | Application (not in this dir)         |
|-----------------|------------------------------------------|---------------------------------------|
| State key       | `bootstrap/terraform.tfstate`            | `prod/terraform.tfstate`              |
| State bucket    | `uniops-terraform-state` (us-east-2)     | same bucket, different key            |
| Lock table      | `uniops-terraform-locks`                 | same lock table, key-level separation |

The application layer is **not** managed by anything in this directory. It
lives under `infrastructure/terraform/` and uses the same backend
configurations that the bootstrap layer provisions.

## Layout

```
terraform/bootstrap/
├── README.md         # this file
├── backend.tf        # S3 + DynamoDB backend config for THIS layer's state
├── provider.tf       # AWS provider pinned to us-east-2
├── s3.tf             # state bucket + versioning + encryption
├── dynamodb.tf       # lock table
├── ecr.tf            # ECR repos for backend + frontend
├── iam.tf            # bootstrap IAM resources (none currently exist)
├── variables.tf      # input variables
└── outputs.tf        # ARNs / names consumed by the app layer
```

## Initialisation

```bash
cd terraform/bootstrap
terraform init
```

This connects to the S3 bucket `uniops-terraform-state` and DynamoDB
`uniops-terraform-locks` in `us-east-2` and reads/writes the
`bootstrap/terraform.tfstate` key.

## Importing existing resources

Existing AWS resources are imported (not recreated) using their live IDs:

```bash
terraform import aws_s3_bucket.terraform_state                  uniops-terraform-state
terraform import aws_s3_bucket_versioning.terraform_state      uniops-terraform-state
terraform import aws_s3_bucket_server_side_encryption_configuration.terraform_state uniops-terraform-state
terraform import aws_s3_bucket_public_access_block.terraform_state uniops-terraform-state
terraform import aws_dynamodb_table.terraform_locks             uniops-terraform-locks
terraform import aws_ecr_repository.backend                     uniops-backend
terraform import aws_ecr_repository.frontend                    uniops-frontend
```

After import, `terraform plan` must show **0 changes** (drift-free).

## Drift policy

This layer must never apply a change that touches production:

- ECR repos in active use by running pods are imported with their **current**
  configuration (image-tag-mutability, scan-on-push). Tightening these
  requires a separate plan and explicit approval.
- The S3 state bucket and DynamoDB lock table have
  `lifecycle { prevent_destroy = true }`.

## Rollback

To destroy this layer (and only this layer):

```bash
cd terraform/bootstrap
terraform destroy
```

The `prevent_destroy` flags on the state bucket and lock table will block
destruction. To override (DANGEROUS), remove the flag from `s3.tf` /
`dynamodb.tf` first.
