-- MariaDB schema for MRM Webpanel (comprehensive)
CREATE DATABASE IF NOT EXISTS mrm_panel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mrm_panel;

-- Users table (superadmin and per-domain admins)
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(191) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('superadmin','admin') NOT NULL DEFAULT 'admin',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_role (role),
  INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Domains table (each admin can have one domain with one runtime)
CREATE TABLE IF NOT EXISTS domains (
  id INT AUTO_INCREMENT PRIMARY KEY,
  domain VARCHAR(255) NOT NULL UNIQUE,
  owner_user INT NOT NULL,
  runtime ENUM('php','python','node') NOT NULL,
  status ENUM('active','suspended','deleted') DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (owner_user) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_domain (domain),
  INDEX idx_owner (owner_user)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Sites table (apps within a domain)
CREATE TABLE IF NOT EXISTS sites (
  id INT AUTO_INCREMENT PRIMARY KEY,
  domain_id INT NOT NULL,
  name VARCHAR(255) NOT NULL,
  runtime VARCHAR(50),
  status ENUM('active','stopped','error','deploying','failed') DEFAULT 'active',
  deploy_error LONGTEXT DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
  INDEX idx_domain_id (domain_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Mail virtual domains
CREATE TABLE IF NOT EXISTS mail_domains (
  id INT AUTO_INCREMENT PRIMARY KEY,
  domain_id INT,
  domain VARCHAR(255) NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE SET NULL,
  INDEX idx_domain (domain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Mail virtual users
CREATE TABLE IF NOT EXISTS mail_users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  domain_id INT NOT NULL,
  username VARCHAR(191) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  mailbox VARCHAR(255) NOT NULL,
  quota_mb INT DEFAULT 1024,
  enabled TINYINT DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY (domain_id, username),
  FOREIGN KEY (domain_id) REFERENCES mail_domains(id) ON DELETE CASCADE,
  INDEX idx_mailbox (mailbox)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Mail aliases
CREATE TABLE IF NOT EXISTS mail_aliases (
  id INT AUTO_INCREMENT PRIMARY KEY,
  domain_id INT NOT NULL,
  alias_local VARCHAR(191) NOT NULL,
  alias_to VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY (domain_id, alias_local),
  FOREIGN KEY (domain_id) REFERENCES mail_domains(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Databases table (per-domain MariaDB databases)
CREATE TABLE IF NOT EXISTS `databases` (
  id INT AUTO_INCREMENT PRIMARY KEY,
  domain_id INT NOT NULL,
  name VARCHAR(64) NOT NULL,
  created_by INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY (domain_id, name),
  FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
  INDEX idx_domain_id (domain_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Database users (credentials to access databases)
CREATE TABLE IF NOT EXISTS database_users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  database_id INT NOT NULL,
  username VARCHAR(32) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY (database_id, username),
  FOREIGN KEY (database_id) REFERENCES `databases`(id) ON DELETE CASCADE,
  INDEX idx_database_id (database_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- DKIM keys storage
CREATE TABLE IF NOT EXISTS dkim_keys (
  id INT AUTO_INCREMENT PRIMARY KEY,
  domain_id INT NOT NULL,
  domain VARCHAR(255) NOT NULL,
  selector VARCHAR(64) DEFAULT 'default',
  private_key LONGTEXT NOT NULL,
  public_key LONGTEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY (domain_id, selector),
  FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
  INDEX idx_domain (domain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- DNS zones
CREATE TABLE IF NOT EXISTS dns_zones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  domain_id INT NOT NULL,
  domain VARCHAR(255) NOT NULL UNIQUE,
  zone_file_path VARCHAR(255),
  status ENUM('active','pending','error') DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
  INDEX idx_domain (domain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- DNS records (A, MX, TXT, etc.)
CREATE TABLE IF NOT EXISTS dns_records (
  id INT AUTO_INCREMENT PRIMARY KEY,
  zone_id INT NOT NULL,
  type VARCHAR(10) NOT NULL,
  name VARCHAR(255),
  value TEXT NOT NULL,
  ttl INT DEFAULT 3600,
  priority INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (zone_id) REFERENCES dns_zones(id) ON DELETE CASCADE,
  INDEX idx_zone_id (zone_id),
  INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- SFTP/SSH accounts
CREATE TABLE IF NOT EXISTS sftp_accounts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  domain_id INT NOT NULL,
  account_name VARCHAR(32) NOT NULL,
  chroot_dir VARCHAR(255) NOT NULL,
  enabled TINYINT DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY (domain_id, account_name),
  FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
  INDEX idx_account_name (account_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Activity logs
CREATE TABLE IF NOT EXISTS activity_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  action VARCHAR(255) NOT NULL,
  resource_type VARCHAR(50),
  resource_id INT,
  details TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  INDEX idx_user_id (user_id),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
