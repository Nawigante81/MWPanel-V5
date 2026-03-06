"""
Google Sheets integration.
Sync offers to Google Sheets for easy sharing and analysis.
"""
from typing import List, Optional
from datetime import datetime

from app.logging_config import get_logger
from app.settings import settings

logger = get_logger("google_sheets")


class GoogleSheetsSync:
    """
    Sync offers to Google Sheets.
    
    Requires Google Service Account credentials.
    """
    
    def __init__(self):
        self.credentials_file = getattr(settings, 'GOOGLE_CREDENTIALS_FILE', None)
        self.spreadsheet_id = getattr(settings, 'GOOGLE_SHEETS_ID', None)
        self.enabled = bool(self.credentials_file and self.spreadsheet_id)
    
    async def sync_offers(
        self,
        offers: List[dict],
        sheet_name: str = "Offers"
    ) -> bool:
        """
        Sync offers to Google Sheet.
        
        Args:
            offers: List of offer dicts
            sheet_name: Name of the sheet tab
        
        Returns:
            True if successful
        """
        if not self.enabled:
            logger.warning("Google Sheets not configured")
            return False
        
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            # Authenticate
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=scopes
            )
            
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(self.spreadsheet_id)
            
            # Get or create worksheet
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
                worksheet.clear()
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(sheet_name, rows=1000, cols=20)
            
            # Prepare data
            headers = [
                "ID", "Source", "Title", "Price", "Currency",
                "City", "Region", "Area m²", "Rooms",
                "URL", "First Seen", "Last Seen", "Status"
            ]
            
            rows = [headers]
            
            for offer in offers:
                rows.append([
                    offer.get("id", ""),
                    offer.get("source", ""),
                    offer.get("title", ""),
                    offer.get("price", ""),
                    offer.get("currency", "PLN"),
                    offer.get("city", ""),
                    offer.get("region", ""),
                    offer.get("area_m2", ""),
                    offer.get("rooms", ""),
                    offer.get("url", ""),
                    offer.get("first_seen", ""),
                    offer.get("last_seen", ""),
                    offer.get("status", "active"),
                ])
            
            # Update sheet
            worksheet.update(rows)
            
            # Format header
            worksheet.format('A1:M1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            logger.info(f"Synced {len(offers)} offers to Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets sync failed: {e}")
            return False
    
    async def append_offer(self, offer: dict, sheet_name: str = "Offers") -> bool:
        """Append a single offer to the sheet."""
        if not self.enabled:
            return False
        
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=scopes
            )
            
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(self.spreadsheet_id)
            
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(sheet_name, rows=1000, cols=20)
                # Add headers
                worksheet.append_row([
                    "ID", "Source", "Title", "Price", "Currency",
                    "City", "Region", "Area m²", "Rooms",
                    "URL", "First Seen", "Last Seen", "Status"
                ])
            
            worksheet.append_row([
                offer.get("id", ""),
                offer.get("source", ""),
                offer.get("title", ""),
                offer.get("price", ""),
                offer.get("currency", "PLN"),
                offer.get("city", ""),
                offer.get("region", ""),
                offer.get("area_m2", ""),
                offer.get("rooms", ""),
                offer.get("url", ""),
                offer.get("first_seen", ""),
                offer.get("last_seen", ""),
                offer.get("status", "active"),
            ])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to append offer: {e}")
            return False


# Global instance
_sheets_sync: Optional[GoogleSheetsSync] = None


def get_google_sheets_sync() -> GoogleSheetsSync:
    """Get or create Google Sheets sync."""
    global _sheets_sync
    
    if _sheets_sync is None:
        _sheets_sync = GoogleSheetsSync()
    
    return _sheets_sync
