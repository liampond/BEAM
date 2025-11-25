# Core Modules

## db_utils.py

Database helper functions for working with the benchmark database.

**Usage**:
```python
import sys
sys.path.insert(0, 'src')
from core.db_utils import get_piece_id, get_or_create_passage, add_question
from core.db_utils import list_passages, list_questions, show_stats

# Get statistics
show_stats()

# List all passages and questions
list_passages()
list_questions()
```

## extract_passage.py

Extracts specific measures from music encoding files with full headers and metadata.

### Supported Formats

- **Humdrum** (.krn): Extracts with all reference records and interpretations
- **ABC** (.abc): Extracts with complete header
- **MusicXML** (.xml/.musicxml): Extracts with part-list and attributes
- **MEI** (.mei): Extracts with scoreDef and section structure

### Usage

**CLI**:
```bash
# Extract measures 1-4 from Sonata 16, Movement 1 (all formats)
python src/core/extract_passage.py --sonata 16 --movement 1 --measures 1-4

# Extract specific format only
python src/core/extract_passage.py --sonata 16 --movement 1 --measures 1-4 --format mei
```

**Library**:
```python
from src.core.extract_passage import extract

content = extract(
    format='abc',
    file_path='data/abc/04-3.abc',
    start_measure=58,
    end_measure=58
)
```
