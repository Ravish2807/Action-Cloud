output "aws_region" { value = var.aws_region }
output "cluster_name" { value = aws_eks_cluster.main.name }
output "cluster_endpoint" { value = aws_eks_cluster.main.endpoint }
output "ecr_repository_url" { value = aws_ecr_repository.app.repository_url }
output "queue_name" { value = aws_sqs_queue.experiences.name }
output "queue_url" { value = aws_sqs_queue.experiences.url }
output "database_endpoint" { value = aws_db_instance.main.address }
output "database_secret_arn" { value = aws_db_instance.main.master_user_secret[0].secret_arn }
output "application_secret_arn" { value = aws_secretsmanager_secret.application.arn }
output "runtime_role_arn" { value = aws_iam_role.app.arn }
output "migration_role_arn" { value = aws_iam_role.migration.arn }
output "load_balancer_controller_role_arn" { value = aws_iam_role.load_balancer_controller.arn }
output "cluster_autoscaler_role_arn" { value = aws_iam_role.cluster_autoscaler.arn }
output "github_deploy_role_arn" { value = try(aws_iam_role.github_deploy[0].arn, null) }
output "api_certificate_arn" { value = try(aws_acm_certificate_validation.api[0].certificate_arn, null) }
output "route53_zone_id" { value = var.route53_zone_id == "" ? null : var.route53_zone_id }
