"""
Backup service for database and exports.
Supports S3, MinIO, and local storage.
"""
import os
import gzip
from datetime import datetime, timedelta
from typing import Optional
from io import BytesIO

from app.logging_config import get_logger
from app.settings import settings

logger = get_logger("backup")


class BackupService:
    """
    Backup service for database and exports.
    
    Supports:
    - S3 (AWS)
    - MinIO (self-hosted S3)
    - Local filesystem
    """
    
    def __init__(self):
        self.s3_endpoint = getattr(settings, 'S3_ENDPOINT', None)
        self.s3_bucket = getattr(settings, 'S3_BUCKET', 'real-estate-backups')
        self.s3_access_key = getattr(settings, 'S3_ACCESS_KEY', None)
        self.s3_secret_key = getattr(settings, 'S3_SECRET_KEY', None)
        self.s3_region = getattr(settings, 'S3_REGION', 'us-east-1')
        
        self.local_backup_path = getattr(settings, 'LOCAL_BACKUP_PATH', '/backup')
        
        self.enabled = bool(
            (self.s3_endpoint and self.s3_access_key and self.s3_secret_key) or
            self.local_backup_path
        )
    
    async def backup_database(self, db_dump: bytes) -> bool:
        """
        Backup database dump.
        
        Args:
            db_dump: Database dump as bytes
        
        Returns:
            True if successful
        """
        if not self.enabled:
            logger.warning("Backup not configured")
            return False
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"db_backup_{timestamp}.sql.gz"
        
        # Compress
        compressed = gzip.compress(db_dump)
        
        success = False
        
        # Upload to S3/MinIO
        if self.s3_endpoint:
            success = await self._upload_to_s3(compressed, filename)
        
        # Save locally
        if self.local_backup_path:
            local_success = self._save_locally(compressed, filename)
            success = success or local_success
        
        return success
    
    async def backup_exports(self, export_data: bytes, export_type: str) -> bool:
        """
        Backup export files.
        
        Args:
            export_data: Export file content
            export_type: Type of export (csv, json, excel)
        
        Returns:
            True if successful
        """
        if not self.enabled:
            return False
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{export_type}_{timestamp}.{export_type}"
        
        success = False
        
        if self.s3_endpoint:
            success = await self._upload_to_s3(export_data, filename)
        
        if self.local_backup_path:
            local_success = self._save_locally(export_data, filename)
            success = success or local_success
        
        return success
    
    async def _upload_to_s3(self, data: bytes, filename: str) -> bool:
        """Upload data to S3/MinIO."""
        try:
            import boto3
            from botocore.config import Config
            
            s3 = boto3.client(
                's3',
                endpoint_url=self.s3_endpoint,
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
                region_name=self.s3_region,
                config=Config(signature_version='s3v4')
            )
            
            # Create bucket if not exists
            try:
                s3.head_bucket(Bucket=self.s3_bucket)
            except:
                s3.create_bucket(Bucket=self.s3_bucket)
            
            # Upload
            s3.put_object(
                Bucket=self.s3_bucket,
                Key=filename,
                Body=data
            )
            
            logger.info(f"Uploaded backup to S3: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return False
    
    def _save_locally(self, data: bytes, filename: str) -> bool:
        """Save data to local filesystem."""
        try:
            os.makedirs(self.local_backup_path, exist_ok=True)
            
            filepath = os.path.join(self.local_backup_path, filename)
            
            with open(filepath, 'wb') as f:
                f.write(data)
            
            logger.info(f"Saved backup locally: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Local backup failed: {e}")
            return False
    
    async def list_backups(self, prefix: str = "") -> list:
        """List available backups."""
        backups = []
        
        # List from S3
        if self.s3_endpoint:
            try:
                import boto3
                
                s3 = boto3.client(
                    's3',
                    endpoint_url=self.s3_endpoint,
                    aws_access_key_id=self.s3_access_key,
                    aws_secret_access_key=self.s3_secret_key,
                )
                
                response = s3.list_objects_v2(
                    Bucket=self.s3_bucket,
                    Prefix=prefix
                )
                
                for obj in response.get('Contents', []):
                    backups.append({
                        "name": obj['Key'],
                        "size": obj['Size'],
                        "modified": obj['LastModified'].isoformat(),
                        "location": "s3"
                    })
                    
            except Exception as e:
                logger.error(f"Failed to list S3 backups: {e}")
        
        # List local
        if self.local_backup_path and os.path.exists(self.local_backup_path):
            for filename in os.listdir(self.local_backup_path):
                if prefix in filename:
                    filepath = os.path.join(self.local_backup_path, filename)
                    stat = os.stat(filepath)
                    backups.append({
                        "name": filename,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "location": "local"
                    })
        
        return sorted(backups, key=lambda x: x['modified'], reverse=True)
    
    async def cleanup_old_backups(self, keep_days: int = 30):
        """Remove backups older than keep_days."""
        cutoff = datetime.utcnow() - timedelta(days=keep_days)
        
        # Cleanup S3
        if self.s3_endpoint:
            try:
                import boto3
                
                s3 = boto3.client(
                    's3',
                    endpoint_url=self.s3_endpoint,
                    aws_access_key_id=self.s3_access_key,
                    aws_secret_access_key=self.s3_secret_key,
                )
                
                response = s3.list_objects_v2(Bucket=self.s3_bucket)
                
                for obj in response.get('Contents', []):
                    if obj['LastModified'].replace(tzinfo=None) < cutoff:
                        s3.delete_object(
                            Bucket=self.s3_bucket,
                            Key=obj['Key']
                        )
                        logger.info(f"Deleted old S3 backup: {obj['Key']}")
                        
            except Exception as e:
                logger.error(f"S3 cleanup failed: {e}")
        
        # Cleanup local
        if self.local_backup_path and os.path.exists(self.local_backup_path):
            for filename in os.listdir(self.local_backup_path):
                filepath = os.path.join(self.local_backup_path, filename)
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if mtime < cutoff:
                    os.remove(filepath)
                    logger.info(f"Deleted old local backup: {filename}")


# Celery task for scheduled backups
from app.tasks.celery_app import celery_app


@celery_app.task
def scheduled_backup():
    """Run scheduled backup."""
    import asyncio
    asyncio.run(_run_backup())


async def _run_backup():
    """Async backup function."""
    from app.db import sync_engine
    
    backup_service = BackupService()
    
    if not backup_service.enabled:
        logger.info("Backup not configured, skipping")
        return
    
    try:
        # Create database dump
        import subprocess
        
        db_url = settings.database_url_sync
        # Parse connection string
        # postgresql://user:pass@host:port/dbname
        
        result = subprocess.run(
            ['pg_dump', db_url],
            capture_output=True
        )
        
        if result.returncode == 0:
            success = await backup_service.backup_database(result.stdout)
            if success:
                logger.info("Database backup completed")
            else:
                logger.error("Database backup failed")
        else:
            logger.error(f"pg_dump failed: {result.stderr}")
        
        # Cleanup old backups
        await backup_service.cleanup_old_backups(keep_days=30)
        
    except Exception as e:
        logger.error(f"Scheduled backup failed: {e}")


# Global instance
_backup_service: Optional[BackupService] = None


def get_backup_service() -> BackupService:
    """Get or create backup service."""
    global _backup_service
    
    if _backup_service is None:
        _backup_service = BackupService()
    
    return _backup_service
