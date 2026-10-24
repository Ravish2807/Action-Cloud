variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "project_name" {
  type    = string
  default = "actioncloud"
}
variable "environment" {
  type    = string
  default = "production"
}
variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}
variable "kubernetes_version" {
  type    = string
  default = "1.36"
}
variable "database_instance_class" {
  type    = string
  default = "db.t4g.medium"
}
variable "database_storage_gb" {
  type    = number
  default = 50
}
variable "database_backup_retention_days" {
  type    = number
  default = 7
}
variable "database_multi_az" {
  type    = bool
  default = true
}
variable "node_instance_types" {
  type    = list(string)
  default = ["m7i.large"]
}
variable "node_group_name_suffix" {
  type    = string
  default = "workers"
}
variable "node_min_size" {
  type    = number
  default = 2
}
variable "node_desired_size" {
  type    = number
  default = 2
}
variable "node_max_size" {
  type    = number
  default = 6
}
variable "cluster_public_access_cidrs" {
  description = "CIDRs allowed to reach the EKS public API endpoint. Set to a trusted deployment network; the default is closed."
  type        = list(string)
  default     = ["127.0.0.1/32"]
}
variable "github_repository" {
  description = "GitHub repository in OWNER/NAME form. Leave empty to omit the GitHub OIDC deploy role."
  type        = string
  default     = ""
}
variable "github_deploy_environment" {
  type    = string
  default = "production"
}
variable "api_hostname" {
  description = "Optional public API hostname. Requires route53_zone_id to request a TLS certificate."
  type        = string
  default     = ""
}
variable "route53_zone_id" {
  type    = string
  default = ""
}
