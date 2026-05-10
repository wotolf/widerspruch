resource "aws_security_group" "rds" {
  name        = "widerspruch-${var.environment}-rds"
  description = "Erlaubt Postgres-Zugriff aus dem VPC"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "widerspruch-${var.environment}-rds"
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "widerspruch-${var.environment}"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = {
    Name = "widerspruch-${var.environment}"
  }
}

resource "aws_db_instance" "main" {
  identifier        = "widerspruch-${var.environment}"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = "db.t4g.micro"
  db_name           = "widerspruch"
  username          = "widerspruch"
  password          = var.db_password
  allocated_storage = 20

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  skip_final_snapshot = true

  tags = {
    Name = "widerspruch-${var.environment}"
  }
}
