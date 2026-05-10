locals {
  ecr_image    = "794457362356.dkr.ecr.eu-central-1.amazonaws.com/widerspruch-bot:latest"
  rds_endpoint = "widerspruch-dev.c9igkim624sd.eu-central-1.rds.amazonaws.com"
}

# ---------------------------------------------------------------------------
# ECS Cluster
# ---------------------------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = "widerspruch-${var.environment}"

  tags = {
    Name = "widerspruch-${var.environment}"
  }
}

# ---------------------------------------------------------------------------
# IAM — Task Execution Role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "widerspruch-${var.environment}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = {
    Name = "widerspruch-${var.environment}-ecs-execution"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "secrets_read" {
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:794457362356:secret:widerspruch/discord-token*",
      "arn:aws:secretsmanager:${var.aws_region}:794457362356:secret:widerspruch/anthropic-key*",
      "arn:aws:secretsmanager:${var.aws_region}:794457362356:secret:widerspruch/db-password*",
    ]
  }
}

resource "aws_iam_role_policy" "ecs_secrets" {
  name   = "secrets-read"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.secrets_read.json
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "bot" {
  name              = "/widerspruch/bot"
  retention_in_days = 14

  tags = {
    Name = "widerspruch-${var.environment}"
  }
}

# ---------------------------------------------------------------------------
# ECS Task Definition
# ---------------------------------------------------------------------------

resource "aws_ecs_task_definition" "bot" {
  family                   = "widerspruch-bot"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([{
    name  = "bot"
    image = local.ecr_image

    environment = [
      {
        name  = "DB_HOST"
        value = local.rds_endpoint
      },
      {
        name  = "DB_PORT"
        value = "5432"
      },
      {
        name  = "DB_NAME"
        value = "widerspruch"
      },
      {
        name  = "LOG_LEVEL"
        value = "INFO"
      },
      {
        name  = "ENVIRONMENT"
        value = "production"
      },
    ]

    secrets = [
      {
        name      = "DISCORD_TOKEN"
        valueFrom = "arn:aws:secretsmanager:${var.aws_region}:794457362356:secret:widerspruch/discord-token"
      },
      {
        name      = "ANTHROPIC_API_KEY"
        valueFrom = "arn:aws:secretsmanager:${var.aws_region}:794457362356:secret:widerspruch/anthropic-key"
      },
      {
        name      = "DB_PASSWORD"
        valueFrom = "arn:aws:secretsmanager:${var.aws_region}:794457362356:secret:widerspruch/db-password"
      },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.bot.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "bot"
      }
    }
  }])

  tags = {
    Name = "widerspruch-${var.environment}"
  }
}

# ---------------------------------------------------------------------------
# Security Group — Bot (outbound only)
# ---------------------------------------------------------------------------

resource "aws_security_group" "bot" {
  name        = "widerspruch-${var.environment}-bot"
  description = "ECS Bot Task - nur ausgehender Traffic"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "widerspruch-${var.environment}-bot"
  }
}

# ---------------------------------------------------------------------------
# ECS Service
# ---------------------------------------------------------------------------

resource "aws_ecs_service" "bot" {
  name            = "widerspruch-bot"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.bot.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.bot.id]
    assign_public_ip = true
  }

  tags = {
    Name = "widerspruch-${var.environment}"
  }
}
