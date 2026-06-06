terraform {
  backend "s3" {
    bucket         = "uniops-terraform-state"
    key            = "app/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "uniops-terraform-locks"
    encrypt        = true
  }
}
