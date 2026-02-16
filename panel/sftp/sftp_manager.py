"""
SFTP user management with chroot jail.
Creates restricted SFTP users per domain for secure file access.
"""

import os
import subprocess
import logging
import secrets
import string

logger = logging.getLogger(__name__)

class SFTPManager:
    """Manage SFTP users with chroot jail for domain file access."""
    
    def __init__(self, domain, site_dir):
        self.domain = domain
        self.site_dir = site_dir
        self.username = self._generate_username()
        self.password = None
        self.sftp_group = 'sftpusers'
    
    def _generate_username(self):
        """Generate SFTP username from domain."""
        # Convert domain to valid username (alphanumeric + underscore)
        username = self.domain.replace('.', '_').replace('-', '_')
        # Limit to 32 chars (Linux username limit)
        return username[:32]
    
    def _generate_password(self):
        """Generate a secure random password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(16))
        return password
    
    def create_user(self):
        """Create SFTP user with chroot jail."""
        try:
            # Ensure SFTP group exists
            self._ensure_sftp_group()
            
            # Generate password
            self.password = self._generate_password()
            
            # Check if user already exists
            try:
                subprocess.run(['id', self.username], check=True, capture_output=True)
                logger.warning(f"User {self.username} already exists, deleting and recreating")
                # Force delete the user - use -f to force removal even if logged in
                result = subprocess.run(
                    ['userdel', '-r', '-f', self.username], 
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    logger.warning(f"userdel warning: {result.stderr}")
                # Wait a moment for the system to clean up
                import time
                time.sleep(0.5)
            except subprocess.CalledProcessError:
                # User doesn't exist, good
                pass
            
            # Create user with no shell (SFTP only)
            result = subprocess.run([
                'useradd',
                '-m',  # Create home directory
                '-d', self.site_dir,  # Home directory = site directory
                '-g', self.sftp_group,  # Primary group
                '-s', '/usr/sbin/nologin',  # No shell access
                self.username
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logger.error(f"useradd failed: {error_msg}")
                raise Exception(f"Failed to create user: {error_msg}")
            
            # Set password
            process = subprocess.Popen(
                ['chpasswd'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            process.communicate(f"{self.username}:{self.password}\n".encode())
            
            # Set ownership and permissions
            self._setup_permissions()
            
            logger.info(f"Created SFTP user: {self.username}")
            return {
                'username': self.username,
                'password': self.password,
                'site_dir': self.site_dir
            }
        
        except Exception as e:
            logger.error(f"Failed to create SFTP user: {e}")
            raise
    
    def _ensure_sftp_group(self):
        """Ensure the SFTP users group exists."""
        try:
            subprocess.run(['getent', 'group', self.sftp_group], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Group doesn't exist, create it
            subprocess.run(['groupadd', self.sftp_group], check=True, capture_output=True)
            logger.info(f"Created SFTP group: {self.sftp_group}")
    
    def _setup_permissions(self):
        """Setup proper permissions for chroot SFTP."""
        try:
            # The parent directory (site_dir) must be owned by root for chroot
            # But we want the data/ subdirectory to be owned by the SFTP user
            
            # Set site_dir ownership to root (required for chroot)
            subprocess.run(['chown', 'root:root', self.site_dir], check=True)
            subprocess.run(['chmod', '755', self.site_dir], check=True)
            
            # Set data directory ownership to SFTP user
            data_dir = os.path.join(self.site_dir, 'data')
            if os.path.exists(data_dir):
                subprocess.run(['chown', '-R', f'{self.username}:{self.sftp_group}', data_dir], check=True)
                # Set 775 for directories (rwxrwxr-x) and 664 for files (rw-rw-r--)
                subprocess.run(['find', data_dir, '-type', 'd', '-exec', 'chmod', '775', '{}', '+'], check=True)
                subprocess.run(['find', data_dir, '-type', 'f', '-exec', 'chmod', '664', '{}', '+'], check=True)
                logger.info(f"Set permissions for {data_dir}")
        
        except Exception as e:
            logger.error(f"Failed to setup permissions: {e}")
    
    def delete_user(self):
        """Delete SFTP user."""
        try:
            # Use -f flag to force removal even if user is logged in
            result = subprocess.run(
                ['userdel', '-r', '-f', self.username], 
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"Deleted SFTP user: {self.username}")
                return True
            else:
                logger.warning(f"userdel completed with warnings: {result.stderr}")
                return True  # Still count as success if user is gone
        except Exception as e:
            logger.error(f"Failed to delete SFTP user: {e}")
            return False
    
    @staticmethod
    def configure_ssh_chroot():
        """Configure SSH for chroot SFTP access (one-time setup)."""
        sshd_config = '/etc/ssh/sshd_config'
        
        try:
            # Check if already configured
            with open(sshd_config, 'r') as f:
                content = f.read()
            
            if 'Match Group sftpusers' in content:
                # Ensure we start users in /data for a better UX.
                # This avoids confusion where the chroot root only contains the `data/` folder.
                updated = False
                if 'ForceCommand internal-sftp -d /data' not in content:
                    if 'ForceCommand internal-sftp' in content:
                        content = content.replace('ForceCommand internal-sftp', 'ForceCommand internal-sftp -d /data')
                        updated = True

                if updated:
                    with open(sshd_config, 'w') as f:
                        f.write(content)

                    result = subprocess.run(['sshd', '-t'], capture_output=True)
                    if result.returncode != 0:
                        logger.error(f"SSH config test failed after update: {result.stderr.decode()}")
                        return False

                    subprocess.run(['systemctl', 'restart', 'sshd'], check=True)
                    logger.info("SSH chroot updated (start dir /data) and service restarted")
                else:
                    logger.info("SSH chroot already configured")
                return True
            
            # Append SFTP chroot configuration
            sftp_config = """
# MRM Panel SFTP Chroot Configuration
Match Group sftpusers
    ChrootDirectory %h
    ForceCommand internal-sftp -d /data
    AllowTcpForwarding no
    X11Forwarding no
"""
            
            with open(sshd_config, 'a') as f:
                f.write(sftp_config)
            
            # Test SSH configuration
            result = subprocess.run(['sshd', '-t'], capture_output=True)
            if result.returncode != 0:
                logger.error(f"SSH config test failed: {result.stderr.decode()}")
                return False
            
            # Reload SSH service
            subprocess.run(['systemctl', 'restart', 'sshd'], check=True)
            logger.info("SSH chroot configured and service restarted")
            return True
        
        except Exception as e:
            logger.error(f"Failed to configure SSH chroot: {e}")
            return False
