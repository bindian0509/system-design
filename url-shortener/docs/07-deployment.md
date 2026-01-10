# AWS Deployment and Infrastructure

This document covers the AWS infrastructure, deployment strategies, and Infrastructure as Code (IaC) for the URL shortener system.

---

## Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          AWS INFRASTRUCTURE                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Global Services                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │  Route 53          CloudFront         WAF              Shield Advanced     ││
│  │  (DNS)             (CDN)              (Firewall)       (DDoS)              ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  US-EAST-1 (Primary)          EU-WEST-1              AP-SOUTH-1                 │
│  ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐         │
│  │ VPC               │   │ VPC               │   │ VPC               │         │
│  │ ├─ ALB            │   │ ├─ ALB            │   │ ├─ ALB            │         │
│  │ ├─ EKS Cluster    │   │ ├─ EKS Cluster    │   │ ├─ EKS Cluster    │         │
│  │ ├─ ElastiCache    │   │ ├─ ElastiCache    │   │ ├─ ElastiCache    │         │
│  │ └─ NAT Gateway    │   │ └─ NAT Gateway    │   │ └─ NAT Gateway    │         │
│  └───────────────────┘   └───────────────────┘   └───────────────────┘         │
│                                                                                  │
│  Global Data Layer                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │  DynamoDB Global Tables    Kinesis      Timestream      S3                 ││
│  │  (URLs, Users)             (Events)     (Analytics)     (Audit Logs)       ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
│  Management & Observability                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │  CloudWatch        X-Ray           Secrets Manager     KMS                 ││
│  │  (Logs/Metrics)    (Tracing)       (Secrets)           (Encryption)        ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Terraform Project Structure

```
terraform/
├── modules/
│   ├── vpc/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── eks/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── dynamodb/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── elasticache/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── cloudfront/
│   │   ├── main.tf
│   │   ├── lambda-edge.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── waf/
│   │   ├── main.tf
│   │   ├── rules.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── observability/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   │   ├── main.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── production/
│       ├── main.tf
│       ├── terraform.tfvars
│       └── backend.tf
├── global/
│   ├── route53/
│   │   └── main.tf
│   ├── iam/
│   │   └── main.tf
│   └── s3/
│       └── main.tf
└── README.md
```

---

## Core Infrastructure Modules

### VPC Module

```hcl
# modules/vpc/main.tf

variable "environment" {
  type = string
}

variable "region" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["a", "b", "c"]
}

locals {
  name = "url-shortener-${var.environment}"

  public_subnets  = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i)]
  private_subnets = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i + 4)]
  data_subnets    = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i + 8)]
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = local.name
    Environment = var.environment
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name}-igw"
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.public_subnets[count.index]
  availability_zone = "${var.region}${var.availability_zones[count.index]}"

  map_public_ip_on_launch = true

  tags = {
    Name                                          = "${local.name}-public-${var.availability_zones[count.index]}"
    "kubernetes.io/role/elb"                      = "1"
    "kubernetes.io/cluster/${local.name}-cluster" = "shared"
  }
}

# Private Subnets (for EKS)
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.private_subnets[count.index]
  availability_zone = "${var.region}${var.availability_zones[count.index]}"

  tags = {
    Name                                          = "${local.name}-private-${var.availability_zones[count.index]}"
    "kubernetes.io/role/internal-elb"             = "1"
    "kubernetes.io/cluster/${local.name}-cluster" = "shared"
  }
}

# Data Subnets (for Redis, isolated)
resource "aws_subnet" "data" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.data_subnets[count.index]
  availability_zone = "${var.region}${var.availability_zones[count.index]}"

  tags = {
    Name = "${local.name}-data-${var.availability_zones[count.index]}"
  }
}

# NAT Gateways (one per AZ for HA)
resource "aws_eip" "nat" {
  count  = length(var.availability_zones)
  domain = "vpc"

  tags = {
    Name = "${local.name}-nat-${var.availability_zones[count.index]}"
  }
}

resource "aws_nat_gateway" "main" {
  count         = length(var.availability_zones)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name = "${local.name}-nat-${var.availability_zones[count.index]}"
  }
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${local.name}-public"
  }
}

resource "aws_route_table" "private" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = {
    Name = "${local.name}-private-${var.availability_zones[count.index]}"
  }
}

# VPC Endpoints for AWS services (no internet required)
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id

  tags = {
    Name = "${local.name}-dynamodb-endpoint"
  }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id

  tags = {
    Name = "${local.name}-s3-endpoint"
  }
}

# Outputs
output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "data_subnet_ids" {
  value = aws_subnet.data[*].id
}
```

