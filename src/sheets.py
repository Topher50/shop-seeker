import gspread

LINK_COL = 5  # Column E = Link


class SheetsClient:
    def __init__(self, credentials_dict: dict, sheet_id: str):
        gc = gspread.service_account_from_dict(credentials_dict)
        self.spreadsheet = gc.open_by_key(sheet_id)

    def get_seen_urls(self) -> set[str]:
        urls = set()
        for tab_name in ("Approved", "Rejected"):
            ws = self.spreadsheet.worksheet(tab_name)
            col = ws.col_values(LINK_COL)
            urls.update(url for url in col[1:] if url)  # skip header
        return urls

    def append_approved(
        self,
        title: str,
        price: str,
        sqft: str,
        address: str,
        link: str,
        date_found: str,
        est_monthly_cost: str,
        suitability_score: str,
        ai_notes: str,
    ) -> None:
        ws = self.spreadsheet.worksheet("Approved")
        row = [
            title, price, sqft, address, link, date_found,
            est_monthly_cost, suitability_score, ai_notes,
            "", "", "",  # Followed Up?, Who, Notes (human columns)
        ]
        ws.append_row(row)

    def append_rejected(
        self,
        title: str,
        price: str,
        sqft: str,
        address: str,
        link: str,
        date_found: str,
        est_monthly_cost: str,
        suitability_score: str,
        rejection_reason: str,
    ) -> None:
        ws = self.spreadsheet.worksheet("Rejected")
        row = [
            title, price, sqft, address, link, date_found,
            est_monthly_cost, suitability_score, rejection_reason,
            "", "",  # Reviewed By, Notes (human columns)
        ]
        ws.append_row(row)
