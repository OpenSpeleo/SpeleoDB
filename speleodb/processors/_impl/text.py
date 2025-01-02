from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format

# ruff: noqa: E501


class TextFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [
        # ------------------------- Common plain text formats ------------------------ #
        #
        ".txt",  # Standard plain text file, widely used for unformatted text.
        ".md",  # Markdown, lightweight markup language for formatted text.
        ".rtf",  # Rich Text Format, supports basic text styling.
        ".log",  # Log files, typically used for recording events or processes.
        ".ini",  # Initialization files, used for configuration settings.
        #
        # --------------------- Programming and markup languages --------------------- #
        #
        ".html",  # Hypertext Markup Language, used in web development.
        ".xml",  # Extensible Markup Language, used for structured data.
        ".json",  # JavaScript Object Notation, a lightweight data-interchange format.
        ".yml",  # YAML Ain't Markup Language, used for configuration files.
        ".yaml",  # YAML Ain't Markup Language, used for configuration files.
        ".toml",  # TOML, a configuration file format with minimal syntax.
        ".php",  # PHP Hypertext Preprocessor, often contains text and code.
        ".css",  # Cascading Style Sheets, describes how HTML elements are displayed.
        ".js",  # JavaScript files, can include both text and code.
        ".py",  # Python script files, often mixed text and code.
        ".sh",  # Shell scripts, plain text files containing shell commands.
        #
        # -------------------- Documentation and technical formats ------------------- #
        #
        ".tex",  # LaTeX, used for typesetting complex documents.
        ".bib",  # BibTeX, bibliography format for LaTeX.
        ".doc",  # Microsoft Word documents (technically zipped XML).
        ".docx",  # Microsoft Word documents (technically zipped XML).
        ".odt",  # OpenDocument Text, an open standard text document format.
        ".pptx",  # PowerPoint files (text content within slides).
        ".epub",  # eBook format, often includes structured text.
        ".pdf",  # Portable Document Format (can include plain or rich text).
        #
        # -------------------------- Code and scripting logs ------------------------- #
        #
        ".bat",  # Batch files, plain text commands for Windows.
        ".cmd",  # Command script files, similar to .bat but on Windows NT.
        ".pl",  # Perl scripts, plain text code with Perl syntax.
        ".java",  # Java source files, plain text containing Java code.
        ".cpp",  # C++ source files, plain text containing C++ code.
        #
        # ------------------------- Specialized text formats ------------------------- #
        #
        ".config",  # Configuration files, used for application settings.
        ".env",  # Environment files, often used for application settings.
        ".po",  # Portable Object files, used for translations.
        ".pot",  # Portable Object Template, used in software localization.
        ".resx",  # .NET resource files, used for storing application resources.
        ".lst",  # List files, often used for plain text lists or input files.
        #
        # ----------------------- Legacy and niche text formats ---------------------- #
        #
        ".asc",  # ASCII files, plain text, often used for emails or simple documents.
        ".ans",  # ANSI text files, a legacy format.
        ".nfo",  # Info files, often used in software distributions.
        ".wri",  # Windows Write files, an older text editor format.
        ".diz",  # Description in Zip files, used for metadata.
        ".ps",  # PostScript files, plain text instructions for printers.
        ".man",  # Unix manual pages, plain text documentation.
        ".me",  # Troff macros, used in Unix-based systems.
        ".1",  # Section 1 man page, for general commands.
        #
        # -------------------------  Data and storage formats ------------------------ #
        #
        ".ldif",  # LDAP Data Interchange Format, used for directory entries.
        ".rdf",  # Resource Description Framework, structured data format.
        #
        # --------------------------- Miscellaneous formats -------------------------- #
        #
        ".rst",  # reStructuredText, used for technical documentation.
        ".adoc",  # AsciiDoc, similar to Markdown but more powerful.
        ".vtt",  # WebVTT, used for subtitles in videos.
        ".srt",  # SubRip subtitle format, used for video captions.
        ".texinfo",  # GNU Texinfo, used for documentation.
        ".c",  # C source code, often treated as plain text.
        ".h",  # Header files for C/C++.
        ".go",  # Go programming language source code.
        ".rb",  # Ruby scripts, plain text with Ruby syntax.
        ".lua",  # Lua scripts, plain text scripting files.
    ]

    ALLOWED_MIMETYPES = ["*"]
    ASSOC_FILEFORMAT = Format.FileFormat.OTHER

    TARGET_FOLDER = "documents"
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None
