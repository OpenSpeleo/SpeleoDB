# Lesson: Never place executable statements between import groups

**Date:** 2026-02-26
**Trigger:** ruff E402 errors in `speleodb/gis/models/view.py`

## The mistake

```python
import logging
import re

logger = logging.getLogger(__name__)   # <-- executable code between imports

from django.db import models           # <-- E402: import not at top of file
from speleodb.gis.models import Foo    # <-- E402
```

Placing `logger = ...` between the stdlib and third-party import groups makes
ruff treat every subsequent import as "not at top of file" (E402).

## The fix

```python
import logging
import re

from django.db import models

from speleodb.gis.models import Foo

if TYPE_CHECKING:
    ...

logger = logging.getLogger(__name__)   # <-- after ALL imports
```

## Rule

Module-level assignments (`logger`, compiled regexes, constants derived from
imports) go **after all import blocks**, including `if TYPE_CHECKING`. The
only things allowed between `from __future__` and the last import are other
imports.

## Self-check

Before committing any Python file, verify: is there any non-import statement
sitting between two import lines? If yes, move it below all imports.