### EKS Module

```hcl
# modules/eks/main.tf

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "kubernetes_version" {
  type    = string
  default = "1.28"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium", "t3.large"]
}

variable "desired_capacity" {
  type    = number
  default = 3
}

variable "min_capacity" {
  type    = number
  default = 2
}

variable "max_capacity" {
  type    = number
  default = 10
}

locals {
  name = "url-shortener-${var.environment}"
}

# EKS Cluster IAM Role
resource "aws_iam_role" "cluster" {
  name = "${local.name}-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}

# EKS Cluster
resource "aws_eks_cluster" "main" {
  name     = "${local.name}-cluster"
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    security_group_ids      = [aws_security_group.cluster.id]
  }

  enabled_cluster_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]

  encryption_config {
    provider {
      key_arn = aws_kms_key.eks.arn
    }
    resources = ["secrets"]
  }

  tags = {
    Environment = var.environment
  }
}

# EKS Node Group IAM Role
resource "aws_iam_role" "nodes" {
  name = "${local.name}-nodes-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "nodes_worker" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.nodes.name
}

resource "aws_iam_role_policy_attachment" "nodes_cni" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.nodes.name
}

resource "aws_iam_role_policy_attachment" "nodes_ecr" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.nodes.name
}

# Custom policy for DynamoDB, Redis, etc.
resource "aws_iam_role_policy" "nodes_app" {
  name = "${local.name}-nodes-app-policy"
  role = aws_iam_role.nodes.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          "arn:aws:dynamodb:*:*:table/url-shortener-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kinesis:PutRecord",
          "kinesis:PutRecords"
        ]
        Resource = [
          "arn:aws:kinesis:*:*:stream/url-shortener-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:*:*:secret:url-shortener/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = [
          aws_kms_key.eks.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = ["*"]
      }
    ]
  })
}

# EKS Node Group
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${local.name}-nodes"
  node_role_arn   = aws_iam_role.nodes.arn
  subnet_ids      = var.private_subnet_ids

  instance_types = var.node_instance_types
  capacity_type  = "ON_DEMAND"

  scaling_config {
    desired_size = var.desired_capacity
    min_size     = var.min_capacity
    max_size     = var.max_capacity
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    Environment = var.environment
    NodeGroup   = "main"
  }

  tags = {
    Environment = var.environment
  }
}

# Security Group for Cluster
resource "aws_security_group" "cluster" {
  name_prefix = "${local.name}-cluster-"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name}-cluster-sg"
  }
}

# KMS Key for encryption
resource "aws_kms_key" "eks" {
  description             = "EKS encryption key for ${local.name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Environment = var.environment
  }
}

# OIDC Provider for IRSA
data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

# Outputs
output "cluster_name" {
  value = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

output "cluster_security_group_id" {
  value = aws_security_group.cluster.id
}

output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.cluster.arn
}
```

### DynamoDB Module

