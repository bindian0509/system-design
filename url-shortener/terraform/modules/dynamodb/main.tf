# DynamoDB Module for URL Shortener

variable "environment" {
  type        = string
  description = "Environment name"
}

variable "enable_global_tables" {
  type        = bool
  default     = false
  description = "Enable DynamoDB Global Tables"
}

variable "replica_regions" {
  type        = list(string)
  default     = []
  description = "Regions for global table replicas"
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

# Counter Table
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
