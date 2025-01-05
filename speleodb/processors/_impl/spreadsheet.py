from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format

# ruff: noqa: E501


class SpreadsheetFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [
        # -------------------------- Microsoft Excel formats ------------------------- #
        #
        ".xls",  # Microsoft Excel 97-2003 Workbook format.
        ".xlsx",  # Microsoft Excel Open XML Workbook format (default from Excel 2007 onwards).
        ".xlsb",  # Excel Binary Workbook format.
        ".xlt",  # Excel 97-2003 Template format.
        ".xltx",  # Excel Open XML Template format.
        ".xltm",  # Excel Template with macros enabled.
        ".xlam",  # Excel Add-in file format.
        #
        # ---------------------- OpenDocument Spreadsheet (ODS) ---------------------- #
        #
        ".ods",  # OpenDocument Spreadsheet format, used in LibreOffice, OpenOffice, and other software.
        #
        # ---------------------- Comma and tab-separated values ---------------------- #
        #
        ".csv",  # Comma-Separated Values, widely used for spreadsheet data exchange.
        ".tsv",  # Tab-Separated Values, similar to CSV but with tabs instead of commas.
        #
        # --------------------- Other spreadsheet-related formats -------------------- #
        #
        ".dif",  # Data Interchange Format, an older spreadsheet exchange format.
        ".slk",  # Symbolic Link format, a standard for exchanging spreadsheet data.
        #
        # ----------------------- Google Sheets export formats ----------------------- #
        #
        ".gsheet",  # Google Sheets file format.
        #
        # ---------------------- Lotus 1-2-3 and related formats --------------------- #
        #
        ".wk1",  # Lotus 1-2-3 Worksheet format (older versions).
        ".wk3",  # Lotus 1-2-3 Worksheet (another older format).
        ".wk4",  # Lotus 1-2-3 Worksheet (even older format).
        #
        # --------------------- Apple Numbers and related formats -------------------- #
        #
        ".numbers",  # Apple Numbers spreadsheet format.
        #
        # --------------------- Miscellaneous spreadsheet formats -------------------- #
        #
        ".qpx",  # Quattro Pro Spreadsheet format.
        ".fods",  # Flat XML OpenDocument Spreadsheet format.
        ".vcs",  # vCalendar format, sometimes used for calendar data in spreadsheets.
    ]

    ALLOWED_MIMETYPES = ["*"]
    ASSOC_FILEFORMAT = Format.FileFormat.OTHER

    TARGET_FOLDER = "spreadsheets"
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None