```hcl
# modules/dynamodb/main.tf

variable "environment" {
  type = string
}

variable "enable_global_tables" {
  type    = bool
  default = false
}

variable "replica_regions" {
  type    = list(string)
  default = []
}

locals {
  name = "url-shortener-${var.environment}"
}

# URLs Table
resource "aws_dynamodb_table" "urls" {
  name         = "${local.name}-urls"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "N"
  }

  attribute {
    name = "expires_at_date"
    type = "S"
  }

  attribute {
    name = "expires_at"
    type = "N"
  }

  # GSI for user's URLs
  global_secondary_index {
    name            = "user-urls-index"
    hash_key        = "user_id"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  # GSI for expiration cleanup
  global_secondary_index {
    name            = "expires-at-index"
    hash_key        = "expires_at_date"
    range_key       = "expires_at"
    projection_type = "KEYS_ONLY"
  }

  # TTL for automatic expiration
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  # Global table replicas
  dynamic "replica" {
    for_each = var.enable_global_tables ? var.replica_regions : []
    content {
      region_name = replica.value
    }
  }

  tags = {
    Environment = var.environment
    Service     = "url-shortener"
  }
}

# Users Table
resource "aws_dynamodb_table" "users" {
  name         = "${local.name}-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "email"
    type = "S"
  }

  global_secondary_index {
    name            = "email-index"
    hash_key        = "email"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  dynamic "replica" {
    for_each = var.enable_global_tables ? var.replica_regions : []
    content {
      region_name = replica.value
    }
  }

  tags = {
    Environment = var.environment
    Service     = "url-shortener"
  }
}

# Counter Table (for ID generation)
resource "aws_dynamodb_table" "counters" {
  name         = "${local.name}-counters"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "counter_name"

  attribute {
    name = "counter_name"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Service     = "url-shortener"
  }
}

# Outputs
output "urls_table_name" {
  value = aws_dynamodb_table.urls.name
}

output "urls_table_arn" {
  value = aws_dynamodb_table.urls.arn
}

output "users_table_name" {
  value = aws_dynamodb_table.users.name
}

output "counters_table_name" {
  value = aws_dynamodb_table.counters.name
}
```

### CloudFront Module

```hcl
# modules/cloudfront/main.tf

variable "environment" {
  type = string
}

variable "domain_name" {
  type = string
}

variable "alb_dns_name" {
  type = string
}

variable "certificate_arn" {
  type = string
}

variable "waf_acl_arn" {
  type = string
}

locals {
  name = "url-shortener-${var.environment}"
}

# Origin Access Identity (not used for ALB but good to have)
resource "aws_cloudfront_origin_access_identity" "main" {
  comment = local.name
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = local.name
  default_root_object = ""
  price_class         = "PriceClass_All"
  web_acl_id          = var.waf_acl_arn

  aliases = [var.domain_name, "*.${var.domain_name}"]

  # ALB Origin
  origin {
    domain_name = var.alb_dns_name
    origin_id   = "alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-Origin-Verify"
      value = "secret-from-secrets-manager"  # Replace in production
    }
  }

  # Default behavior (API requests)
  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb"

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Host", "X-Correlation-ID"]

      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
    compress               = true

    # Lambda@Edge for authentication/rate limiting
    lambda_function_association {
      event_type   = "viewer-request"
      lambda_arn   = aws_lambda_function.edge_auth.qualified_arn
      include_body = false
    }
  }

  # Redirect behavior (cache aggressively)
  ordered_cache_behavior {
    path_pattern     = "/[a-zA-Z0-9]*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb"

    forwarded_values {
      query_string = false
      headers      = ["Host"]

      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400     # 24 hours
    max_ttl                = 31536000  # 1 year
    compress               = true

    # Lambda@Edge for redirect + analytics
    lambda_function_association {
      event_type   = "viewer-request"
      lambda_arn   = aws_lambda_function.edge_redirect.qualified_arn
      include_body = false
    }
  }

  # Health check endpoint (no caching)
  ordered_cache_behavior {
    path_pattern     = "/health*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "blacklist"
      locations        = ["KP", "IR", "SY", "CU"]  # Sanctioned countries
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  logging_config {
    include_cookies = false
    bucket          = "${local.name}-cf-logs.s3.amazonaws.com"
    prefix          = "cloudfront/"
  }

  tags = {
    Environment = var.environment
  }
}

# Lambda@Edge for redirect handling
resource "aws_lambda_function" "edge_redirect" {
  provider      = aws.us_east_1  # Lambda@Edge must be in us-east-1
  filename      = "${path.module}/lambda/redirect.zip"
  function_name = "${local.name}-edge-redirect"
  role          = aws_iam_role.edge_lambda.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"
  publish       = true

  memory_size = 128
  timeout     = 5

  tags = {
    Environment = var.environment
  }
}

# Lambda@Edge for auth/rate limiting
resource "aws_lambda_function" "edge_auth" {
  provider      = aws.us_east_1
  filename      = "${path.module}/lambda/auth.zip"
  function_name = "${local.name}-edge-auth"
  role          = aws_iam_role.edge_lambda.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"
  publish       = true

  memory_size = 128
  timeout     = 5

  tags = {
    Environment = var.environment
  }
}

# IAM Role for Lambda@Edge
resource "aws_iam_role" "edge_lambda" {
  name = "${local.name}-edge-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = [
          "lambda.amazonaws.com",
          "edgelambda.amazonaws.com"
        ]
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "edge_lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.edge_lambda.name
}

# Outputs
output "distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "distribution_domain_name" {
  value = aws_cloudfront_distribution.main.domain_name
}
```

