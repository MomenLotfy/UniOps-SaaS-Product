# Root configuration linking all phases
# This root module orchestrates the deployment of the UniOps SaaS Infrastructure.

module "networking" {
  source = "./phase-01-networking"

  project_name = local.name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
  tags         = local.common_tags
}

module "eks" {
  source = "./phase-02-eks"

  project_name    = local.name
  environment     = var.environment
  cluster_version = var.cluster_version
  vpc_id          = module.networking.vpc_id
  private_subnets = module.networking.private_subnet_ids
  tags            = local.common_tags
}

module "data" {
  source = "./phase-03-data"

  project_name    = local.name
  environment     = var.environment
  vpc_id          = module.networking.vpc_id
  vpc_cidr        = module.networking.vpc_cidr
  private_subnets = module.networking.private_subnet_ids
  eks_nodes_sg_id = module.eks.node_security_group_id
  kms_key_arn     = module.security.kms_key_arn
  tags            = local.common_tags
}

module "tools" {
  source = "./phase-04-tools"

  project_name    = local.name
  environment     = var.environment
  vpc_id          = module.networking.vpc_id
  vpc_cidr        = module.networking.vpc_cidr
  public_subnets  = module.networking.public_subnet_ids
  private_subnets = module.networking.private_subnet_ids
  bastion_sg_id   = module.networking.bastion_sg_id
  tags            = local.common_tags
}

module "security" {
  source = "./phase-05-security"

  project_name     = local.name
  environment      = var.environment
  vpc_id           = module.networking.vpc_id
  alb_arn          = module.tools.alb_arn
  eks_cluster_name = module.eks.cluster_name
  rds_instance_id  = module.data.rds_instance_id
  rds_instance_arn = module.data.rds_instance_arn
  efs_id           = module.data.efs_id
  efs_arn          = module.data.efs_arn
  tags             = local.common_tags
}

output "cluster_name" { value = module.eks.cluster_name }
output "region"       { value = var.aws_region }
output "rds_endpoint" { value = module.data.rds_endpoint }
output "rds_username" { value = module.data.rds_username }
output "rds_password" {
  value     = module.data.db_password
  sensitive = true
}
output "rds_db_name"  { value = module.data.db_name }
output "redis_endpoint" { value = module.data.redis_endpoint }
output "redis_auth_token" {
  value     = module.data.redis_auth_token
  sensitive = true
}
output "efs_id"       { value = module.data.efs_id }