---

## Production Environment Configuration

```hcl
# environments/production/main.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.primary_region

  default_tags {
    tags = {
      Project     = "url-shortener"
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

provider "aws" {
  alias  = "eu_west_1"
  region = "eu-west-1"
}

provider "aws" {
  alias  = "ap_south_1"
  region = "ap-south-1"
}

variable "primary_region" {
  default = "us-east-1"
}

variable "replica_regions" {
  default = ["eu-west-1", "ap-south-1"]
}

# Primary Region Infrastructure
module "vpc_primary" {
  source = "../../modules/vpc"

  environment = "production"
  region      = var.primary_region
  vpc_cidr    = "10.0.0.0/16"
}

module "eks_primary" {
  source = "../../modules/eks"

  environment        = "production"
  vpc_id             = module.vpc_primary.vpc_id
  private_subnet_ids = module.vpc_primary.private_subnet_ids
  kubernetes_version = "1.28"
  desired_capacity   = 5
  min_capacity       = 3
  max_capacity       = 20
}

module "elasticache_primary" {
  source = "../../modules/elasticache"

  environment        = "production"
  vpc_id             = module.vpc_primary.vpc_id
  subnet_ids         = module.vpc_primary.data_subnet_ids
  node_type          = "cache.r6g.large"
  num_cache_clusters = 3
}

# DynamoDB with Global Tables
module "dynamodb" {
  source = "../../modules/dynamodb"

  environment          = "production"
  enable_global_tables = true
  replica_regions      = var.replica_regions
}

# CloudFront
module "cloudfront" {
  source = "../../modules/cloudfront"

  environment     = "production"
  domain_name     = "short.io"
  alb_dns_name    = module.eks_primary.alb_dns_name
  certificate_arn = aws_acm_certificate.main.arn
  waf_acl_arn     = module.waf.web_acl_arn
}

# WAF
module "waf" {
  source = "../../modules/waf"

  environment = "production"
}

# Observability
module "observability" {
  source = "../../modules/observability"

  environment  = "production"
  cluster_name = module.eks_primary.cluster_name
}
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: url-shortener
  EKS_CLUSTER_NAME: url-shortener-production-cluster

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Rust
        uses: dtolnay/rust-action@stable

      - name: Run tests
        run: cargo test --all-features

      - name: Run clippy
        run: cargo clippy -- -D warnings

      - name: Check formatting
        run: cargo fmt -- --check

  build:
    needs: test
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.build.outputs.image_tag }}
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push Docker image
        id: build
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG -f docker/Dockerfile.prod .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image_tag=$IMAGE_TAG" >> $GITHUB_OUTPUT

  deploy-staging:
    needs: build
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name url-shortener-staging-cluster

      - name: Deploy to staging
        run: |
          kubectl set image deployment/url-shortener \
            url-shortener=${{ secrets.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ needs.build.outputs.image_tag }} \
            -n url-shortener
          kubectl rollout status deployment/url-shortener -n url-shortener

  deploy-production:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name ${{ env.EKS_CLUSTER_NAME }}

      - name: Deploy to production (canary)
        run: |
          # Update canary deployment first (10% traffic)
          kubectl set image deployment/url-shortener-canary \
            url-shortener=${{ secrets.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ needs.build.outputs.image_tag }} \
            -n url-shortener
          kubectl rollout status deployment/url-shortener-canary -n url-shortener

      - name: Wait for canary validation
        run: sleep 300  # 5 minutes

      - name: Check canary metrics
        run: |
          # Check error rate of canary vs stable
          # If error rate is significantly higher, fail the deployment
          ./scripts/check-canary-metrics.sh

      - name: Deploy to production (full)
        run: |
          kubectl set image deployment/url-shortener \
            url-shortener=${{ secrets.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ needs.build.outputs.image_tag }} \
            -n url-shortener
          kubectl rollout status deployment/url-shortener -n url-shortener

      - name: Invalidate CloudFront cache
        run: |
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.CLOUDFRONT_DISTRIBUTION_ID }} \
            --paths "/*"
```

---

## Disaster Recovery

### Multi-Region Failover

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DISASTER RECOVERY                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Route 53 Health Checks                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │  • Check ALB health every 30 seconds                                       │ │
│  │  • Failover threshold: 3 consecutive failures                             │ │
│  │  • Automatic DNS failover to next healthy region                          │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
│  Normal State:                                                                   │
│  ┌─────────────────┐                                                            │
│  │   Route 53      │                                                            │
│  │   Latency-based │                                                            │
│  └───────┬─────────┘                                                            │
│          │                                                                       │
│    ┌─────┼─────┬───────────┐                                                    │
│    ▼     ▼     ▼           ▼                                                    │
│  US-E1  EU-W1  AP-S1    (All healthy)                                          │
│                                                                                  │
│  Failover State (US-E1 down):                                                   │
│  ┌─────────────────┐                                                            │
│  │   Route 53      │                                                            │
│  │   Health-based  │                                                            │
│  └───────┬─────────┘                                                            │
│          │                                                                       │
│    ┌─────┼─────┬───────────┐                                                    │
│    ✗     ▼     ▼           │                                                    │
│  US-E1  EU-W1  AP-S1    (Traffic shifted)                                      │
│                                                                                  │
│  RTO: < 60 seconds (DNS TTL)                                                    │
│  RPO: < 1 second (DynamoDB Global Tables)                                       │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Backup and Recovery

```yaml
backup_strategy:
  dynamodb:
    - type: Point-in-Time Recovery
      retention: 35 days
      automated: true

    - type: On-demand backups
      frequency: daily
      retention: 90 days
      destination: s3://url-shortener-backups/dynamodb/

  redis:
    - type: Snapshots
      frequency: hourly
      retention: 24 hours

    - type: Daily backups
      frequency: daily
      retention: 7 days
      destination: s3://url-shortener-backups/redis/

  s3_audit_logs:
    - type: Cross-region replication
      source: us-east-1
      destination: eu-west-1

  secrets:
    - type: Secrets Manager replication
      regions: [us-east-1, eu-west-1, ap-south-1]

recovery_procedures:
  region_failure:
    steps:
      - Verify health check failures
      - Confirm Route 53 failover activated
      - Verify traffic routing to healthy regions
      - Monitor error rates in receiving regions
      - Scale up receiving regions if needed
      - Begin root cause analysis

  data_corruption:
    steps:
      - Identify scope of corruption
      - Pause writes to affected table
      - Initiate point-in-time recovery
      - Verify data integrity
      - Resume writes
      - Post-incident review
```

---

## Cost Optimization

### Estimated Monthly Costs (Tier 5 - 500M URLs/month)

| Service | Configuration | Estimated Cost |
|---------|--------------|----------------|
| CloudFront | 1.5TB data transfer | $1,500 |
| EKS | 15 nodes (3 regions) | $3,000 |
| EC2 (Nodes) | t3.large x 15 | $2,500 |
| DynamoDB | 500M writes, 50B reads | $15,000 |
| ElastiCache | r6g.large x 9 | $4,500 |
| Kinesis | 50 shards | $1,500 |
| Timestream | Storage + queries | $2,000 |
| S3 | Audit logs + exports | $500 |
| Data Transfer | Inter-region | $3,000 |
| WAF + Shield | Advanced | $6,000 |
| **Total** | | **~$40,000/month** |

### Cost Optimization Strategies

1. **Reserved Capacity**: 30-40% savings on EC2/ElastiCache
2. **DynamoDB On-Demand**: Pay per request, scale automatically
3. **CloudFront Caching**: Higher cache hit rate = lower origin costs
4. **Spot Instances**: For non-critical workloads
5. **Data Lifecycle**: Move old data to Glacier
